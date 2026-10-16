"""Extend the zip's scrollytelling to the other scenes, in the page's own components (pin, steps, cards).
- step trigger by scroll position (viewport centre) instead of an IntersectionObserver rootMargin, which browsers
  ignore inside embedded (cross-origin) frames such as the artifact viewer;
- scene 04 becomes a pinned scene: three steps drive the map (today, last 31 days, then a tall step whose scroll
  position scrubs the public-sector series month by month);
- scene 03: the France bars fill one after another with the scroll;
- scene 02: the sparklines draw themselves with the scroll;
- scene 05: a time cursor sweeps the "premières apparitions" timeline and each new title lights up when it is passed;
- hero: slow parallax of the background veil.
Idempotent: running it twice leaves the page unchanged. Usage: python tools/add_scroll_story.py (from website/)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'index.html'
html = P.read_text(encoding='utf-8')
if 'id="steps-carte"' in html:
    print('scroll story already present'); raise SystemExit(0)

def sub_once(old, new, text, label):
    if old not in text: raise SystemExit('pattern not found: ' + label)
    return text.replace(old, new, 1)

# ---------------------------------------------------------------- CSS
CSS = r"""
/* récit au défilement étendu : carte épinglée pilotée par le défilement, barres, frises et courbes qui se dessinent */
.scrolly-carte{position:relative;background:var(--night)}
.pin-carte{padding:8vh clamp(18px,4vw,52px) 5vh}
.pin-carte .sc-carte{display:flex;flex-direction:column;min-height:0}
.pin-carte .carte-wrap{grid-template-columns:minmax(0,calc((100vh - 380px) / .92)) 290px;grid-template-columns:minmax(0,calc((100svh - 380px) / .92)) 290px;justify-content:start}
.steps-carte .step{justify-content:flex-end;align-items:flex-end;padding-bottom:14vh}
.steps-carte .step.step-scrub{min-height:340vh;min-height:340svh;align-items:flex-start;padding-top:0;padding-bottom:0}
.steps-carte .step.step-scrub .card{position:sticky;top:calc(86vh - 160px);top:calc(86svh - 160px)}
@media (max-width:860px){
  .pin-carte .map-rail,.pin-carte .src-note,.pin-carte .map-foot{display:none}
  .pin-carte .carte-wrap{grid-template-columns:minmax(0,1fr)}
  .steps-carte .step{justify-content:center}
}
#frbars.scrub .frbar .trk i{transition:width .22s linear}
#appear g.ap{opacity:.13;transition:opacity .35s}
#appear g.ap.on{opacity:1}
#appear g.ap-cursor{transition:opacity .3s}
@media (prefers-reduced-motion: reduce){
  #appear g.ap{opacity:1;transition:none}
  #appear g.ap-cursor{display:none}
  #frbars.scrub .frbar .trk i{transition:none}
}
"""
html = sub_once('</style>', CSS + '</style>', html, 'first </style>')

# ---------------------------------------------------------------- scene 04 markup: pin + steps
m = re.search(r'(  <!-- 04 · carte -->\n)  <section class="sc sc-carte" id="carte">([\s\S]*?)\n  </section>\n', html)
if not m: raise SystemExit('map section not found')
inner = m.group(2)
new_map = ('  <!-- 04 · carte, épinglée : le défilement pilote la carte -->\n'
           '  <div class="scrolly scrolly-carte" id="carte-recit">\n'
           '    <div class="pin pin-carte">\n'
           '  <section class="sc-carte" id="carte">' + inner + '\n  </section>\n'
           '    </div>\n'
           '    <div class="steps steps-carte" id="steps-carte">\n'
           '      <div class="step" data-c="0"><div class="card"><span class="y">Aujourd’hui</span><b id="cs-idf">—</b> des offres IA en ligne sont publiées en Île-de-France.</div></div>\n'
           '      <div class="step" data-c="1"><div class="card"><span class="y">Depuis 31 jours</span>Les offres récentes dessinent la même carte : <b id="cs-rec">—</b> ont moins d’un mois.</div></div>\n'
           '      <div class="step step-scrub" data-c="2"><div class="card"><span class="y">Secteur public, 2022 → 2026</span>Continuez à défiler : la carte rejoue <b>mois par mois</b> les offres IA de la fonction publique.</div></div>\n'
           '    </div>\n'
           '  </div>\n')
html = html[:m.start()] + new_map + html[m.end():]

# ---------------------------------------------------------------- main script: step trigger moved to the scroll engine
old_io = """const steps = [...document.querySelectorAll('.step')];
const io = new IntersectionObserver(es => {
  for (const e of es){
    e.target.classList.toggle('is-on', e.isIntersecting);
    if (e.isIntersecting) setState(Number(e.target.dataset.s));
  }
}, {rootMargin: '-42% 0px -42% 0px'});
steps.forEach(s => io.observe(s));"""
html = sub_once(old_io, "/* étapes du récit : déclenchées par la position de défilement, voir le moteur plus bas (fonctionne aussi dans un cadre intégré) */", html, 'steps observer')

# discovery timeline: tag the nodes with their x and add a time cursor
old_node = """  const node = svgA.append('g').selectAll('g').data(placed).join('g')
    .attr('transform', p => `translate(${p.cx},${yl(p.lane)})`)"""
new_node = """  const node = svgA.append('g').selectAll('g').data(placed).join('g')
    .attr('class', 'ap').attr('data-cx', p => p.cx.toFixed(1))
    .attr('transform', p => `translate(${p.cx},${yl(p.lane)})`)"""
html = sub_once(old_node, new_node, html, 'appear nodes')
old_title = """    (p.known ? ', déjà en taxonomie' : ', inédit'));"""
new_title = """    (p.known ? ', déjà en taxonomie' : ', inédit'));
  const cur = svgA.append('g').attr('class', 'ap-cursor').attr('pointer-events', 'none').style('opacity', 0);
  cur.append('line').attr('y1', 10).attr('y2', H - 22).attr('stroke', 'var(--rose)').attr('stroke-width', 1.2);
  cur.append('text').attr('x', 5).attr('y', H - 27).attr('fill', 'var(--rose)').attr('font-size', 10.5).attr('font-weight', 700).attr('font-family', FONT);
  svgA.node().__ap = { x0: x.range()[0], x1: x.range()[1], d0: +x.domain()[0], d1: +x.domain()[1] };"""
html = sub_once(old_title, new_title, html, 'appear titles')

# hooks for the scroll engine (inside the page closure, next to the tour hooks)
old_boot = "/* ---------- boot ---------- */"
hooks = """window.ELIA_STORY = {
  panorama: n => setState(n),
  carte(n){
    const m = ['total', 'recent', 'monthly'][n] || 'total';
    if (m === 'monthly' && !CSPM) return;
    if (mapMetric === m) return;
    mapMetric = m; stopPlay();
    if (mapMetricEl) mapMetricEl.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.m === m)));
    const monthly = isMonthly();
    $('#timectl').hidden = !monthly; $('#map-month').hidden = !monthly;
    if (monthly){ $('#month-slider').max = String(CSPM.months.length - 1); if (monthIdx < 0) monthIdx = 0; }
    renderCarte();
    if (monthly) setMonth(monthIdx);
  },
  carteMonth(p){
    if (!CSPM || !isMonthly()) return;
    const i = Math.round(Math.max(0, Math.min(1, p)) * (CSPM.months.length - 1));
    if (i !== monthIdx) setMonth(i);
  },
  regions: () => regionsData(),
};

/* ---------- boot ---------- */"""
html = sub_once(old_boot, hooks, html, 'boot marker')

# ---------------------------------------------------------------- scroll engine (after the page script, before the tour script)
ENGINE = r"""<script>
/* Moteur de défilement : une seule boucle rAF lit la position des étapes et des figures et pilote les scènes. */
(function(){
  'use strict';
  const S = window.ELIA_STORY; if (!S) return;
  const $ = s => document.querySelector(s);
  const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp = v => Math.max(0, Math.min(1, v));
  const fmtM = new Intl.DateTimeFormat('fr-FR', {month:'short', year:'numeric'});
  const pct0 = v => Math.round(v).toLocaleString('fr-FR') + ' %';
  /* textes des étapes de la carte, depuis les données */
  try{
    const R = (S.regions() || []).filter(r => !['01','02','03','04','06'].includes(r.code));
    const tot = R.reduce((s, r) => s + r.total, 0), rec = R.reduce((s, r) => s + r.recent, 0);
    const idf = R.find(r => r.code === '11');
    if (tot && idf) $('#cs-idf').textContent = pct0(idf.total / tot * 100);
    if (tot) $('#cs-rec').textContent = pct0(rec / tot * 100);
  }catch(_e){}
  const stories = [
    {steps:[...document.querySelectorAll('#steps .step')], key:'s', on:n => S.panorama(n), cur:-1},
    {steps:[...document.querySelectorAll('#steps-carte .step')], key:'c', on:n => S.carte(n), cur:-1},
  ];
  const fb = $('#frbars'); if (fb) fb.classList.add('scrub');
  function frame(){
    const H = innerHeight, mid = H * 0.5;
    for (const st of stories){
      let act = -1;
      st.steps.forEach((el, i) => { const r = el.getBoundingClientRect(); if (r.top <= mid && r.bottom >= mid) act = i; });
      st.steps.forEach((el, i) => el.classList.toggle('is-on', i === act));
      if (act >= 0 && act !== st.cur){ st.cur = act; st.on(Number(st.steps[act].dataset[st.key])); }
    }
    /* carte : la dernière étape fait défiler les mois */
    const sc = $('#steps-carte .step-scrub');
    if (sc && stories[1].cur === 2){ const r = sc.getBoundingClientRect(); S.carteMonth((mid - r.top) / Math.max(1, r.height - mid)); }
    /* France : les barres se remplissent l'une après l'autre */
    if (fb){
      const r = fb.getBoundingClientRect(), p = RM ? 1 : clamp((H * 0.92 - r.top) / (r.height * 0.7 + H * 0.15));
      const bars = fb.querySelectorAll('.frbar .trk i'), n = bars.length;
      bars.forEach((el, i) => { const w = parseFloat(el.style.getPropertyValue('--w')) || 0; const f = clamp((p * (n + 3) - i) / 3); el.style.width = (w * f).toFixed(2) + '%'; });
    }
    /* familles en essor : les courbes se dessinent */
    const mi = $('#minis');
    if (mi){
      const r = mi.getBoundingClientRect(), p = RM ? 1 : clamp((H * 0.95 - r.top) / (r.height + H * 0.3));
      const ms = mi.querySelectorAll('.mini'), n = ms.length;
      ms.forEach((m, i) => {
        const paths = m.querySelectorAll('svg path'); if (paths.length < 2) return;
        const line = paths[1], f = clamp((p * (n + 2) - i) / 2.2);
        if (!line.__L){ line.__L = line.getTotalLength() || 1; line.style.strokeDasharray = line.__L; }
        line.style.strokeDashoffset = (line.__L * (1 - f)).toFixed(1); paths[0].style.opacity = f;
        const dot = m.querySelector('svg circle'); if (dot) dot.style.opacity = f > .97 ? 1 : 0;
      });
    }
    /* découverte : un curseur temporel balaie la frise */
    const ap = $('#appear');
    if (ap && ap.__ap){
      const r = ap.getBoundingClientRect(), g = ap.__ap, p = RM ? 1 : clamp((H * 0.85 - r.top) / (r.height + H * 0.3));
      const cx = g.x0 + p * (g.x1 - g.x0);
      ap.querySelectorAll('g.ap').forEach(nd => nd.classList.toggle('on', +nd.dataset.cx <= cx + 0.5));
      const c = ap.querySelector('g.ap-cursor');
      if (c){ c.setAttribute('transform', 'translate(' + cx.toFixed(1) + ',0)'); c.style.opacity = (p > 0 && p < 1) ? 1 : 0; c.querySelector('text').textContent = fmtM.format(new Date(g.d0 + p * (g.d1 - g.d0))); }
    }
    /* ouverture : léger parallaxe du voile */
    const veil = $('#veil');
    if (veil && !RM && scrollY < H * 1.3) veil.style.transform = 'translateY(' + (scrollY * 0.32).toFixed(1) + 'px)';
  }
  let raf = 0;
  const req = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; frame(); }); };
  addEventListener('scroll', req, {passive:true}); addEventListener('resize', req);
  window.ELIA_SCROLL_FRAME = frame; req();
})();
</script>
"""
# insert just before the tour script (second <script> block after d3/data): find the tour IIFE start
tour_marker = "<script>\n(function(){\n  'use strict';\n  const $=s=>document.querySelector(s), O=window.ELIA_OUTCOMES;"
html = sub_once(tour_marker, ENGINE + tour_marker, html, 'tour script start')
P.write_text(html, encoding='utf-8')
print('scroll story added:', len(html), 'bytes')
