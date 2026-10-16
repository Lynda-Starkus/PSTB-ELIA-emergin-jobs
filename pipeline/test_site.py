"""Load the website in headless Chromium, collect console errors, take screenshots of each section, and produce website/artifact.html (body-only copy for the Claude artifact preview)."""
import sys, os, re
from playwright.sync_api import sync_playwright
root = sys.argv[1]; site = os.path.join(root, 'website'); shots = os.path.join(site, '_shots'); os.makedirs(shots, exist_ok=True)
html = open(os.path.join(site, 'index.html'), encoding='utf-8').read()
# artifact copy: strip the document skeleton (the artifact host adds its own), keep title/meta/link/style/scripts
inner = re.sub(r'^.*?<head>', '', html, flags=re.S); inner = inner.replace('</head>', '').replace('<body>', '').replace('</body>', '').replace('</html>', '')
inner = re.sub(r'<meta name="viewport"[^>]*>', '', inner); inner = re.sub(r'<meta charset[^>]*>', '', inner)
open(os.path.join(site, 'artifact.html'), 'w', encoding='utf-8').write(inner.strip() + '\n')
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1360, 'height': 900}, device_scale_factor=1)
    pg.on('console', lambda m: errors.append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None); pg.on('pageerror', lambda e: errors.append('pageerror: ' + str(e)))
    pg.goto('file:///' + os.path.join(site, 'index.html').replace('\\', '/')); pg.wait_for_timeout(2500)
    for sec in ['serie', 'naissance', 'indice', 'bourse', 'france', 'competences', 'salaires', 'public', 'explorateur', 'barometre', 'methode']:
        pg.evaluate(f"document.getElementById('{sec}').scrollIntoView()"); pg.wait_for_timeout(600); pg.screenshot(path=os.path.join(shots, f'{sec}.png'))
    pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(300); pg.screenshot(path=os.path.join(shots, 'hero.png'))
    pg.set_viewport_size({'width': 400, 'height': 800}); pg.wait_for_timeout(800); pg.screenshot(path=os.path.join(shots, 'mobile.png'))
    sw = pg.evaluate("document.documentElement.scrollWidth"); print('mobile scrollWidth', sw)
    b.close()
print('console issues:', len(errors)); [print(' ', e[:300]) for e in errors[:20]]
