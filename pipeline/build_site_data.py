# -*- coding: utf-8 -*-
"""Build website/data/site_data.js (window.ELIA = {...}) from the result tables: everything the observatory needs, aggregated only."""
import sys, os, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lexicon as L, skills as S
root = sys.argv[1]; lake = os.path.join(root, 'data-lake', 'lake'); res = os.path.join(lake, 'results'); out = os.path.join(root, 'website', 'data'); os.makedirs(out, exist_ok=True)
def rd(name, **kw): return pd.read_csv(os.path.join(res, name), **kw)
def clean(o):
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating, float)): return None if (o is None or np.isnan(o)) else round(float(o), 4)
    if isinstance(o, np.bool_): return bool(o)
    return o
D = {}
S_ = json.load(open(os.path.join(lake, 'summary.json'), encoding='utf-8')); D['kpis'] = S_['kpis']; D['generated'] = S_['generated']
LABEL_FR = {'forward_deployed_engineer': 'Forward Deployed Engineer', 'agent_engineer': 'Ingénieur agents IA', 'prompt_engineer': 'Prompt engineer', 'genai_engineer': 'Ingénieur IA générative / LLM', 'mlops_engineer': 'Ingénieur MLOps / plateforme IA', 'nlp_engineer': 'Ingénieur NLP', 'computer_vision_engineer': 'Ingénieur vision par ordinateur', 'ml_engineer': 'Ingénieur machine learning', 'ai_researcher': 'Chercheur·se IA', 'ai_architect': 'Architecte IA', 'ai_product_manager': 'AI product manager', 'head_of_ai': 'Responsable IA / Head of AI', 'ai_governance': 'Gouvernance, éthique & conformité IA', 'ai_consultant': 'Consultant·e / expert·e IA', 'ai_trainer': 'Formateur·rice IA / annotateur·rice', 'ai_sales': 'Commercial·e / solutions IA', 'ai_engineer': 'Ingénieur IA / développeur IA', 'data_scientist': 'Data scientist', 'data_engineer': 'Data engineer', 'data_analyst': 'Data analyst / BI', 'data_architect': 'Architecte data', 'data_leader': 'Responsable data & gouvernance', 'ai_other': 'Autre intitulé IA'}
FAM_FR = {'AI engineering (new titles)': 'Ingénierie IA (nouveaux intitulés)', 'AI engineering': 'Ingénierie IA', 'ML engineering': 'Ingénierie ML', 'AI research': 'Recherche IA', 'AI architecture & leadership': 'Architecture & direction IA', 'AI business roles': 'Fonctions business IA', 'AI governance & ethics': 'Gouvernance & éthique IA', 'AI training & data labelling': 'Formation & annotation', 'Data science': 'Data science', 'Data engineering': 'Ingénierie des données', 'Data analytics': 'Analyse & BI', 'Data leadership': 'Direction data', 'Other AI-labelled': 'Autres intitulés IA'}
SKILL_FAM_FR = {'AI/ML modelling': 'Modélisation IA/ML', 'Generative AI & LLM': 'IA générative & LLM', 'Data engineering': 'Ingénierie des données', 'Software engineering': 'Génie logiciel', 'Cloud, DevOps & MLOps': 'Cloud, DevOps & MLOps', 'Data analysis & BI': 'Analyse & BI', 'Governance, ethics & regulation': 'Gouvernance & éthique', 'Product & project': 'Produit & projet', 'Domain & business': 'Métier', 'Transversal & languages': 'Transversal & langues'}
STAGE_FR = {'appearing': 'en apparition', 'diffusing': 'en diffusion', 'established': 'établi', 'fading': 'en reflux', 'intermittent': 'intermittent', 'renamed': 'renommé', 'too rare': 'trop rare'}
D['labels'] = {'canon': LABEL_FR, 'family': FAM_FR, 'skill_family': SKILL_FAM_FR, 'stage': STAGE_FR, 'canon_en': L.CANON_LABEL, 'canon_family': L.CANON_FAMILY}
# HN monthly
hm = rd('hn_monthly.csv', index_col=0); hm = hm[hm.n >= 50]
D['hn_monthly'] = {'months': list(hm.index), 'n': hm.n.tolist(), 'ai_share': (100 * hm.ai_share).round(2).tolist(), 'core_share': (100 * hm.core_share).round(2).tolist(), 'ai_ma3': (100 * hm.ai_share_ma3).round(2).tolist(), 'core_ma3': (100 * hm.core_share_ma3).round(2).tolist()}
fam = rd('hn_family_share_monthly.csv', index_col=0).reindex(hm.index).fillna(0); fam = fam.rolling(3, center=True, min_periods=1).mean() * 100
D['hn_family_monthly'] = {'months': list(fam.index), 'families': {c: fam[c].round(3).tolist() for c in fam.columns}}
# per-canon monthly series from HN (for tickers/sparklines) + FR counts
hn = pd.read_parquet(os.path.join(lake, 'hn_classified.parquet'), columns=['month', 'canon']); months = list(hm.index)
tot = hn.groupby('month').size().reindex(months, fill_value=0)
series = {}
for c, g in hn[hn.canon.notna()].groupby('canon'):
    s = g.groupby('month').size().reindex(months, fill_value=0); series[c] = {'n': s.tolist(), 'per10k': (1e4 * s / tot.replace(0, np.nan)).fillna(0).round(1).tolist()}
D['hn_canon_monthly'] = {'months': months, 'series': series}
em = rd('emergence_index.csv'); ct = rd('ft_canon_titles.csv', index_col=0); skc = rd('skills_profile_by_canon_ft.csv').set_index('canon'); skh = rd('skills_profile_by_canon_hn.csv').set_index('canon')
titles = []
for r in em.itertuples():
    c = r.canon; row = {'canon': c, 'label_fr': LABEL_FR.get(c, c), 'label_en': L.CANON_LABEL.get(c, c), 'family': L.CANON_FAMILY.get(c), 'family_fr': FAM_FR.get(L.CANON_FAMILY.get(c), ''), 'E': r.E, 'stage': r.stage, 'stage_fr': STAGE_FR.get(r.stage, r.stage), 'N': r.N, 'G': r.G, 'B': r.B, 'P': r.P, 'hn_first_seen': r.hn_first_seen, 'hn_first_5': r.hn_first_5, 'hn_total': r.hn_total, 'hn_last12': r.hn_last12, 'hn_prev12': r.hn_prev12, 'growth_12m': r.growth_12m, 'hn_employers_12m': r.hn_employers_12m, 'share_last12_pct': r.share_last12_pct, 'fr_postings_2026': r.fr_postings_2026, 'fr_employers': r.fr_employers, 'fr_depts': r.fr_depts}
    if c in ct.index:
        q = ct.loc[c]; row.update({'fr_sal_median': q.sal_median, 'fr_sal_n': q.sal_n, 'fr_cdi_share': q.cdi_share, 'fr_exp_required': q.exp_required, 'fr_idf_share': q.idf_share})
    for src, sk in [('fr', skc), ('hn', skh)]:
        if c in sk.index: row[f'skills_{src}'] = {f: float(sk.loc[c, f]) for f in S.FAMILIES}; row[f'top_skills_{src}'] = json.loads(sk.loc[c, 'top_skills'])[:15]
    titles.append(row)
D['titles'] = titles
# FR breakdowns
for name, key in [('ft_ai_share_by_naf.csv', 'naf'), ('ft_ai_share_by_region.csv', 'region'), ('ft_ai_share_by_dept.csv', 'dept'), ('ft_ai_share_by_contract.csv', 'contract'), ('ft_ai_share_by_size.csv', 'size'), ('ft_ai_outside_tech_by_naf.csv', 'naf_outside_tech')]:
    d = rd(name, index_col=0, dtype={0: str}); d.index = d.index.astype(str)
    if key == 'dept': d.index = d.index.str.zfill(2)
    D['fr_' + key] = [{'key': k, 'n': int(v.n), 'k': int(v.k), 'share': round(100 * v.share, 3), 'lo': round(100 * v.lo, 3), 'hi': round(100 * v.hi, 3)} for k, v in d.iterrows()]
seg = rd('ft_segments.csv', index_col=0); D['fr_segments'] = {k: {c: (None if pd.isna(v[c]) else float(v[c])) for c in seg.columns} for k, v in seg.iterrows()}
D['fr_top_employers'] = [{'name': k, 'n': int(v)} for k, v in rd('ft_ai_top_employers.csv', index_col=0).iloc[:, 0].head(25).items()]
D['fr_ai_terms'] = [{'term': k, 'n': int(v)} for k, v in rd('ft_ai_terms.csv', index_col=0).iloc[:, 0].head(40).items()]
D['fr_rome'] = [{'code': r.romeCode, 'label': r.romeLibelle, 'n': int(r.iloc[2])} for _, r in rd('ft_ai_rome.csv').head(25).iterrows()]
D['fr_monthly'] = rd('ft_monthly.csv', index_col=0).reset_index().to_dict(orient='list')
# skills
sks = rd('skills_profile_by_segment.csv').set_index('segment'); D['skills_by_segment'] = {k: {f: float(v[f]) for f in S.FAMILIES} for k, v in sks.iterrows()}
D['skills_top_ai_fr'] = [{'skill': k, 'n': int(v), 'family': S.TERM2FAM.get(k)} for k, v in rd('skills_top_ai_ft.csv', index_col=0).iloc[:, 0].head(60).items()]
co = rd('skills_cooccurrence_ai_ft.csv', index_col=0); top = list(co.index[:40]); co = co.loc[top, top]
edges = []
for i, a in enumerate(top):
    for b in top[i + 1:]:
        c_ = float(co.loc[a, b]); jac = c_ / (co.loc[a, a] + co.loc[b, b] - c_ + 1e-9)
        if jac >= 0.12 and c_ >= 10: edges.append({'source': a, 'target': b, 'w': round(jac, 3), 'n': int(c_)})
D['skills_network'] = {'nodes': [{'id': a, 'n': int(co.loc[a, a]), 'family': S.TERM2FAM.get(a)} for a in top], 'edges': edges}
hy = rd('skills_profile_hn_ai_by_year.csv').set_index('year'); D['skills_hn_by_year'] = {'years': [str(y) for y in hy.index], 'families': {f: (100 * hy[f]).round(2).tolist() for f in S.FAMILIES}}
# CSP
cm = rd('csp_monthly.csv', index_col=0); cm = cm[cm.n >= 2000]; D['csp_monthly'] = {'months': list(cm.index), 'n': cm.n.tolist(), 'ai': cm.ai.tolist(), 'tech': cm.tech.tolist(), 'ai_per10k': (1e4 * cm.ai / cm.n).round(2).tolist()}
cy = rd('csp_yearly.csv', index_col=0); D['csp_yearly'] = {'years': [str(y) for y in cy.index], 'ai_per10k': cy.ai_per_10k.round(2).tolist(), 'n': cy.n.tolist(), 'ai': cy.ai.tolist()}
D['csp_canon'] = [{'canon': k, 'label_fr': LABEL_FR.get(k, k), 'n': int(v)} for k, v in rd('csp_ai_canon.csv', index_col=0).iloc[:, 0].items()]
D['csp_versant'] = [{'key': k, 'n': int(v.n), 'share': round(100 * v.share, 3)} for k, v in rd('csp_ai_by_versant.csv', index_col=0).iterrows()]
# discovery
dh = rd('discovery_hn_ngrams.csv'); dh = dh[(dh.first_seen >= '2022-11') & (dh.employers >= 2) & (~dh.ngram.str.contains('https|\\.ai$|^is |x$', regex=True))].sort_values('n', ascending=False).head(30)
D['discovery_hn'] = dh.to_dict(orient='records'); D['discovery_fr'] = rd('discovery_ft_ngrams.csv').head(40).to_dict(orient='records')
# validation
if os.path.exists(os.path.join(res, 'validation_scores.csv')): D['validation'] = rd('validation_scores.csv').to_dict(orient='records')
# bourse: tickers
months12 = months[-12:]; prev12 = months[-24:-12]; tot12 = tot.reindex(months12).sum(); totp = tot.reindex(prev12).sum()
tick = []
for t in titles:
    c = t['canon']; s = series.get(c, {'n': [0] * len(months)}); n = pd.Series(s['n'], index=months)
    last = n.reindex(months12).sum(); prev = n.reindex(prev12).sum(); v = 1e4 * last / max(1, tot12); vp = 1e4 * prev / max(1, totp)
    tick.append({'canon': c, 'ticker': ''.join(w[0] for w in c.split('_')).upper()[:4], 'label_fr': t['label_fr'], 'family': t['family'], 'value': round(v, 1), 'prev': round(vp, 1), 'change_pct': round(100 * (v - vp) / vp, 1) if vp > 0 else None, 'spark': [round(x, 1) for x in (1e4 * n.reindex(months[-36:]) / tot.reindex(months[-36:]).replace(0, np.nan)).fillna(0).tolist()], 'fr_volume': t['fr_postings_2026'], 'stage': t['stage'], 'E': t['E']})
D['bourse'] = {'months': months[-36:], 'tickers': tick, 'index_ai_share': D['hn_monthly']['ai_ma3'][-36:], 'index_core_share': D['hn_monthly']['core_ma3'][-36:]}
# geo
D['geo_regions'] = json.load(open(os.path.join(root, 'data-lake', 'geo', 'fr-regions.geojson'), encoding='utf-8'))
gj = json.load(open(os.path.join(root, 'data-lake', 'geo', 'departements.geojson'), encoding='utf-8'))
for f in gj['features']:
    f['properties'] = {'code': f['properties'].get('code'), 'nom': f['properties'].get('nom')}
    g = f['geometry']
    def rnd(c): return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 3), round(c[1], 3)]
    g['coordinates'] = rnd(g['coordinates'])
D['geo_depts'] = gj
js = 'window.ELIA = ' + json.dumps(clean(D), ensure_ascii=False, separators=(',', ':')) + ';'
open(os.path.join(out, 'site_data.js'), 'w', encoding='utf-8').write(js); print('site_data.js', round(len(js) / 1e6, 2), 'MB', 'titles', len(titles), 'tickers', len(tick))
