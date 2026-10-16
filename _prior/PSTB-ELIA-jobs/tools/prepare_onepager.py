"""Embed the existing brand mark and Google Fonts for an offline HTML slide."""
from pathlib import Path
import base64
import re
import urllib.request
from shutil import copy2

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "onepager"
CACHE.mkdir(parents=True, exist_ok=True)
FONT_URL = "https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800&family=Hanken+Grotesk:wght@400..700&display=swap"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=30).read()

css_path = CACHE / "fonts-modern.css"
if not css_path.exists():
    css_path.write_bytes(fetch(FONT_URL))
css = css_path.read_text(encoding="utf-8")
blocks = re.findall(r"(?:/\* ([^*]+) \*/\s*)?(@font-face\s*\{[^}]+\})", css)
embedded = []
for subset, block in blocks:
    if subset.strip() not in ("", "latin", "latin-ext"):
        continue
    url = re.search(r"src:\s*url\(([^)]+)\)", block).group(1)
    font_path = CACHE / url.rsplit("/", 1)[-1]
    if not font_path.exists():
        font_path.write_bytes(fetch(url))
    mime = "font/woff2" if url.endswith(".woff2") else "font/ttf"
    data_url = "data:" + mime + ";base64," + base64.b64encode(font_path.read_bytes()).decode("ascii")
    embedded.append(block.replace(url, data_url).replace("font-display: swap", "font-display: block"))

html_path = ROOT / "onepager.html"
template_path = ROOT / "tools" / "onepager.template.html"
if template_path.exists():
    archive = CACHE / "previous"
    archive.mkdir(exist_ok=True)
    for name in ("onepager.html", "onepager.pdf", "onepager.png"):
        previous_file = ROOT / name
        if previous_file.exists() and not (archive / name).exists():
            copy2(previous_file, archive / name)
    html = template_path.read_text(encoding="utf-8")
else:
    html = html_path.read_text(encoding="utf-8")
html = re.sub(r'<style id="embedded-fonts">[\s\S]*?</style>', '<style id="embedded-fonts">\n' + "\n".join(embedded) + "\n</style>", html, count=1)
logo = (ROOT / "assets" / "logo-pstb-blanc.svg").read_text(encoding="utf-8")
# The source SVG was copied from inline HTML and has an unescaped ampersand.
logo = logo.replace('aria-label="Paris School of Technology & Business"', 'aria-label="Paris School of Technology &amp; Business"')
logo_url = "data:image/svg+xml;base64," + base64.b64encode(logo.encode("utf-8")).decode("ascii")
html = html.replace('src="assets/logo-pstb-blanc.svg"', 'src="' + logo_url + '"')
html_path.write_text(html, encoding="utf-8")
print(f"Offline slide ready: {len(embedded)} font faces, embedded logo, {html_path.stat().st_size:,} bytes.")
