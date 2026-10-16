# -*- coding: utf-8 -*-
"""Emergence Index and lifecycle stages per canonical title (HN monthly series 2011-2026; FT 2026 cross-section adds French breadth).
E = rank-mean(N novelty, G shrunk 12-month growth, B breadth, P persistence). Stages by rules (see fig2)."""
import sys, os, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lexicon as L
sys.stdout.reconfigure(encoding='utf-8')
root = sys.argv[1]; lake = os.path.join(root, 'data-lake', 'lake'); res = os.path.join(lake, 'results')
hn = pd.read_parquet(os.path.join(lake, 'hn_classified.parquet'), columns=['month', 'canon', 'text', 'ai_tier'])
hn['company'] = hn.text.str.split(r'\s\|\s', regex=True).str[0].str.strip().str[:40]
months = sorted(hn.month.unique()); tot = hn.groupby('month').size()
ft = pd.read_parquet(os.path.join(lake, 'ft_enriched.parquet'), columns=['canon', 'entreprise.nom', 'dept'])
rows = []
for c in L.CANON_LABEL:
    g = hn[hn.canon == c]
    if len(g) == 0 and (ft.canon == c).sum() == 0: continue
    mc = g.groupby('month').size().reindex(months, fill_value=0)
    cum = mc.cumsum(); first5 = cum[cum >= 5].index.min() if (cum >= 5).any() else None
    def win(k, off=0):
        idx = months[len(months) - off - k: len(months) - off]; return mc.reindex(idx).sum(), idx
    n12, idx12 = win(12); n_prev, idxp = win(12, 12)
    growth = np.log((n12 + 1) / (n_prev + 1)); shrink = n12 / (n12 + 10); G = growth * shrink
    # novelty: share of history after Nov 2022
    after = mc[[m > '2022-11' for m in months]].sum(); N = after / max(1, mc.sum()) if first5 and first5 <= '2022-11' else 1.0
    emp12 = g[g.month.isin(idx12)].company.nunique(); P = (mc.reindex(idx12) > 0).mean()
    ftg = ft[ft.canon == c]; fr_n = len(ftg); fr_emp = ftg['entreprise.nom'].nunique(); fr_dep = ftg.dept.nunique()
    rows.append({'canon': c, 'label': L.CANON_LABEL[c], 'family': L.CANON_FAMILY[c], 'hn_total': int(mc.sum()), 'hn_first_seen': mc[mc > 0].index.min() if mc.sum() else None, 'hn_first_5': first5, 'hn_last12': int(n12), 'hn_prev12': int(n_prev),
                 'growth_12m': growth, 'G': G, 'N': N, 'hn_employers_12m': int(emp12), 'P': P, 'fr_postings_2026': fr_n, 'fr_employers': fr_emp, 'fr_depts': fr_dep, 'share_last12_pct': 100 * n12 / max(1, tot.reindex(idx12).sum())})
df = pd.DataFrame(rows)
df['B'] = 0.5 * (df.hn_employers_12m / df.hn_employers_12m.max() + df.fr_employers / df.fr_employers.max())
for k in ['N', 'G', 'B', 'P']: df[k + '_rank'] = df[k].rank(pct=True)
df['E'] = df[['N_rank', 'G_rank', 'B_rank', 'P_rank']].mean(axis=1)
def stage(r):
    if r.hn_total + r.fr_postings_2026 < 5: return 'too rare'
    if r.hn_first_5 and r.hn_first_5 >= '2024-01' and r.hn_last12 >= 3: return 'appearing'
    if r.growth_12m < -0.5 and r.hn_prev12 >= 10: return 'fading'
    if r.growth_12m > 0.3 and r.hn_employers_12m >= 10: return 'diffusing'
    if r.P >= 0.9 and abs(r.growth_12m) <= 0.3: return 'established'
    if r.growth_12m > 0 and r.hn_last12 >= 5: return 'diffusing'
    return 'established' if r.P >= 0.75 else 'intermittent'
df['stage'] = df.apply(stage, axis=1)
df = df.sort_values('E', ascending=False); df.to_csv(os.path.join(res, 'emergence_index.csv'), index=False)
print(df[['label', 'hn_first_5', 'hn_last12', 'hn_prev12', 'growth_12m', 'hn_employers_12m', 'P', 'fr_postings_2026', 'fr_employers', 'E', 'stage']].round(2).to_string())
