"""Record the real ELIA browser tour and encode a shareable 1080p MP4.

Requires the project's existing Python Playwright, installed Chromium and ffmpeg.
Run from any directory: python tools/video/record_walkthrough.py --theme original
"""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import textwrap

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def chromium_executable() -> str:
    cache = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    candidates = list(cache.glob("chromium_headless_shell-*/**/chrome-headless-shell.exe"))
    if not candidates:
        candidates = list(cache.glob("chromium-*/**/chrome.exe"))
    if not candidates:
        raise RuntimeError("No installed Playwright Chromium was found.")
    return str(sorted(candidates)[-1])


def calibrated_trim(ffmpeg: str, raw_video: Path, approximate_start: float) -> float:
    """Find the first real video frame after the removable green sync marker."""
    pixels = subprocess.check_output(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(raw_video),
         "-t", f"{approximate_start + 1:.3f}", "-vf",
         "fps=25,crop=12:12:2:2,scale=1:1:flags=area,format=rgb24",
         "-f", "rawvideo", "pipe:1"]
    )
    marked_frames = [i // 3 for i in range(0, len(pixels) - 2, 3)
                     if pixels[i] < 65 and pixels[i + 1] > 200 and pixels[i + 2] < 65]
    if not marked_frames:
        raise RuntimeError("Recording calibration marker was not captured.")
    return (marked_frames[-1] + 1) / 25


def subtitle_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def write_subtitles(path: Path, definitions: list[dict], starts: list[dict], end: float) -> int:
    """Use actual chapter timing and the tour's French text for an editable SRT."""
    observed = {entry["index"]: entry["seconds"] for entry in starts}
    nominal = 0.0
    timeline = []
    for i, definition in enumerate(definitions):
        timeline.append(observed.get(i, nominal))
        nominal += definition["duration"]
    cues = []
    for i, definition in enumerate(definitions):
        start = timeline[i]
        stop = timeline[i + 1] if i + 1 < len(timeline) else end
        heading_end = start + min(3.0, (stop - start) / 4)
        heading = "\n".join(textwrap.wrap(definition["heading"], width=72))
        cues.append((start, heading_end - .04, heading))
        lines = textwrap.wrap(definition["body"], width=72)
        chunks = ["\n".join(lines[j:j + 2]) for j in range(0, len(lines), 2)]
        character_total = sum(len(chunk) for chunk in chunks)
        cursor = heading_end
        for chunk in chunks:
            cue_end = cursor + (stop - heading_end) * len(chunk) / max(1, character_total)
            cues.append((cursor, cue_end - .04, chunk))
            cursor = cue_end
    path.write_text("\n\n".join(
        f"{i}\n{subtitle_time(start)} --> {subtitle_time(stop)}\n{caption}"
        for i, (start, stop, caption) in enumerate(cues, 1)
    ) + "\n", encoding="utf-8")
    return len(cues)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", default="index.html", help="HTML path relative to the project root")
    parser.add_argument("--url", help="Existing server URL (otherwise start a temporary local server)")
    parser.add_argument("--theme", choices=("original", "dark", "light"), default="original")
    parser.add_argument("--output", default="dist/elia-visite-guidee.mp4")
    parser.add_argument("--timeout", type=float, default=240, help="Maximum tour duration, seconds")
    parser.add_argument("--tail", type=float, default=2, help="Seconds to keep the closing screen visible")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--headed", action="store_true", help="Display the browser while recording")
    args = parser.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe must be on PATH.")
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    captures = output.parent / (output.stem + "-apercus")
    captures.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / ".cache" / "video" / output.stem
    scratch.mkdir(parents=True, exist_ok=True)

    server = None
    if args.url:
        url = args.url
    else:
        html_path = (ROOT / args.html).resolve()
        relative = html_path.relative_to(ROOT).as_posix()
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_address[1]}/{relative}"

    errors: list[str] = []
    chapters: list[dict] = []
    snapshots: list[str] = []
    recorded_indices: set[int] = set()
    context = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=chromium_executable(),
                headless=not args.headed,
                args=["--autoplay-policy=no-user-gesture-required", "--hide-scrollbars"],
            )
            context = browser.new_context(
                viewport={"width": args.width, "height": args.height},
                screen={"width": args.width, "height": args.height},
                device_scale_factor=1,
                color_scheme="dark" if args.theme == "original" else args.theme,
                reduced_motion="no-preference",
                locale="fr-FR",
                timezone_id="Europe/Paris",
                record_video_dir=str(scratch),
                record_video_size={"width": args.width, "height": args.height},
            )
            context.add_init_script("localStorage.setItem('elia-native-theme-v3', '" + args.theme + "');")
            video_origin = time.monotonic()
            page = context.new_page()
            video = page.video
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.evaluate("document.fonts.ready")
            page.locator("#cands .cand").first.wait_for(timeout=30000)
            page.wait_for_function("typeof window.ELIA_TOUR?.start === 'function'", timeout=30000)
            page.wait_for_timeout(600)
            page.mouse.move(args.width - 8, args.height - 8)
            definitions = page.evaluate("window.ELIA_TOUR.chapters")
            capture_indices = set(range(len(definitions)))
            nominal_starts = [sum(c["duration"] for c in definitions[:i]) for i in range(len(definitions))]
            page.evaluate("""() => {
                const marker = document.createElement('div');
                marker.id = '__elia_recording_sync';
                marker.style.cssText = 'position:fixed;top:0;left:0;width:16px;height:16px;background:#00ff00;z-index:2147483647;pointer-events:none';
                document.body.append(marker);
            }""")
            page.wait_for_timeout(400)
            browser_origin = page.evaluate(
                """theme => {
                    const origin = performance.now();
                    window.ELIA_TOUR.start({recording:true, theme});
                    document.getElementById('__elia_recording_sync').remove();
                    return origin;
                }""", args.theme
            )
            tour_origin = time.monotonic()
            trim_start = tour_origin - video_origin
            print(f"Recording {args.width}x{args.height}, theme={args.theme}, tour started", flush=True)

            index = None
            index_origin = tour_origin
            state = {}
            while True:
                page.wait_for_timeout(250)
                observation = page.evaluate("({state:window.ELIA_TOUR.state, now:performance.now()})")
                state = observation["state"]
                now = time.monotonic()
                if state.get("index") != index:
                    index = state.get("index")
                    index_origin = now
                    elapsed_in_chapter = max(0, state["elapsed"] - nominal_starts[index])
                    chapter_start = max(0, (observation["now"] - browser_origin) / 1000 - elapsed_in_chapter)
                    entry = {"index": index, "seconds": round(chapter_start, 3)}
                    chapters.append(entry)
                    print(f"Chapter {index}: {entry['seconds']}s", flush=True)
                if (index in capture_indices and index not in recorded_indices
                        and now - index_origin >= 5):
                    screenshot = captures / f"chapitre-{index + 1:02d}.png"
                    page.screenshot(path=str(screenshot))
                    snapshots.append(str(screenshot.relative_to(ROOT)))
                    recorded_indices.add(index)
                if state.get("complete"):
                    break
                if now - tour_origin > args.timeout:
                    raise TimeoutError(f"Tour did not finish within {args.timeout}s: {state}")
            page.wait_for_timeout(args.tail * 1000)
            tour_duration = time.monotonic() - tour_origin
            closing = captures / "conclusion.png"
            page.screenshot(path=str(closing))
            snapshots.append(str(closing.relative_to(ROOT)))
            context.close()
            context = None
            assert video is not None
            raw_video = Path(video.path())
            browser.close()
    finally:
        if context is not None:
            context.close()
        if server is not None:
            server.shutdown()
            server.server_close()

    approximate_trim = trim_start
    trim_start = calibrated_trim(ffmpeg, raw_video, approximate_trim)
    subtitle_path = output.with_suffix(".srt")
    subtitle_cues = write_subtitles(subtitle_path, definitions, chapters, tour_duration)
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "warning", "-y", "-i", str(raw_video),
         "-ss", f"{trim_start:.3f}", "-t", f"{tour_duration:.3f}",
         "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)],
        check=True,
    )
    probe = json.loads(subprocess.check_output(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=codec_name,width,height,avg_frame_rate:format=duration,size",
         "-of", "json", str(output)], text=True, encoding="utf-8"
    ))
    stream = probe["streams"][0]
    if (stream["width"], stream["height"]) != (args.width, args.height):
        raise RuntimeError(f"Unexpected encoded video dimensions: {stream}")
    first_frame = captures / "video-premiere-image.png"
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(output),
         "-frames:v", "1", str(first_frame)], check=True,
    )
    first_corner = subprocess.check_output(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(output),
         "-frames:v", "1", "-vf", "crop=12:12:2:2,scale=1:1:flags=area,format=rgb24",
         "-f", "rawvideo", "pipe:1"]
    )
    marker_absent = not (first_corner[0] < 65 and first_corner[1] > 200 and first_corner[2] < 65)
    if not marker_absent:
        raise RuntimeError("Calibration marker remains in the first exported video frame.")
    metadata = {"url": url, "theme": args.theme, "viewport": [args.width, args.height],
                "tour_seconds": round(tour_duration, 3), "trim_start": round(trim_start, 3),
                "trim_calibration": "first frame after sync marker", "subtitle_cues": subtitle_cues,
                "subtitles": str(subtitle_path.relative_to(ROOT)),
                "first_frame_preview": str(first_frame.relative_to(ROOT)),
                "first_frame_rgb": list(first_corner), "first_frame_marker_absent": marker_absent,
                "chapters": chapters, "screenshots": snapshots, "browser_errors": errors,
                "video": str(output.relative_to(ROOT)), "media": probe}
    metadata_path = output.with_suffix(".json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=True, indent=2), flush=True)
    if errors:
        raise RuntimeError("Browser reported JavaScript errors; see recording metadata.")


if __name__ == "__main__":
    main()
