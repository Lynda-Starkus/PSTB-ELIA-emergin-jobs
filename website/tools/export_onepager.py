"""Export the meeting slide and verify readable, stable presentation geometry."""
from pathlib import Path
import json
import os
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache' / 'onepager'
CACHE.mkdir(parents=True, exist_ok=True)
browser_cache = Path(os.environ['LOCALAPPDATA']) / 'ms-playwright'
executables = list(browser_cache.glob('chromium_headless_shell-*/**/chrome-headless-shell.exe'))
if not executables:
    executables = list(browser_cache.glob('chromium-*/**/chrome.exe'))
if not executables:
    raise RuntimeError('No installed Chromium found for visual verification.')

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=str(sorted(executables)[-1]))
    page = browser.new_page(viewport={'width':1600,'height':900}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('http://**/*', lambda route: route.abort())
    page.route('https://**/*', lambda route: route.abort())
    page.goto((ROOT / 'onepager.html').as_uri())
    page.evaluate('document.fonts.ready')
    page.wait_for_timeout(1600)
    assert page.evaluate("document.querySelector('#brand-logo').naturalWidth > 0")
    assert page.evaluate('''document.fonts.check('500 24px "Bricolage Grotesque"') && document.fonts.check('400 24px "Hanken Grotesk"')''')
    assert page.locator('dialog').count() == 0
    page.locator('#slide').screenshot(path=str(ROOT / 'onepager.png'))
    page.emulate_media(media='print')
    page.pdf(path=str(ROOT / 'onepager.pdf'), print_background=True, prefer_css_page_size=True)
    pdf = PdfReader(ROOT / 'onepager.pdf')
    assert len(pdf.pages) == 1, f'PDF has {len(pdf.pages)} pages'
    pdf_text = pdf.pages[0].extract_text()
    for phrase in ('Catalogue', 'Alumni', 'VivaTech', 'Relais'):
        assert phrase in pdf_text, f'Missing PDF content: {phrase}'
    page.emulate_media(media='screen')

    # Selecting a topic must preserve all content sizes and positions.
    geometry_script = '''() => [...document.querySelectorAll('#slide, #slide section, #slide p, #slide h1, #slide h2, #slide h3')].map(e => {
      const r=e.getBoundingClientRect(); return [r.x,r.y,r.width,r.height];
    })'''
    initial_geometry = page.evaluate(geometry_script)
    for key, expected in (('1','scope'),('2','results'),('3','survey')):
        page.keyboard.press(key)
        assert page.locator('.discussion.current').get_attribute('id') == expected
        assert page.evaluate(geometry_script) == initial_geometry, 'Topic selection resized or moved content'
    page.keyboard.press('Escape')
    assert page.locator('.discussion.current').count() == 0
    layouts = []
    for width,height in ((1366,768),(1600,900),(1920,1080),(1024,768),(390,844)):
        page.set_viewport_size({'width':width,'height':height})
        page.wait_for_timeout(60)
        metrics = page.evaluate('''() => {
          const sheet=document.querySelector('.sheet'),r=sheet.getBoundingClientRect();
          return {width:innerWidth,height:innerHeight,pageHeight:document.documentElement.scrollHeight,
            pageWidth:document.documentElement.scrollWidth,sheetBottom:r.bottom,
            transform:getComputedStyle(sheet).transform,
            textSize:parseFloat(getComputedStyle(document.querySelector('.rationale')).fontSize),
            detailSize:parseFloat(getComputedStyle(document.querySelector('.dimensions')).fontSize)};
        }''')
        assert metrics['pageWidth'] <= width, metrics
        assert metrics['transform'] == 'none', metrics
        if width >= 1366:
            assert metrics['pageHeight'] <= height, metrics
            assert metrics['sheetBottom'] <= height - 30, metrics
            assert metrics['textSize'] >= 24 and metrics['detailSize'] >= 22, metrics
            page.evaluate("document.body.classList.add('presenting')")
            assert page.evaluate('document.documentElement.scrollHeight <= innerHeight'), f'Fullscreen layout clipped at {width}'
            page.evaluate("document.body.classList.remove('presenting')")
        page.screenshot(path=str(CACHE / f'revised-{width}.png'),full_page=True)
        layouts.append(metrics)
    page.emulate_media(reduced_motion='reduce')
    page.wait_for_function("document.body.classList.contains('quiet')")
    assert not errors, errors
    browser.close()

print(json.dumps({'offline':True,'pdf_pages':1,'browser_errors':errors,'no_topic_zoom':True,'layouts':layouts,'artifacts':['onepager.html','onepager.pdf','onepager.png']},ensure_ascii=False,indent=2))
