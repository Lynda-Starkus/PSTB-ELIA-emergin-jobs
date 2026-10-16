"""Headless check of website/index.html: console errors, hero counters, scene screenshots (desktop + mobile), tour chapters count.
Usage: python tools/test_page.py   (from website/; needs PLAYWRIGHT_BROWSERS_PATH)"""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]; shots = ROOT / '_shots'; shots.mkdir(exist_ok=True)
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1440, 'height': 900}, device_scale_factor=1)
    pg.on('console', lambda m: errors.append(f'{m.type}: {m.text[:200]}') if m.type in ('error', 'warning') else None); pg.on('pageerror', lambda e: errors.append('pageerror: ' + str(e)[:300]))
    pg.goto((ROOT / 'index.html').as_uri()); pg.wait_for_timeout(2500)
    nums = pg.evaluate("() => ({corpus: document.getElementById('n-corpus').textContent, ads: document.getElementById('n-ads').textContent, adz: document.getElementById('n-adz').textContent, fr: document.getElementById('n-fr').textContent, boot: document.getElementById('boot-error').textContent, chapters: (window.ELIA_TOUR && window.ELIA_TOUR.chapters.length) || 0, foot: document.getElementById('foot-stamp').textContent})")
    print('hero:', json.dumps(nums, ensure_ascii=False))
    pg.screenshot(path=str(shots / '00_hero.png'))
    for i, sel in enumerate(['.step[data-s="1"]', '.step[data-s="2"]', '.step[data-s="3"]', '#accel', '#france', '#carte', '#decouverte', '#intitules', '#methode']):
        pg.evaluate(f"document.querySelector('{sel}').scrollIntoView({{block: 'center'}})"); pg.wait_for_timeout(1400)
        pg.screenshot(path=str(shots / f'{i + 1:02d}_{sel.strip("#.").split("[")[0]}.png'))
    # France section numbers and map rail
    fr = pg.evaluate("() => ({total: document.getElementById('fr-total').textContent, sub: document.getElementById('fr-sub').textContent, bars: [...document.querySelectorAll('#frbars .frbar .lb')].slice(0,6).map(e => e.textContent), carte: document.getElementById('carte-sub').textContent, mine: document.getElementById('mine-sub').textContent, cands: [...document.querySelectorAll('#cands .cand .lb')].slice(0,5).map(e => e.textContent), vols: [...document.querySelectorAll('#vols .vol .n')].map(e => e.textContent)})")
    print('france/map/mine:', json.dumps(fr, ensure_ascii=False))
    # tour: start and step through 3 chapters
    pg.evaluate("window.scrollTo(0,0)"); pg.click('#tour-launch'); pg.wait_for_timeout(2500); pg.screenshot(path=str(shots / '10_tour.png'))
    for k in range(3): pg.click('#tour-next'); pg.wait_for_timeout(1800)
    pg.screenshot(path=str(shots / '11_tour_step4.png')); pg.click('#tour-stop'); pg.wait_for_timeout(500)
    pg.set_viewport_size({'width': 390, 'height': 844}); pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(800); pg.screenshot(path=str(shots / '12_mobile.png'))
    print('mobile scrollWidth', pg.evaluate('document.documentElement.scrollWidth'))
    b.close()
print('console issues:', len(errors)); [print(' ', e) for e in errors[:15]]
