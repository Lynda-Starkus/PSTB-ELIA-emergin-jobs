# -*- coding: utf-8 -*-
"""Generate research-paper/numbers.tex: LaTeX macros for every number quoted in the manuscript, from the result tables (single source of truth)."""
import sys, os, json, glob, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lexicon as L
root = sys.argv[1]; lake = os.path.join(root, 'data-lake', 'lake'); res = os.path.join(lake, 'results'); out = os.path.join(root, 'research-paper', 'numbers.tex')
S = json.load(open(os.path.join(lake, 'summary.json'), encoding='utf-8'))['kpis']
def num(x): return f'{int(round(x)):,}'.replace(',', '\\,')
def pct(x, d=1): return f'{100 * x:.{d}f}'
M = {}
ftseg = pd.read_csv(os.path.join(res, 'ft_segments.csv'), index_col=0)
N = int(S['Offres France Travail (texte intégral, 2026)'].replace(' ', '')); NT = int(S['dont tech (ROME M18 + lexique)'].replace(' ', '')); NA = int(S['dont mention IA'].replace(' ', '')); NC = int(S['dont IA dans l’intitulé'].replace(' ', ''))
NCSP = int(S['Offres secteur public CSP 2022–2026'].replace(' ', '')); NHN = int(S['Annonces Hacker News 2011–2026'].replace(' ', ''))
M.update(nFT=num(N), nTech=num(NT), nAI=num(NA), nCore=num(NC), nCSP=num(NCSP), nHN=num(NHN), nAll=f'{(N + NCSP + NHN) / 1e6:.1f}', pTech=pct(NT / N, 2), pAI=pct(NA / N, 2), pCore=pct(NC / N, 2))
M['nAIoutside'] = num(ftseg.loc['AI mention, non-tech', 'n']); M['pAIoutside'] = pct(ftseg.loc['AI mention, non-tech', 'n'] / NA, 0)
for s, k in [('AI-core (title)', 'Core'), ('AI-related tech', 'AItech'), ('Other tech', 'Tech'), ('AI mention, non-tech', 'AIother'), ('All other postings', 'Rest')]:
    r = ftseg.loc[s]; M[f'sal{k}'] = f'{r.sal_median / 1000:.1f}'; M[f'salN{k}'] = num(r.sal_n); M[f'exp{k}'] = pct(r.exp_required, 0); M[f'cdi{k}'] = pct(r.cdi, 0); M[f'idf{k}'] = pct(r.idf, 0); M[f'nSeg{k}'] = num(r.n)
M['salAll'] = M['salRest']
M['salPremAItech'] = pct(ftseg.loc['AI-related tech', 'sal_median'] / ftseg.loc['Other tech', 'sal_median'] - 1, 0)
hm = pd.read_csv(os.path.join(res, 'hn_monthly.csv'), index_col=0)
M['hnAIlast'] = pct(hm.ai_share.tail(12).mean(), 0); M['hnAIpre'] = pct(hm.loc['2021-11':'2022-10'].ai_share.mean(), 0); M['hnCorelast'] = pct(hm.core_share.tail(12).mean(), 0); M['hnCorepre'] = pct(hm.loc['2021-11':'2022-10'].core_share.mean(), 0)
M['hnAIfirst'] = pct(hm.loc['2011-04':'2012-03'].ai_share.mean(), 0); M['hnLastMonth'] = hm.index[-1]
fam = pd.read_csv(os.path.join(res, 'hn_family_share_monthly.csv'), index_col=0); M['hnTitlesPre'] = pct(fam.loc['2019-01':'2019-12'].sum(axis=1).mean(), 1); M['hnTitlesLast'] = pct(fam.tail(6).sum(axis=1).mean(), 1)
cy = pd.read_csv(os.path.join(res, 'csp_yearly.csv'), index_col=0); M['cspFirst'] = f'{cy.ai_per_10k.iloc[0]:.1f}'; M['cspLast'] = f'{cy.ai_per_10k.iloc[-1]:.1f}'; M['cspRatio'] = f'{cy.ai_per_10k.iloc[-1] / cy.ai_per_10k.iloc[0]:.1f}'; M['cspAIn'] = num(cy.ai.sum())
naf = pd.read_csv(os.path.join(res, 'ft_ai_share_by_naf.csv'), index_col=0); M['nafJ'] = pct(naf.loc['J Information et communication', 'share'], 1); M['nafL'] = pct(naf.loc['L Immobilier', 'share'], 1); M['nafM'] = pct(naf.loc['M Activités spécialisées, scientifiques et techniques', 'share'], 1); M['nafF'] = pct(naf.loc['F Construction', 'share'], 2)
reg = pd.read_csv(os.path.join(res, 'ft_ai_share_by_region.csv'), index_col=0); M['idfShare'] = pct(reg.loc['Île-de-France', 'share'], 1); M['idfConc'] = pct(reg.loc['Île-de-France', 'k'] / reg.k.sum(), 0); M['idfJobs'] = pct(reg.loc['Île-de-France', 'n'] / reg.n.sum(), 0); M['regSecond'] = reg.index[1]; M['regSecondShare'] = pct(reg.share.iloc[1], 1)
con = pd.read_csv(os.path.join(res, 'ft_ai_share_by_contract.csv'), index_col=0); M['conLIB'] = pct(con.loc['LIB', 'share'], 1); M['conCDI'] = pct(con.loc['CDI', 'share'], 2); M['conMIS'] = pct(con.loc['MIS', 'share'], 2); M['conCDD'] = pct(con.loc['CDD', 'share'], 2)
dep = pd.read_csv(os.path.join(res, 'ft_ai_share_by_dept.csv'), index_col=0, dtype={0: str}); dep.index = dep.index.astype(str).str.zfill(2); M['depHautsDeSeine'] = pct(dep.loc['92', 'share'], 2); M['depParis'] = pct(dep.loc['75', 'share'], 2)
emp = pd.read_csv(os.path.join(res, 'ft_ai_top_employers.csv'), index_col=0).iloc[:, 0]; M['topTenEmp'] = pct(emp.head(10).sum() / NA, 1); M['topEmp'] = str(emp.index[0]); M['topEmpN'] = num(emp.iloc[0])
em = pd.read_csv(os.path.join(res, 'emergence_index.csv')).set_index('canon')
for c in ['forward_deployed_engineer', 'ai_engineer', 'agent_engineer', 'genai_engineer', 'ai_architect', 'ai_governance', 'ml_engineer', 'data_scientist', 'data_engineer', 'prompt_engineer', 'mlops_engineer', 'head_of_ai']:
    if c in em.index:
        r = em.loc[c]; k = ''.join(w.capitalize() for w in c.split('_'))
        M[f'E{k}'] = f'{r.E:.2f}'; M[f'stage{k}'] = str(r.stage); M[f'first{k}'] = str(r.hn_first_5)[:7] if isinstance(r.hn_first_5, str) else '--'; M[f'hnLast{k}'] = num(r.hn_last12); M[f'hnPrev{k}'] = num(r.hn_prev12); M[f'fr{k}'] = num(r.fr_postings_2026); M[f'frEmp{k}'] = num(r.fr_employers); M[f'g{k}'] = f'{r.growth_12m:+.2f}'
M['nStages'] = num((em.stage != 'too rare').sum()); M['nAppearing'] = num((em.stage == 'appearing').sum()); M['nFading'] = num((em.stage == 'fading').sum()); M['nEstablished'] = num((em.stage == 'established').sum()); M['nDiffusing'] = num((em.stage == 'diffusing').sum())
dh = pd.read_csv(os.path.join(res, 'discovery_hn_ngrams.csv')); M['nNgramsHN'] = num(len(dh)); M['nNgramsNew'] = num((dh.first_seen >= '2022-11').sum())
ct = pd.read_csv(os.path.join(res, 'ft_canon_titles.csv'), index_col=0); M['nCanonFR'] = num(ct.n.sum()); M['nCanonTitles'] = num(len(ct))
sk = pd.read_csv(os.path.join(res, 'skills_profile_by_segment.csv')).set_index('segment')
for s, k in [('AI-core (title)', 'Core'), ('AI-related tech', 'AItech'), ('Other tech', 'Tech')]:
    for f, kk in [('AI/ML modelling', 'Model'), ('Generative AI & LLM', 'GenAI'), ('Cloud, DevOps & MLOps', 'Cloud'), ('Software engineering', 'Soft'), ('Governance, ethics & regulation', 'Gov'), ('Data engineering', 'DataEng'), ('Transversal & languages', 'Transv')]:
        M[f'sk{kk}{k}'] = pct(sk.loc[s, f], 0)
hy = pd.read_csv(os.path.join(res, 'skills_profile_hn_ai_by_year.csv')).set_index('year'); hy.index = hy.index.astype(str)
M['hnGenAIpre'] = pct(hy.loc['2022', 'Generative AI & LLM'], 0); M['hnGenAIlast'] = pct(hy.loc['2026', 'Generative AI & LLM'], 0); M['hnModelPre'] = pct(hy.loc['2019', 'AI/ML modelling'], 0); M['hnModelLast'] = pct(hy.loc['2026', 'AI/ML modelling'], 0); M['hnGovLast'] = pct(hy.loc['2026', 'Governance, ethics & regulation'], 0)
vs = os.path.join(res, 'validation_scores.csv')
if os.path.exists(vs):
    v = pd.read_csv(vs); v = v[v.stratum == 'all'].set_index('label')
    for lab in ['is_tech', 'ai_any', 'ai_core']:
        k = ''.join(w.capitalize() for w in lab.split('_')); M[f'prec{k}'] = pct(v.loc[lab, 'precision'], 0); M[f'rec{k}'] = pct(v.loc[lab, 'recall'], 0); M[f'f{k}'] = f'{v.loc[lab, "f1"]:.2f}'; M[f'kappa{k}'] = f'{v.loc[lab, "kappa"]:.2f}'; M[f'nVal{k}'] = num(v.loc[lab, 'n'])
    v2 = pd.read_csv(vs); row = v2[(v2.label == 'ai_any') & (v2.stratum == 'ai_text')]
    if len(row): M['precAItext'] = pct(row.precision.iloc[0], 0)
ex = os.path.join(res, 'validation_extra.json')
if os.path.exists(ex):
    for k, v in json.load(open(ex)).items(): M[k] = v
lines = ['% auto-generated by pipeline/paper_numbers.py -- do not edit'] + [f'\\newcommand{{\\{k}}}{{{v}}}' for k, v in M.items()]
open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n'); print('macros', len(M))
