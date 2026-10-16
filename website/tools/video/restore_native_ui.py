"""Restore the committed Claude interface, adding only tour and theme support."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent

def main():
    html=subprocess.check_output(['git','show','f99a007:index.html'],cwd=ROOT).decode('utf-8')
    css=(HERE/'native_tour.css').read_text(encoding='utf-8')
    javascript=(HERE/'native_tour.js').read_text(encoding='utf-8')
    html=html.replace('</style>',css+'\n</style>',1)
    controls='''<div class="elia-dock"><button id="theme-toggle" type="button"></button><button id="tour-launch" type="button">Visite guid&eacute;e</button></div>
<div id="tour-overlay" class="tour-overlay" hidden>
  <div class="tour-caption" id="tour-caption" aria-live="polite"><h2 id="tour-heading"></h2><p id="tour-body"></p><p id="tour-source"></p></div>
  <div class="tour-controls"><span class="tour-time" id="tour-time"></span><button id="tour-prev" aria-label="Pr&eacute;c&eacute;dent">&#8592;</button><button id="tour-pause">Pause</button><button id="tour-next" aria-label="Suivant">&#8594;</button><button id="tour-stop">Fermer</button></div>
  <div id="tour-cursor" aria-hidden="true"><i></i><svg viewBox="0 0 25 32"><path d="M2 2 L2 26 L8 21 L12 30 L17 27 L13 19 L23 19 Z" fill="white" stroke="#17121f" stroke-width="1.8"/></svg></div>
</div>'''
    html=html.replace('<div id="boot-error"></div>','<div id="boot-error"></div>\n'+controls,1)
    html=html.replace("const c = el('button', 'cardt');","const c = el('button', 'cardt');\n    c.dataset.title = t.id;",1)
    html=html.replace("const b = el('button', 'cand');","const b = el('button', 'cand');\n    b.dataset.group = c.label;",1)
    html=html.replace("const b = el('button', 'frbar');","const b = el('button', 'frbar');\n    b.dataset.title = t.id;",1)
    html=html.replace('function renderBoard(){','let tourTitleIds=null, tourBoardSnapshot=null;\nfunction renderBoard(){',1)
    html=html.replace('let rows = TITLES.filter(t => {','let rows = TITLES.filter(t => {\n    if(tourTitleIds && !tourTitleIds.includes(t.id)) return false;',1)
    html=html.replace("  $('#tbl-count').textContent = rows.length", "  if(tourTitleIds) rows.sort((a,b)=>tourTitleIds.indexOf(a.id)-tourTitleIds.indexOf(b.id));\n  $('#tbl-count').textContent = rows.length",1)
    bridge='''window.ELIA_NATIVE={
  start(){tourBoardSnapshot={...B,hiddenCats:new Set(B.hiddenCats)};},
  select(ids,sort='roles'){
    tourTitleIds=ids;B.q='';B.dom='';B.lvl='';B.sort=sort;B.hiddenCats.clear();
    document.querySelector('#q').value='';document.querySelector('#f-domain').value='';document.querySelector('#f-level').value='';document.querySelector('#sort-sel').value=sort;
    renderEtatChips();renderBoard();
  },
  restore(){
    tourTitleIds=null;if(tourBoardSnapshot){Object.assign(B,tourBoardSnapshot);tourBoardSnapshot=null;}
    document.querySelector('#q').value=B.q;document.querySelector('#f-domain').value=B.dom;document.querySelector('#f-level').value=B.lvl;document.querySelector('#sort-sel').value=B.sort;
    renderEtatChips();renderBoard();
  }
};'''
    html=html.replace('/* ---------- boot ---------- */',bridge+'\n\n/* ---------- boot ---------- */',1)
    html=html.replace("'.sc-mine', '.sc-board'", "'.sc-mine'",1)
    html=html.replace('/* ---------- boot ---------- */', "new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting)e.target.classList.add('seen');}),{threshold:0}).observe(document.querySelector('.sc-board'));\n\n/* ---------- boot ---------- */",1)
    html=html.replace('<!-- ELIA:CONTENT-END -->','<script>\n'+javascript+'\n</script>\n<!-- ELIA:CONTENT-END -->',1)
    assert 'sc-outcome' not in html and 'market-grid' not in html
    (ROOT/'index.html').write_text(html,encoding='utf-8')
    print('Restored Claude UI from f99a007; added isolated tour and theme controls.')

if __name__=='__main__':
    main()
