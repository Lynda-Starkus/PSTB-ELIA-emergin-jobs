"""Package the observatory and its guided tour as one offline HTML document."""
from pathlib import Path
import base64
import re
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "deliverables"
CACHE = ROOT / ".cache" / "video" / "assets"
OUTPUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

# Keep the Google Fonts subset boundaries. Without these, the last latin-ext
# face replaces the latin face for the whole Unicode space and French letters
# fall back to a different font even though the embedded latin font has them.
FONT_RANGES = {
    "latin": "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
    "latin-ext": "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C4,U+2113,U+2C60-2C7F,U+A720-A7FF",
}


def download(url, destination):
    if not destination.exists():
        with urlopen(url, timeout=40) as response:
            destination.write_bytes(response.read())
    return destination.read_bytes()


def embedded_font_css():
    faces = []
    fonts = [
        ("Bricolage Grotesque", "300 800", "latin", "bricolagegrotesque/v9/3y9K6as8bTXq_nANBjzKo3IeZx8z6up5BeSl9D4dj_x9PpZBMlGIInE.woff2"),
        ("Bricolage Grotesque", "300 800", "latin-ext", "bricolagegrotesque/v9/3y9K6as8bTXq_nANBjzKo3IeZx8z6up5BeSl9D4dj_x9PpZBMlGGInHEVA.woff2"),
        ("Hanken Grotesk", "400 700", "latin", "hankengrotesk/v12/ieVn2YZDLWuGJpnzaiwFXS9tYtpd59A.woff2"),
        ("Hanken Grotesk", "400 700", "latin-ext", "hankengrotesk/v12/ieVn2YZDLWuGJpnzaiwFXS9tYtpT59CjCQ.woff2"),
    ]
    for family, weights, subset, suffix in fonts:
        filename = suffix.rsplit("/", 1)[-1]
        previous = ROOT / ".cache" / "onepager" / filename
        binary = previous.read_bytes() if previous.exists() else download("https://fonts.gstatic.com/s/" + suffix, CACHE / filename)
        encoded = base64.b64encode(binary).decode("ascii")
        faces.append("@font-face{font-family:'" + family + "';font-style:normal;font-weight:" + weights +
                     ";font-display:swap;src:url(data:font/woff2;base64," + encoded + ") format('woff2');unicode-range:" +
                     FONT_RANGES[subset] + "}")
    return "\n".join(faces)


def main():
    # Strict UTF-8 reads fail on damaged input instead of silently dropping
    # accents. utf-8-sig also accepts and strips an optional editor-written BOM.
    html = (ROOT / "index.html").read_text(encoding="utf-8-sig")
    if "\ufffd" in html:
        raise ValueError("The source HTML contains Unicode replacement characters")
    if not re.search(r'<meta\s+charset=["\']utf-8["\']', html[:1024], re.I):
        raise ValueError("The source HTML must declare UTF-8 within its first 1024 bytes")
    d3_url = "https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"
    d3 = download(d3_url, CACHE / "d3-7.9.0.min.js").decode("utf-8")
    html = html.replace('<script src="' + d3_url + '"></script>', "<script>" + d3 + "</script>")
    data = (ROOT / "data" / "data.js").read_text(encoding="utf-8-sig")
    html = html.replace('<script src="data/data.js"></script>', "<script>" + data.replace("</script", r"<\/script") + "</script>")
    html = re.sub(r'<link[^>]+href="https://fonts\.[^"]+"[^>]*>\s*', "", html)
    html = html.replace("<style>", "<style>\n" + embedded_font_css() + "\n", 1)
    path = OUTPUT / "elia-scrollytelling.html"
    path.write_text(html, encoding="utf-8")
    # Assert a byte-preserving round trip for every accented source label.
    assert path.read_text(encoding="utf-8") == html
    print(f"Offline HTML: {path} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
