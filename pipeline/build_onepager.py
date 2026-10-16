# -*- coding: utf-8 -*-
"""One-pager presse (A4 portrait, français) dans la langue visuelle du projet d'origine (tools/onepager.template.html du zip) :
feuille papier, Bricolage Grotesque + Hanken Grotesk, filets, colonne d'étiquettes, schémas SVG au trait fin.
Sortie : dissemination/onepager/onepager.html + .pdf + .png (Playwright)."""
import sys, os, json, base64, math, numpy as np, pandas as pd
root = sys.argv[1]; res = os.path.join(root, 'data-lake', 'lake', 'results'); lake = os.path.join(root, 'data-lake', 'lake'); out = os.path.join(root, 'dissemination', 'onepager'); os.makedirs(out, exist_ok=True)
MD = lambda m: pd.Timestamp(m + '-01')
def fr(n, d=0):
    s = f'{n:,.{d}f}'.replace(',', ' ').replace('.', ',')
    return s
def pc(v, d=1): return fr(v, d) + ' %'
VIO, ROSE, INK, SEC, MUT, HAIR, SLATE = '#6520ff', '#b23a55', '#17151e', '#55515d', '#77717f', '#d8d5dd', '#4c4a55'

# ------------------------------------------------------------------ data
S = json.load(open(os.path.join(lake, 'summary.json'), encoding='utf-8'))['kpis']
N_FT = int(S['Offres France Travail (texte intégral, 2026)'].replace(' ', '')); N_CSP = int(S['Offres secteur public CSP 2022–2026'].replace(' ', ''))
N_AI = int(S['dont mention IA'].replace(' ', '')); N_CORE = int(S['dont IA dans l’intitulé'].replace(' ', '')); N_TECH = int(S['dont tech (ROME M18 + lexique)'].replace(' ', ''))
hm = pd.read_csv(os.path.join(res, 'hn_monthly.csv'), index_col=0); hm = hm[hm.index <= '2026-09']; N_HN = int(hm.n.sum())
cm = pd.read_csv(os.path.join(res, 'csp_monthly.csv'), index_col=0); cm = cm[(cm.index >= '2022-01') & (cm.index <= '2026-09')]
fm = pd.read_csv(os.path.join(res, 'ft_monthly.csv'), index_col=0)
N_ADZ = 11895; N_ALL = N_FT + N_CSP + N_HN + N_ADZ
hn_pre = 100 * hm.loc['2021-11':'2022-10'].ai_share.mean(); hn_last = 100 * hm.ai_share.tail(12).mean(); core_last = 100 * hm.core_share.tail(12).mean(); core_pre = 100 * hm.loc['2021-11':'2022-10'].core_share.mean()
seg = pd.read_csv(os.path.join(res, 'ft_segments.csv'), index_col=0)
con = pd.read_csv(os.path.join(res, 'ft_ai_share_by_contract.csv'), index_col=0)
cy = pd.read_csv(os.path.join(res, 'csp_yearly.csv'), index_col=0)
em = pd.read_csv(os.path.join(res, 'emergence_index.csv'))
naf = pd.read_csv(os.path.join(res, 'ft_ai_share_by_naf.csv'), index_col=0)
share_all = 100 * N_AI / N_FT; share_outside = 100 * seg.loc['AI mention, non-tech', 'n'] / N_AI
LAB = {'forward_deployed_engineer': 'Forward deployed engineer', 'ai_engineer': 'Ingénieur IA', 'head_of_ai': 'Responsable IA', 'mlops_engineer': 'Ingénieur MLOps', 'genai_engineer': 'Ingénieur IA générative', 'agent_engineer': 'Ingénieur agents IA', 'ai_governance': 'Gouvernance & conformité IA', 'ai_architect': 'Architecte IA', 'prompt_engineer': 'Prompt engineer', 'ml_engineer': 'Ingénieur machine learning', 'data_scientist': 'Data scientist', 'ai_trainer': 'Formateur IA / annotation'}
STAGE_FR = {'appearing': 'en apparition', 'diffusing': 'en diffusion', 'established': 'établi', 'fading': 'en reflux', 'intermittent': 'intermittent', 'too rare': 'trop rare'}

# ------------------------------------------------------------------ svg helpers
def T(x, y, s, cls='', anchor='start', size=None, fill=None, weight=None):
    st = (f' font-size="{size}"' if size else '') + (f' fill="{fill}"' if fill else '') + (f' font-weight="{weight}"' if weight else '')
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{(" class=%s" % chr(34) + cls + chr(34)) if cls else ""}{st}>{s}</text>'
def path(d, stroke, w=1.6, dash=None, fill='none', op=1.0):
    return f'<path d="{d}" stroke="{stroke}" stroke-width="{w}" fill="{fill}" stroke-linecap="round" stroke-linejoin="round" opacity="{op}"{(" stroke-dasharray=%s" % (chr(34) + dash + chr(34))) if dash else ""}/>'
def smooth(pts):
    """Catmull-Rom → cubic Bézier, like the hand-drawn trajectory sketch of the template."""
    if len(pts) < 3: return 'M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts)
    d = f'M{pts[0][0]:.1f},{pts[0][1]:.1f}'
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]; p1 = pts[i]; p2 = pts[i + 1]; p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6); c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f' C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}'
    return d

def svg_hn(W=440, H=168):
    m = dict(l=8, r=92, t=16, b=22); x0, x1 = MD('2011-04'), MD('2026-10')
    X = lambda d: m['l'] + (d - x0) / (x1 - x0) * (W - m['l'] - m['r']); Y = lambda v: H - m['b'] - v / 70 * (H - m['t'] - m['b'])
    s = [f'<path class="base" d="M{m["l"]} {Y(0):.1f}H{W - m["r"]}"/>']
    for v in (25, 50): s.append(f'<path d="M{m["l"]} {Y(v):.1f}H{W - m["r"]}" stroke="{HAIR}" stroke-width="0.6" stroke-dasharray="1 3"/>'); s.append(T(m['l'] - 3, Y(v) + 3, f'{v}', anchor='end', size=8.5, fill=MUT))
    ai = [(X(MD(mm)), Y(100 * v)) for mm, v in hm.ai_share_ma3.items()]; co = [(X(MD(mm)), Y(100 * v)) for mm, v in hm.core_share_ma3.items()]
    s.append(path(smooth(ai), VIO, 1.9)); s.append(path(smooth(co), ROSE, 1.5, dash='4 3'))
    xc = X(MD('2022-11')); s.append(f'<path d="M{xc:.1f} {m["t"]}V{Y(0):.1f}" stroke="{MUT}" stroke-width="0.7" stroke-dasharray="2 3"/>'); s.append(T(xc + 4, m['t'] + 7, 'ChatGPT', size=9, fill=MUT))
    s.append(T(W - m['r'] + 6, ai[-1][1] + 3, f'sept. 2026 : {pc(100 * hm.ai_share_ma3.iloc[-1], 0)} mentionnent l’IA', size=9.5, fill=VIO, weight='600'))
    s.append(T(W - m['r'] + 6, co[-1][1] + 3, f'{pc(100 * hm.core_share_ma3.iloc[-1], 0)} avec un intitulé IA', size=9.5, fill=ROSE, weight='600'))
    for y in (2012, 2016, 2020, 2024): s.append(T(X(MD(f'{y}-01')), H - 6, str(y), anchor='middle', size=9, fill=SEC))
    return f'<svg viewBox="0 0 {W} {H}" class="sk">' + ''.join(s) + '</svg>'

def svg_sources(W=300, H=150):
    rows = [('Hacker News', 'international', hm.n, SLATE, N_HN), ('Service public', 'France, intitulés', cm.n, '#9a94a6', N_CSP), ('France Travail', 'texte intégral', fm.n, VIO, N_FT), ('Adzuna', 'secteur privé', None, '#9a94a6', N_ADZ)]
    m = dict(l=100, r=8, t=6, b=18); x0, x1 = MD('2011-01'), MD('2027-01'); X = lambda d: m['l'] + (d - x0) / (x1 - x0) * (W - m['l'] - m['r']); rh = (H - m['t'] - m['b']) / 4
    s = []
    for i, (name, sub, ser, col, n) in enumerate(rows):
        yb = m['t'] + (i + 1) * rh - 4
        s.append(f'<path d="M{m["l"]} {yb:.1f}H{W - m["r"]}" stroke="{HAIR}" stroke-width="0.8"/>')
        if ser is not None:
            v = ser.values / ser.values.max() * (rh - 9); pts = [(X(MD(mm)), yb - vv) for mm, vv in zip(ser.index, v)]
            d = f'M{pts[0][0]:.1f},{yb:.1f} ' + ' '.join(f'L{x:.1f},{y:.1f}' for x, y in pts) + f' L{pts[-1][0]:.1f},{yb:.1f} Z'
            s.append(f'<path d="{d}" fill="{col}" opacity="0.8"/>')
        else: s.append(f'<path d="M{X(MD("2026-10")):.1f} {yb:.1f}V{yb - rh * 0.5:.1f}" stroke="{col}" stroke-width="2"/>')
        s.append(T(m['l'] - 6, yb - rh * 0.45, name, anchor='end', size=9.5, fill=INK)); s.append(T(m['l'] - 6, yb - rh * 0.45 + 10, f'{sub} · {fr(n)}', anchor='end', size=8, fill=MUT))
    xc = X(MD('2022-11')); s.append(f'<path d="M{xc:.1f} {m["t"]}V{H - m["b"] - 4}" stroke="{MUT}" stroke-width="0.7" stroke-dasharray="2 3"/>')
    for y in (2011, 2016, 2021, 2026): s.append(T(X(MD(f'{y}-01')), H - 4, str(y), anchor='middle', size=8.5, fill=SEC))
    return f'<svg viewBox="0 0 {W} {H}" class="sk">' + ''.join(s) + '</svg>'

def svg_contract(W=215, H=118):
    rows = [('Freelance', 'LIB'), ('Agent commercial', 'CCE'), ('Franchise', 'FRA'), ('CDI', 'CDI'), ('CDD', 'CDD'), ('Intérim', 'MIS')]
    m = dict(l=92, r=34, t=4, b=16); X = lambda v: m['l'] + v / 9 * (W - m['l'] - m['r']); rh = (H - m['t'] - m['b']) / len(rows)
    s = [f'<path d="M{X(share_all):.1f} {m["t"]}V{H - m["b"]}" stroke="{MUT}" stroke-width="0.7" stroke-dasharray="2 3"/>', T(X(share_all) + 3, H - m['b'] - 2, f'toutes offres {pc(share_all, 2)}', size=7.5, fill=MUT)]
    for i, (lab, code) in enumerate(rows):
        r = con.loc[code]; y = m['t'] + (i + 0.5) * rh; v = 100 * r.share
        s.append(f'<path d="M{X(100 * r.lo):.1f} {y:.1f}H{X(100 * r.hi):.1f}" stroke="{HAIR}" stroke-width="1.2"/>'); s.append(f'<circle cx="{X(v):.1f}" cy="{y:.1f}" r="3.2" fill="{VIO}"/>')
        s.append(T(m['l'] - 6, y + 3, lab, anchor='end', size=9, fill=INK)); s.append(T(X(100 * r.hi) + 5, y + 3, pc(v, 1), size=8.5, fill=SEC))
    s.append(f'<path class="base" d="M{m["l"]} {H - m["b"] + 2}H{W - m["r"]}"/>')
    for v in (0, 4, 8): s.append(T(X(v), H - 2, f'{v} %', anchor='middle', size=8, fill=SEC))
    return f'<svg viewBox="0 0 {W} {H}" class="sk">' + ''.join(s) + '</svg>'

def svg_salary(W=215, H=118):
    rows = [('Tech + IA', 'AI-related tech', VIO), ('IA dans l’intitulé', 'AI-core (title)', ROSE), ('Autres postes tech', 'Other tech', SLATE), ('Toutes les offres', 'All other postings', '#b5b0bf')]
    m = dict(l=92, r=34, t=4, b=16); X = lambda v: m['l'] + (v - 15) / 60 * (W - m['l'] - m['r']); rh = (H - m['t'] - m['b']) / len(rows)
    s = []
    for i, (lab, key, col) in enumerate(rows):
        r = seg.loc[key]; y = m['t'] + (i + 0.5) * rh
        s.append(f'<path d="M{X(r.sal_p25 / 1000):.1f} {y:.1f}H{X(r.sal_p75 / 1000):.1f}" stroke="{col}" stroke-width="5" stroke-linecap="butt"/>'); s.append(f'<circle cx="{X(r.sal_median / 1000):.1f}" cy="{y:.1f}" r="3" fill="#fdfdfb" stroke="{col}" stroke-width="1.4"/>')
        s.append(T(m['l'] - 6, y + 3, lab, anchor='end', size=9, fill=INK)); s.append(T(X(r.sal_p75 / 1000) + 5, y + 3, f'{fr(r.sal_median / 1000, 0)} k€', size=8.5, fill=SEC))
    s.append(f'<path class="base" d="M{m["l"]} {H - m["b"] + 2}H{W - m["r"]}"/>')
    for v in (20, 40, 60): s.append(T(X(v), H - 2, f'{v} k€', anchor='middle', size=8, fill=SEC))
    return f'<svg viewBox="0 0 {W} {H}" class="sk">' + ''.join(s) + '</svg>'

def svg_public(W=215, H=118):
    m = dict(l=30, r=8, t=10, b=16); n = len(cy); bw = (W - m['l'] - m['r']) / n; Y = lambda v: H - m['b'] - v / 28 * (H - m['t'] - m['b'])
    s = [f'<path class="base" d="M{m["l"]} {Y(0):.1f}H{W - m["r"]}"/>']
    for i, (yr, r) in enumerate(cy.iterrows()):
        x = m['l'] + i * bw + bw * 0.22; w = bw * 0.56
        s.append(f'<rect x="{x:.1f}" y="{Y(r.ai_per_10k):.1f}" width="{w:.1f}" height="{Y(0) - Y(r.ai_per_10k):.1f}" fill="{ROSE}" opacity="{0.45 + 0.12 * i:.2f}"/>')
        s.append(T(x + w / 2, Y(r.ai_per_10k) - 4, fr(r.ai_per_10k, 0), anchor='middle', size=9, fill=INK, weight='600')); s.append(T(x + w / 2, H - 3, str(yr), anchor='middle', size=8.5, fill=SEC))
    s.append(T(m['l'] - 4, m['t'] + 2, 'pour 10 000 offres', anchor='start', size=7.5, fill=MUT))
    return f'<svg viewBox="0 0 {W} {H}" class="sk">' + ''.join(s) + '</svg>'

def svg_titles(W=440, H=188):
    keys = ['data_scientist', 'ml_engineer', 'ai_engineer', 'head_of_ai', 'forward_deployed_engineer', 'mlops_engineer', 'genai_engineer', 'ai_governance', 'agent_engineer', 'ai_architect']
    rows = [em[em.canon == k].iloc[0] for k in keys]; rows = sorted(rows, key=lambda r: str(r.hn_first_5))
    m = dict(l=150, r=104, t=8, b=18); x0, x1 = MD('2012-01'), MD('2027-01'); X = lambda d: m['l'] + (d - x0) / (x1 - x0) * (W - m['l'] - m['r']); rh = (H - m['t'] - m['b']) / len(rows)
    s = []; xc = X(MD('2022-11')); s.append(f'<path d="M{xc:.1f} {m["t"] - 2}V{H - m["b"]}" stroke="{ROSE}" stroke-width="0.7" stroke-dasharray="2 3"/>'); s.append(T(xc + 4, m['t'] + 5, 'ChatGPT', size=8.5, fill=ROSE))
    for i, r in enumerate(rows):
        y = m['t'] + (i + 0.5) * rh; xa, xb = X(MD(r.hn_first_seen)), X(MD(r.hn_first_5)); col = VIO if r.stage in ('appearing', 'diffusing') else SLATE
        s.append(f'<path d="M{xa:.1f} {y:.1f}H{xb:.1f}" stroke="{col}" stroke-width="1" opacity="0.6"/>'); s.append(f'<circle cx="{xa:.1f}" cy="{y:.1f}" r="2.6" fill="#fdfdfb" stroke="{col}" stroke-width="1.2"/>')
        rad = 2.6 + 0.75 * math.sqrt(max(0, r.hn_last12)); s.append(f'<circle cx="{xb:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="{col}" opacity="0.9"/>')
        s.append(T(m['l'] - 8, y + 3, LAB.get(r.canon, r.label), anchor='end', size=9.5, fill=INK))
        s.append(T(W - m['r'] + 8, y + 3, f'{STAGE_FR.get(r.stage, r.stage)} · {int(r.fr_postings_2026)} offres FR', size=8.5, fill=VIO if r.stage in ('appearing', 'diffusing') else SEC))
    s.append(f'<path class="base" d="M{m["l"]} {H - m["b"] + 2}H{W - m["r"]}"/>')
    for y in (2013, 2017, 2021, 2025): s.append(T(X(MD(f'{y}-01')), H - 3, str(y), anchor='middle', size=9, fill=SEC))
    return f'<svg viewBox="0 0 {W} {H}" class="sk">' + ''.join(s) + '</svg>'

logo_svg = open(os.path.join(root, '_prior', 'PSTB-ELIA-jobs', 'assets', 'logo-pstb-blanc.svg'), encoding='utf-8').read().replace('aria-label="Paris School of Technology & Business"', 'aria-label="Paris School of Technology &amp; Business"')
logo_url = 'data:image/svg+xml;base64,' + base64.b64encode(logo_svg.encode('utf-8')).decode('ascii')
fde = em[em.canon == 'forward_deployed_engineer'].iloc[0]; genai = em[em.canon == 'genai_engineer'].iloc[0]
lib, cdi = 100 * con.loc['LIB', 'share'], 100 * con.loc['CDI', 'share']
sal_ai, sal_tech = seg.loc['AI-related tech', 'sal_median'] / 1000, seg.loc['Other tech', 'sal_median'] / 1000
n_app = int((em.stage == 'appearing').sum()); n_fad = int((em.stage == 'fading').sum())

html = f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light">
<title>ELIA · Les métiers de l'IA en France</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,500;12..96,600;12..96,700&family=Hanken+Grotesk:wght@400;500;600&display=block">
<style>
:root{{--paper:#fdfdfb;--ink:#17151e;--secondary:#55515d;--muted:#77717f;--hair:#d8d5dd;--violet:#6520ff;--rose:#b23a55;--display:'Bricolage Grotesque',Arial,sans-serif;--text:'Hanken Grotesk',Arial,sans-serif}}
*{{box-sizing:border-box}} html,body{{margin:0;background:#eeedf0;color:var(--ink);font-family:var(--text);-webkit-font-smoothing:antialiased}} h1,h2,h3,p,figure{{margin:0}}
@page{{size:A4;margin:0}}
.sheet{{width:210mm;height:297mm;margin:0 auto;padding:11mm 13mm 9mm;background:var(--paper);display:flex;flex-direction:column}}
.mast{{display:flex;align-items:center;gap:14px;min-height:26px}} .wordmark{{font-family:var(--display);font-size:16px;font-weight:700;letter-spacing:.01em}} .wordmark i{{display:inline-block;width:5px;height:5px;background:var(--violet);margin:0 0 7px 5px}}
.mast p{{font-size:10.5px;letter-spacing:.035em;color:var(--secondary)}} .mast .meeting{{font-size:10.5px;color:var(--secondary);border-left:1px solid var(--hair);padding-left:14px}} .brand-logo{{width:74px;height:32px;object-fit:contain;filter:brightness(0);margin-left:auto}}
.title{{margin:9px 0 10px}} h1{{font-family:var(--display);font-size:29px;font-weight:500;letter-spacing:-.025em;line-height:1.1}} .title p{{font-size:11.5px;color:var(--secondary);line-height:1.35;margin-top:6px;max-width:150mm}}
.row{{display:grid;grid-template-columns:104px minmax(0,1fr);gap:16px;padding:9px 0;border-top:1px solid var(--hair)}} .row h2{{font-family:var(--display);font-weight:500;font-size:11px;letter-spacing:-.01em;line-height:1.3;color:var(--ink);padding-top:2px}}
.content{{min-width:0;font-size:12px;line-height:1.3}} .statement{{font-size:12.5px;font-weight:500;line-height:1.32}} .detail{{font-size:10.5px;color:var(--secondary);margin-top:4px;line-height:1.35}}
.two{{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:18px;align-items:center}} .two.wide{{grid-template-columns:200px minmax(0,1fr)}}
.three{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-top:4px}} .three figcaption,.sk-cap{{font-size:9px;color:var(--muted);margin-top:2px;line-height:1.3}}
svg.sk{{display:block;width:100%;height:auto;overflow:visible}} svg.sk text{{font-family:var(--text)}} svg.sk .base{{stroke:#d8d5dd;stroke-width:1;fill:none}}
.outputs{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}} .output h3{{font-family:var(--display);font-weight:500;font-size:12.5px;letter-spacing:-.012em;line-height:1.2}} .output p{{font-size:10.5px;color:var(--secondary);margin-top:3px;line-height:1.35}}
.decisions{{margin-top:auto;padding-top:8px;border-top:1px solid var(--hair);display:flex;gap:12px;align-items:baseline;font-size:9.5px;line-height:1.3;color:var(--secondary)}} .decisions .label{{font-weight:500;color:var(--violet)}} .decisions .folio{{margin-left:auto;color:var(--muted);white-space:nowrap}}
b{{font-weight:600;color:var(--ink)}} .num{{font-variant-numeric:tabular-nums}}
@media print{{html,body{{background:var(--paper);print-color-adjust:exact;-webkit-print-color-adjust:exact}}.sheet{{margin:0}}}}
</style>
</head>
<body>
<main class="sheet">
  <header class="mast"><div class="wordmark">ELIA<i aria-hidden="true"></i></div><p>Observatoire des métiers de l'IA</p><span class="meeting">Note de synthèse · octobre 2026</span><img class="brand-logo" src="{logo_url}" alt="Paris School of Technology &amp; Business"></header>
  <div class="title"><h1>Les métiers de l'IA en France : ce que disent {fr(N_ALL / 1e6, 1)} millions d'offres d'emploi</h1>
  <p>Première lecture, avec des règles fixées à l'avance, de {fr(N_FT)} offres France Travail en texte intégral, {fr(N_CSP)} offres du secteur public depuis 2022 et {fr(N_HN)} annonces tech internationales depuis 2011. Chiffres préliminaires.</p></div>

  <section class="row"><h2>Quinze ans de recrutements tech</h2><div class="content two wide">
    <div><p class="statement">{pc(hn_last, 0)} des annonces tech internationales mentionnent l'IA sur les douze derniers mois, contre {pc(hn_pre, 0)} l'année précédant ChatGPT.</p><p class="detail">Les annonces dont l'intitulé est un métier de l'IA passent de {pc(core_pre, 0)} à {pc(core_last, 0)} : une couche mince de spécialistes, une couche épaisse de postes ordinaires qui parlent d'IA.</p></div>
    {svg_hn()}</div></section>

  <section class="row"><h2>La France<br>en 2026</h2><div class="content">
    <p class="statement">{pc(share_all, 2)} des offres mentionnent l'IA, et {pc(share_outside, 0)} de ces offres ne sont pas des postes informatiques : immobilier, comptabilité, enseignement, commerce.</p>
    <div class="three">
      <figure>{svg_contract()}<figcaption>Part des offres mentionnant l'IA par type de contrat · France Travail 2026</figcaption></figure>
      <figure>{svg_salary()}<figcaption>Salaire annuel affiché, quartiles et médiane · offres avec salaire</figcaption></figure>
      <figure>{svg_public()}<figcaption>Secteur public : offres mentionnant l'IA pour 10 000 offres · Choisir le Service Public</figcaption></figure>
    </div></div></section>

  <section class="row"><h2>Les métiers<br>qui naissent</h2><div class="content two wide">
    <div><p class="statement">Dix intitulés, du premier au cinquième signalement dans les annonces internationales.</p><p class="detail">Le cercle plein grandit avec les mentions des douze derniers mois. {n_app} intitulés sont en apparition, {n_fad} en reflux ; la plupart des nouveaux noms recombinent « IA » avec un rôle existant.</p></div>
    {svg_titles()}</div></section>

  <section class="row"><h2>Trois repères</h2><div class="content outputs">
    <div class="output"><h3>Les indépendants en première ligne</h3><p>{pc(lib, 1)} des missions freelance mentionnent l'IA, contre {pc(cdi, 1)} des CDI : la demande passe d'abord par la mission.</p></div>
    <div class="output"><h3>Une prime salariale visible</h3><p>Médiane affichée de {fr(sal_ai, 0)} k€ pour les postes tech avec IA, {fr(sal_tech, 0)} k€ pour les autres postes tech. À confirmer toutes choses égales par ailleurs.</p></div>
    <div class="output"><h3>Un contre-exemple : le prompt engineer</h3><p>Né en 2023 dans les annonces internationales, l'intitulé a presque disparu en 2026. La compétence s'est fondue dans les autres métiers.</p></div>
  </div></section>

  <section class="row"><h2>Sources<br>et méthode</h2><div class="content two">
    <p class="detail" style="margin-top:0">France Travail (API Offres d'emploi, texte intégral), Choisir le Service Public (archives data.gouv.fr), Hacker News « Who is hiring », Adzuna. Périmètre tech, mention IA et IA dans l'intitulé définis par des règles bilingues fixées avant lecture des résultats ; 1 000 offres annotées en aveugle pour mesurer la précision ({pc(90, 0)}) et le rappel ({pc(98, 0)}) de la mention IA ; intervalles de confiance à 95 %. Indice d'émergence par intitulé : nouveauté, croissance, diffusion, persistance.</p>
    {svg_sources()}</div></section>

  <footer class="decisions"><span class="label">Contact</span><span>Linda Belkessa · Armand Derhy · Mahdi Zargayouna — Laboratoire ELIA, PST&amp;B · GRETTIA-COSYS, Université Gustave Eiffel</span><span class="folio">Données au 14 octobre 2026 · observatoire en ligne à venir</span></footer>
</main>
</body></html>'''
open(os.path.join(out, 'onepager.html'), 'w', encoding='utf-8').write(html); print('html written')
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={'width': 794, 'height': 1123}, device_scale_factor=2)
        pg.goto('file:///' + os.path.join(out, 'onepager.html').replace('\\', '/')); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(1800)
        ok = pg.evaluate('''document.fonts.check('500 24px "Bricolage Grotesque"') && document.fonts.check('400 24px "Hanken Grotesk"')'''); print('fonts loaded:', ok)
        pg.pdf(path=os.path.join(out, 'onepager.pdf'), format='A4', print_background=True, prefer_css_page_size=True)
        pg.locator('.sheet').screenshot(path=os.path.join(out, 'onepager.png')); b.close()
    print('pdf + png exported')
except Exception as e: print('export failed:', e)
