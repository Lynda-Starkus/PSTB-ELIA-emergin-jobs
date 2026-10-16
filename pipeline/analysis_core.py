# -*- coding: utf-8 -*-
"""Core descriptive results for the three corpora -> data-lake/lake/results/*.csv|json and summary.json (dashboard KPIs)."""
import sys, os, re, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lexicon as L
sys.stdout.reconfigure(encoding='utf-8')
root = sys.argv[1]; lake = os.path.join(root, 'data-lake', 'lake'); res = os.path.join(lake, 'results'); os.makedirs(res, exist_ok=True)

DEPT2REG = {}
REGIONS = {'11': 'Île-de-France', '24': 'Centre-Val de Loire', '27': 'Bourgogne-Franche-Comté', '28': 'Normandie', '32': 'Hauts-de-France', '44': 'Grand Est', '52': 'Pays de la Loire', '53': 'Bretagne', '75': 'Nouvelle-Aquitaine', '76': 'Occitanie', '84': 'Auvergne-Rhône-Alpes', '93': "Provence-Alpes-Côte d'Azur", '94': 'Corse', '01': 'Guadeloupe', '02': 'Martinique', '03': 'Guyane', '04': 'La Réunion', '06': 'Mayotte'}
DEPTS = {'11': ['75', '77', '78', '91', '92', '93', '94', '95'], '24': ['18', '28', '36', '37', '41', '45'], '27': ['21', '25', '39', '58', '70', '71', '89', '90'], '28': ['14', '27', '50', '61', '76'], '32': ['02', '59', '60', '62', '80'], '44': ['08', '10', '51', '52', '54', '55', '57', '67', '68', '88'], '52': ['44', '49', '53', '72', '85'], '53': ['22', '29', '35', '56'], '75': ['16', '17', '19', '23', '24', '33', '40', '47', '64', '79', '86', '87'], '76': ['09', '11', '12', '30', '31', '32', '34', '46', '48', '65', '66', '81', '82'], '84': ['01', '03', '07', '15', '26', '38', '42', '43', '63', '69', '73', '74'], '93': ['04', '05', '06', '13', '83', '84'], '94': ['2A', '2B', '20'], '01': ['971'], '02': ['972'], '03': ['973'], '04': ['974'], '06': ['976']}
for r, ds in DEPTS.items():
    for d in ds: DEPT2REG[d] = REGIONS[r]
NAF_SECTIONS = [(1, 3, 'A Agriculture'), (5, 9, 'B Industries extractives'), (10, 33, 'C Industrie manufacturière'), (35, 35, 'D Énergie'), (36, 39, 'E Eau, déchets'), (41, 43, 'F Construction'), (45, 47, 'G Commerce'), (49, 53, 'H Transports'), (55, 56, 'I Hébergement-restauration'), (58, 63, 'J Information et communication'), (64, 66, 'K Finance, assurance'), (68, 68, 'L Immobilier'), (69, 75, 'M Activités spécialisées, scientifiques et techniques'), (77, 82, 'N Services administratifs et de soutien'), (84, 84, 'O Administration publique'), (85, 85, 'P Enseignement'), (86, 88, 'Q Santé, action sociale'), (90, 93, 'R Arts, spectacles'), (94, 96, 'S Autres services'), (97, 99, 'T-U Ménages, extraterritorial')]
def naf_section(code):
    try: d = int(str(code)[:2])
    except: return None
    for a, b, s in NAF_SECTIONS:
        if a <= d <= b: return s
    return None
RE_SAL = re.compile(r"(Annuel|Mensuel|Horaire|Cachet)\s+de\s+([\d.,]+)\s*Euros(?:\s+à\s+([\d.,]+)\s*Euros)?(?:\s+sur\s+([\d.,]+)\s*mois)?", re.I)
def salary_annual(s):
    if not isinstance(s, str): return (np.nan, np.nan)
    m = RE_SAL.search(s)
    if not m: return (np.nan, np.nan)
    unit, lo, hi, months = m.group(1).lower(), float(m.group(2).replace(',', '.')), m.group(3), m.group(4)
    hi = float(hi.replace(',', '.')) if hi else lo; months = float(months.replace(',', '.')) if months else 12.0
    f = {'annuel': 1.0, 'mensuel': months, 'horaire': 1607.0, 'cachet': np.nan}[unit]
    lo, hi = lo * f, hi * f
    if not (8000 <= lo <= 400000): return (np.nan, np.nan)
    return (lo, hi)

# ---------------- France Travail ----------------
ft = pd.read_parquet(os.path.join(lake, 'ft_postings.parquet'), columns=['id', 'intitule', 'month', 'date_posted', 'dept', 'romeCode', 'romeLibelle', 'entreprise.nom', 'typeContrat', 'experienceExige', 'experienceLibelle', 'salaire.libelle', 'codeNAF', 'trancheEffectifEtab', 'qualificationLibelle', 'origineOffre.origine', 'dup_text', 'alternance', 'lieuTravail.latitude', 'lieuTravail.longitude', 'ingest'])
cl = pd.read_parquet(os.path.join(lake, 'ft_classified.parquet'))
ft = ft.merge(cl, on='id', how='left')
ft['region'] = ft.dept.map(DEPT2REG); ft['naf_section'] = ft.codeNAF.map(naf_section)
sal = ft['salaire.libelle'].map(salary_annual); ft['sal_lo'] = [s[0] for s in sal]; ft['sal_hi'] = [s[1] for s in sal]; ft['sal_mid'] = (ft.sal_lo + ft.sal_hi) / 2
ft['ai_any'] = ft.ai_tier >= 2; ft['ai_core'] = ft.ai_tier == 3
ft['family'] = ft.canon.map(L.CANON_FAMILY)
ft['segment'] = np.select([ft.ai_core, ft.ai_any & ft.is_tech, ft.is_tech, ft.ai_any], ['AI-core (title)', 'AI-related tech', 'Other tech', 'AI mention, non-tech'], 'All other postings')
ft.to_parquet(os.path.join(lake, 'ft_enriched.parquet'), index=False)
N = len(ft); n_tech = int(ft.is_tech.sum()); n_ai = int(ft.ai_any.sum()); n_core = int(ft.ai_core.sum())
print('FT', N, 'tech', n_tech, 'ai_any', n_ai, 'ai_core', n_core)
# share tables
def share_table(df, by, flag, min_n=200):
    g = df.groupby(by).agg(n=(flag, 'size'), k=(flag, 'sum')); g = g[g.n >= min_n]; g['share'] = g.k / g.n
    # Wilson 95% CI
    z = 1.96; p = g.share; n = g.n
    g['lo'] = (p + z * z / (2 * n) - z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)
    g['hi'] = (p + z * z / (2 * n) + z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)
    return g.sort_values('share', ascending=False)
share_table(ft, 'naf_section', 'ai_any').to_csv(os.path.join(res, 'ft_ai_share_by_naf.csv'))
share_table(ft, 'region', 'ai_any').to_csv(os.path.join(res, 'ft_ai_share_by_region.csv'))
share_table(ft, 'dept', 'ai_any', 100).to_csv(os.path.join(res, 'ft_ai_share_by_dept.csv'))
share_table(ft[ft.is_tech], 'region', 'ai_any', 50).to_csv(os.path.join(res, 'ft_ai_share_tech_by_region.csv'))
share_table(ft, 'typeContrat', 'ai_any', 100).to_csv(os.path.join(res, 'ft_ai_share_by_contract.csv'))
# AI outside tech by sector
out = ft[~ft.is_tech]; share_table(out, 'naf_section', 'ai_any').to_csv(os.path.join(res, 'ft_ai_outside_tech_by_naf.csv'))
# canonical titles
ct = ft[ft.canon.notna()].groupby('canon').agg(n=('id', 'size'), employers=('entreprise.nom', 'nunique'), depts=('dept', 'nunique'), sal_median=('sal_mid', 'median'), sal_n=('sal_mid', 'count'), cdi_share=('typeContrat', lambda s: (s == 'CDI').mean()), exp_required=('experienceExige', lambda s: (s == 'E').mean()), idf_share=('region', lambda s: (s == 'Île-de-France').mean()))
ct['label'] = ct.index.map(L.CANON_LABEL); ct['family'] = ct.index.map(L.CANON_FAMILY); ct.sort_values('n', ascending=False).to_csv(os.path.join(res, 'ft_canon_titles.csv'))
# segments for salary / experience comparisons
ft['segment'] = np.select([ft.ai_core, ft.ai_any & ft.is_tech, ft.is_tech, ft.ai_any], ['AI-core (title)', 'AI-related tech', 'Other tech', 'AI mention, non-tech'], 'All other postings')
seg = ft.groupby('segment').agg(n=('id', 'size'), sal_n=('sal_mid', 'count'), sal_p25=('sal_mid', lambda s: s.quantile(.25)), sal_median=('sal_mid', 'median'), sal_p75=('sal_mid', lambda s: s.quantile(.75)), cdi=('typeContrat', lambda s: (s == 'CDI').mean()), exp_required=('experienceExige', lambda s: (s == 'E').mean()), debutant=('experienceExige', lambda s: (s == 'D').mean()), idf=('region', lambda s: (s == 'Île-de-France').mean()), alternance=('alternance', 'mean'), partner_origin=('origineOffre.origine', lambda s: (s.astype(str) == '2').mean()))
seg.to_csv(os.path.join(res, 'ft_segments.csv')); print(seg.round(3).to_string())
# top employers of AI postings
emp = ft[ft.ai_any].groupby('entreprise.nom').size().sort_values(ascending=False).head(40); emp.to_csv(os.path.join(res, 'ft_ai_top_employers.csv'))
top10 = emp.head(10).sum() / max(1, n_ai)
# monthly (censored) series
ms = ft.groupby('month').agg(n=('id', 'size'), tech=('is_tech', 'sum'), ai=('ai_any', 'sum'), core=('ai_core', 'sum')); ms.to_csv(os.path.join(res, 'ft_monthly.csv'))
# AI terms frequency among AI postings
from collections import Counter
cnt = Counter()
for s in ft.loc[ft.ai_any, 'ai_terms']:
    for t in json.loads(s): cnt[t] += 1
pd.Series(cnt).sort_values(ascending=False).head(80).to_csv(os.path.join(res, 'ft_ai_terms.csv'))
# normalised title ranking within AI-core
tn = ft[ft.ai_core].groupby('title_norm').agg(n=('id', 'size'), employers=('entreprise.nom', 'nunique')).sort_values('n', ascending=False); tn.head(300).to_csv(os.path.join(res, 'ft_aicore_titles_norm.csv'))
# ROME codes of AI postings
ft[ft.ai_any].groupby(['romeCode', 'romeLibelle']).size().sort_values(ascending=False).head(40).to_csv(os.path.join(res, 'ft_ai_rome.csv'))
# tranche effectif
share_table(ft, 'trancheEffectifEtab', 'ai_any', 100).to_csv(os.path.join(res, 'ft_ai_share_by_size.csv'))

# ---------------- CSP ----------------
csp = pd.read_parquet(os.path.join(lake, 'csp_postings.parquet'), columns=['ref', 'versant', 'organisme', 'categorie', 'dept', 'month', 'title', 'metier_rmfp'])
cc = pd.read_parquet(os.path.join(lake, 'csp_classified.parquet')).drop(columns=['month'])
csp = csp.merge(cc, on='ref', how='left'); csp['ai_any'] = csp.ai_tier >= 2
cm = csp[csp.month >= '2022-01'].groupby('month').agg(n=('ref', 'size'), tech=('is_tech', 'sum'), ai=('ai_any', 'sum')); cm['ai_share'] = cm.ai / cm.n; cm['tech_share'] = cm.tech / cm.n; cm.to_csv(os.path.join(res, 'csp_monthly.csv'))
cy = csp[csp.month >= '2022-01'].groupby(csp.month.str[:4]).agg(n=('ref', 'size'), tech=('is_tech', 'sum'), ai=('ai_any', 'sum')); cy['ai_per_10k'] = 1e4 * cy.ai / cy.n; cy.to_csv(os.path.join(res, 'csp_yearly.csv')); print(cy.to_string())
share_table(csp, 'versant', 'ai_any', 1000).to_csv(os.path.join(res, 'csp_ai_by_versant.csv'))
csp[csp.ai_any].groupby('canon').size().sort_values(ascending=False).to_csv(os.path.join(res, 'csp_ai_canon.csv'))
csp[csp.ai_any].groupby('organisme').size().sort_values(ascending=False).head(30).to_csv(os.path.join(res, 'csp_ai_top_orgs.csv'))

# ---------------- HN ----------------
hn = pd.read_parquet(os.path.join(lake, 'hn_classified.parquet')); hn['ai_any'] = hn.ai_tier >= 2; hn['ai_core'] = hn.ai_tier == 3
hm = hn.groupby('month').agg(n=('text', 'size'), ai=('ai_any', 'sum'), core=('ai_core', 'sum')); hm['ai_share'] = hm.ai / hm.n; hm['core_share'] = hm.core / hm.n
hm['ai_share_ma3'] = hm.ai_share.rolling(3, center=True, min_periods=1).mean(); hm['core_share_ma3'] = hm.core_share.rolling(3, center=True, min_periods=1).mean(); hm.to_csv(os.path.join(res, 'hn_monthly.csv'))
# family shares by month
hn['family'] = hn.canon.map(L.CANON_FAMILY)
fam = hn.pivot_table(index='month', columns='family', values='text', aggfunc='size', fill_value=0); fam = fam.div(hm.n, axis=0); fam.to_csv(os.path.join(res, 'hn_family_share_monthly.csv'))
# canonical title first appearance / growth
rows = []
months = sorted(hn.month.unique()); last12 = months[-12:]; prev12 = months[-24:-12]
for c, g in hn[hn.canon.notna()].groupby('canon'):
    mc = g.groupby('month').size()
    first = mc.index.min(); cum = mc.cumsum(); first5 = cum[cum >= 5].index.min() if (cum >= 5).any() else None
    n_last = int(mc.reindex(last12, fill_value=0).sum()); n_prev = int(mc.reindex(prev12, fill_value=0).sum())
    rows.append({'canon': c, 'label': L.CANON_LABEL.get(c), 'family': L.CANON_FAMILY.get(c), 'total': int(mc.sum()), 'first_seen': first, 'first_seen_5': first5, 'last12': n_last, 'prev12': n_prev, 'growth_12m': (np.log((n_last + 1) / (n_prev + 1))), 'share_last12_pct': 100 * n_last / max(1, hm.n.reindex(last12).sum())})
pd.DataFrame(rows).sort_values('total', ascending=False).to_csv(os.path.join(res, 'hn_canon_titles.csv'), index=False)
# French equivalents from FT for the same canon
ftc = ft[ft.canon.notna()].groupby('canon').size()

summary = {'kpis': {
    'Offres France Travail (texte intégral, 2026)': f'{N:,}'.replace(',', ' '), 'dont tech (ROME M18 + lexique)': f'{n_tech:,}'.replace(',', ' '), 'dont mention IA': f'{n_ai:,}'.replace(',', ' '), 'dont IA dans l’intitulé': f'{n_core:,}'.replace(',', ' '),
    'Offres secteur public CSP 2022–2026': f'{len(csp):,}'.replace(',', ' '), 'Annonces Hacker News 2011–2026': f'{len(hn):,}'.replace(',', ' '),
    'Part IA des annonces HN (12 derniers mois)': f"{100 * hn[hn.month.isin(last12)].ai_any.mean():.1f} %", 'Part IA des offres FT 2026': f"{100 * n_ai / N:.2f} %",
    'Concentration : top-10 employeurs IA (FT)': f"{100 * top10:.1f} %"},
    'generated': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}
json.dump(summary, open(os.path.join(lake, 'summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
