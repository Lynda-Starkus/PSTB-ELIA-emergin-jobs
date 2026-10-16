"""Regenerate the guided-tour chapter texts of index.html from the current data (outcomes, FT counts, regions, discovery, Adzuna).
Only the `const chapters=[ ... ];` block is rewritten; the page's design, scenes and scripts are untouched.
Usage: python tools/update_tour.py   (from website/)"""
from __future__ import annotations
import json, re, locale
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
rd = lambda n: json.loads((ROOT / 'data' / f'{n}.json').read_text(encoding='utf-8'))
O, FT, REG, DISC, ADZ, TAX = rd('outcomes'), rd('ft_fr'), rd('ft_regions'), rd('discovery'), rd('adzuna'), rd('taxonomy')
bundle = (ROOT / 'data' / 'data.js').read_text(encoding='utf-8')
D = json.loads(re.search(r'window\.ELIA_DATA\s*=\s*(\{.*?\});(?:\r?\n|$)', bundle, re.S).group(1))

MONTHS_FR = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
MONTHS_FR_S = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
def fint(n): return f'{int(round(n)):,}'.replace(',', ' ')
def fday(iso, short=False):
    y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10]); return f'{d} {(MONTHS_FR_S if short else MONTHS_FR)[m - 1]} {y}'
def fmon(ym, short=True): y, m = int(ym[:4]), int(ym[5:7]); return f'{(MONTHS_FR_S if short else MONTHS_FR)[m - 1]} {y}'
def pct(v): return ('+' if v > 0 else '') + f'{v:.0f} %'
def js(s): return "'" + s.replace('\\', '\\\\').replace("'", "\\'") + "'"
label = {t['id']: (t.get('title_fr') or t.get('title_en')) for t in TAX['titles']}
fam = {f['id']: f for f in TAX['families']}

ft_day = FT['collected_at'][:10]
corpus_total = DISC['fr']['corpus_total']; ft_total = DISC['fr']['by_source'].get('FT', 0)
cur, prev = O['meta']['hnCurrentWindow'], O['meta']['hnPreviousWindow']
window_txt = f"{fmon(cur['from'])}–{fmon(cur['to'])} / année précédente"
# FDE
fde = next((x for x in O['international5'] + O['bullish5'] if x['id'] == 'fde'), None)
# family with the largest 12-month gain (same computation as the page's scene 02)
ser, months = D['series']['families'], D['months']; last = len(months) - 1
gains = [(f['label_fr'], ser[f['id']][last] - ser[f['id']][max(0, last - 12)]) for f in D['families'] if not f['is_context'] and ser[f['id']][last] >= 0.1]
top_fam = max(gains, key=lambda x: x[1])[0] if gains else 'Ingénierie IA'
# France
aie = FT['results'].get('ai_engineer', {}); aie_c, aie_31 = aie.get('count', 0), aie.get('count_31j', 0)
emp = (ADZ.get('companies') or {}).get('ai_engineer') or []
regs = sorted(REG['regions'], key=lambda r: -r['total'])
cands = DISC['fr']['candidates']
jun = (O.get('optionalEvidence', {}).get('juniorExamples', {}) or {}).get('items') or []
sel = O['selectedFrance5']; bull = O['bullish5']; bear = O['bearish5']; absent = O['absent12Months']; intl = O['international5']
fde_i = next((x for x in intl if x['id'] == 'fde'), intl[0])

C = []  # (duration, target, label, heading, body, source, prepare_js, action_js)
C.append((9, '.sc-title', 'Objectif', f"{corpus_total / 1e6:.1f}".replace('.', ',') + ' millions d’offres analysées.', 'Quels métiers émergent avec l’IA ?', f'Étude France · {fint(corpus_total)} intitulés, dont {fint(ft_total)} offres France Travail.', None, None))
C.append((9, '.step[data-s="1"]', 'Signaux précoces', 'De nouveaux rôles apparaissent.', 'On suit leur diffusion dans les annonces.', f"HN · Archive internationale, {O['meta']['hnArchiveWindow']['from'][:4]}–{O['meta']['hnArchiveWindow']['to'][:4]}.", None, None))
if fde and fde.get('growthPct') is not None:
    C.append((10, '.step[data-s="2"]', 'Déploiement', f"FDE : {fde['previous']} → {fde['current']} mentions.", f"{pct(fde['growthPct'])} sur deux années comparées.", f'HN international · {window_txt}.', None, None))
C.append((8, '#accel', 'Familles en essor', f'{top_fam} gagne du terrain.', 'Le graphique suit les familles de métiers.', 'HN international · Parts des annonces, lissées sur 3 mois.', None, None))
C.append((11, '#france', 'France', f'Ingénieur IA : {fint(aie_c)} offres en ligne.', f'{fint(aie_31)} publiées depuis 31 jours ou moins.', f'France Travail · {fday(ft_day, True)} · Mots-clés, chevauchements possibles.', None, None))
C.append((8, '#france', 'Offres récentes', 'On regarde les offres récentes.', 'Le filtre passe à 31 jours.', f'France Travail · Collecte du {fday(ft_day)}.', None, "()=>click('#fr-metric button[data-m=\"count_31j\"]')"))
if len(emp) >= 2:
    C.append((9, '#france', 'Employeurs', f"{emp[0]['name']} : {emp[0]['count']} · {emp[1]['name']} : {emp[1]['count']}.", 'Des offres d’ingénieur IA publiées.', f"Adzuna France · Requête « AI engineer » · {fday(ADZ['collected_at'][:10])}.", "()=>$('#fr-metric button[data-m=\"count\"]').click()", None))
else:
    C.append((8, '#france', 'Toutes les offres', 'Retour à toutes les offres en ligne.', 'Comptage par mots-clés d’intitulé.', f'France Travail · Collecte du {fday(ft_day)}.', "()=>$('#fr-metric button[data-m=\"count\"]').click()", None))
C.append((9, '#carte', 'Territoires', f"{regs[0]['nom']} : {fint(regs[0]['total'])} offres.", f"{regs[1]['nom']} : {fint(regs[1]['total'])}.", f"France Travail · Requêtes sur {len(REG['titles_tracked'])} intitulés IA.", None, None))
if cands:
    c0 = cands[0]; C.append((11, '#decouverte', 'Appellations', f"{c0['label'].capitalize()} : {fint(c0['count'])} annonces.", f"{c0['variants']} variantes d’intitulé.", 'France · FT, CSP, Adzuna · Groupement automatique.', None, f"()=>click('#cands .cand[data-group=\"{c0['label']}\"]',true)"))
if len(cands) > 1:
    c1 = cands[1]; C.append((9, '#decouverte', 'Fiches à construire', f"{c1['label'].capitalize()} : {fint(c1['count'])} annonces.", 'Exemples bruts à l’appui.', 'France · Regroupement à valider.', None, f"()=>click('#cands .cand[data-group=\"{c1['label']}\"]',true)"))
if jun:
    j0 = jun[0]; C.append((9, '#decouverte', 'Entrée dans le métier', f"{j0['label'][:48]}" + (f" · {j0['contract']}" if j0.get('contract') else '') + '.', 'Un intitulé réellement publié.', f"France Travail · Exemple du {fday(j0['date'][:10])}." if j0.get('date') else 'France Travail · Exemple réel.', None, None))
C.append((12, '#intitules', 'Cinq rôles en France', f'{len(sel)} rôles IA recrutés en France.', ' · '.join(fint(x['ftCount'] or 0) for x in sel) + ' offres.', f'France Travail · Sélection ELIA · {fday(ft_day)}.', '()=>select(O.selectedFrance5)', None))
if len(bull) >= 2:
    C.append((13, '#intitules', 'Top 5 bullish', f"{label.get(bull[0]['id'], bull[0]['label'])} {pct(bull[0]['growthPct'])} · {label.get(bull[1]['id'], bull[1]['label'])} {pct(bull[1]['growthPct'])}.", f'Les {len(bull)} plus fortes hausses retenues.', 'HN international · 12 mois comparés · ≥ 24 mentions / 24 mois.', "()=>select(O.bullish5,'growth')", None))
if bear:
    C.append((13, '#intitules', 'Top 5 bearish', f"{label.get(bear[0]['id'], bear[0]['label'])} : {bear[0]['previous']} → {bear[0]['current']} mentions.", f'{len(bear)} intitulés en recul dans l’archive.', 'HN international · 12 mois comparés · Petits effectifs.', "()=>select(O.bearish5,'growth')", None))
if absent:
    C.append((11, '#intitules', 'Signaux absents', f'{len(absent)} intitulés absents depuis 12 mois.', 'Disparition du métier non établie.', 'HN international · 1–2 mentions l’année précédente.', '()=>select(O.absent12Months)', None))
C.append((10, '#intitules', 'France / international', f"FDE : {fde_i['current']} mentions HN, {fint(fde_i['ftCount'] or 0)} offres FR.", f'{len(intl)} rôles à surveiller ici.', 'HN / France Travail · Deux périmètres différents.', '()=>select(O.international5.slice().sort((a,b)=>(b.ftCount||0)-(a.ftCount||0)))', None))
C.append((11, '#intitules', 'Fiche métier', 'Ingénieur IA : ouvrir la fiche.', 'Alias, compétences et sources.', 'Référentiel ELIA · Fiche à actualiser.', "()=>{window.ELIA_NATIVE.select(null);search('Ingénieur IA');}", "()=>click('.cardt[data-title=\"ai_engineer\"]')"))
C.append((8, '#intitules', 'Thème', 'Original, clair ou sombre.', 'Le choix est mémorisé.', '', '()=>window.ELIA_NATIVE.select(null)', "()=>{document.body.classList.add('tour-show-theme');click('#theme-toggle');}"))
C.append((9, '#methode', 'Résultats', 'Repérer les rôles. Suivre leur diffusion.', 'Puis valider les fiches métier.', f'France : collecte du {fday(ft_day, True)} · Archive HN internationale.', None, None))

lines = []
for d, t, l, h, b, s, prep, act in C:
    args = [str(d), js(t), js(l), js(h), js(b), js(s)]
    if prep or act: args.append(prep or 'null')
    if act: args.append(act)
    lines.append('    chapter(' + ','.join(args) + ')')
block = 'const chapters=[\n' + ',\n'.join(lines) + '\n  ];'
html_path = ROOT / 'index.html'; html = html_path.read_text(encoding='utf-8')
new, n = re.subn(r'const chapters=\[\n[\s\S]*?\n  \];', lambda m: block, html, count=1)
assert n == 1, 'chapters block not found'
html_path.write_text(new, encoding='utf-8')
print(f'index.html: {len(C)} tour chapters rewritten from data ({fday(ft_day)})')
