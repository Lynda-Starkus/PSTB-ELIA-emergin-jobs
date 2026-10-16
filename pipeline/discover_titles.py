# -*- coding: utf-8 -*-
"""Data-driven discovery of emerging AI title n-grams (beyond the canonical list): title bigrams/trigrams containing an AI token,
first-appearance month, 12-month counts and growth, employer breadth. Sources: HN role segments (2011-2026) and FT normalised titles (2026)."""
import sys, os, re, json, numpy as np, pandas as pd
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lexicon as L
sys.stdout.reconfigure(encoding='utf-8')
root = sys.argv[1]; lake = os.path.join(root, 'data-lake', 'lake'); res = os.path.join(lake, 'results')
AI_TOK = re.compile(r"\b(ai|ia|ml|llm|llms|genai|nlp|mlops|llmops|agent|agents|agentic|prompt|rag|intelligence|artificielle|artificial|learning|generative|generative|vision|robotics|data|deep|neural|copilot|gpt|chatbot|conversational|inference|evals|alignment|safety|annotation|labeling|foundation|model|models|embedded)\b", re.I)
STOP = set("the a an and or of for to in with at on senior junior lead staff principal head intern remote sr jr de des du la le les et en d l un une pour chez h f".split())

def grams(t, nmin=2, nmax=4):
    toks = [w for w in re.findall(r"[a-zà-ÿ0-9][a-zà-ÿ0-9+#.-]*", t.lower()) if w not in STOP]
    out = set()
    for n in range(nmin, nmax + 1):
        for i in range(len(toks) - n + 1):
            g = toks[i:i + n]
            if AI_TOK.search(' '.join(g)) and not g[0] in STOP: out.add(' '.join(g))
    return out

hn = pd.read_parquet(os.path.join(lake, 'hn_classified.parquet'), columns=['month', 'role', 'text'])
hn['company'] = hn.text.str.split(r'\s\|\s', regex=True).str[0].str.strip().str[:40]
months = sorted(hn.month.unique()); last12 = set(months[-12:]); prev12 = set(months[-24:-12])
stat = defaultdict(lambda: {'n': 0, 'first': '9999', 'last12': 0, 'prev12': 0, 'emp': set(), 'emp12': set(), 'months': set()})
for m, r, c in zip(hn.month, hn.role.fillna(''), hn.company):
    for g in grams(r):
        s = stat[g]; s['n'] += 1; s['first'] = min(s['first'], m); s['months'].add(m); s['emp'].add(c)
        if m in last12: s['last12'] += 1; s['emp12'].add(c)
        elif m in prev12: s['prev12'] += 1
rows = [{'ngram': g, 'n': s['n'], 'first_seen': s['first'], 'last12': s['last12'], 'prev12': s['prev12'], 'growth': np.log((s['last12'] + 1) / (s['prev12'] + 1)), 'employers': len(s['emp']), 'employers_12m': len(s['emp12']), 'months_active': len(s['months'])} for g, s in stat.items() if s['n'] >= 8]
d = pd.DataFrame(rows)
# keep maximal n-grams: drop a gram if a longer gram containing it has >= 80 % of its count
d = d.sort_values('n', ascending=False)
keep = []
for r in d.itertuples():
    longer = d[(d.ngram.str.contains(re.escape(r.ngram), regex=True)) & (d.ngram.str.len() > len(r.ngram))]
    if len(longer) and longer.n.max() >= 0.8 * r.n: continue
    keep.append(r.Index)
d = d.loc[keep]
d['canon'] = d.ngram.map(L.canon_title)
d.sort_values(['first_seen', 'n'], ascending=[False, False]).to_csv(os.path.join(res, 'discovery_hn_ngrams.csv'), index=False)
new = d[(d.first_seen >= '2022-11')].sort_values('n', ascending=False)
print('HN n-grams >= 8:', len(d), '| first seen after ChatGPT:', len(new)); print(new.head(40).to_string())
# France Travail titles (2026): AI-core normalised titles with employers and departments
ft = pd.read_parquet(os.path.join(lake, 'ft_enriched.parquet'), columns=['title_norm', 'ai_core', 'ai_any', 'entreprise.nom', 'dept', 'canon'])
f = ft[ft.ai_core]
stat = defaultdict(lambda: {'n': 0, 'emp': set(), 'dep': set()})
for t, e, dp in zip(f.title_norm, f['entreprise.nom'].fillna(''), f.dept.fillna('')):
    for g in grams(t):
        s = stat[g]; s['n'] += 1; s['emp'].add(e); s['dep'].add(dp)
rows = [{'ngram': g, 'n': s['n'], 'employers': len(s['emp']), 'depts': len(s['dep']), 'canon': L.canon_title(g)} for g, s in stat.items() if s['n'] >= 5]
d2 = pd.DataFrame(rows).sort_values('n', ascending=False)
keep = []
for r in d2.itertuples():
    longer = d2[(d2.ngram.str.contains(re.escape(r.ngram), regex=True)) & (d2.ngram.str.len() > len(r.ngram))]
    if len(longer) and longer.n.max() >= 0.8 * r.n: continue
    keep.append(r.Index)
d2 = d2.loc[keep]; d2.to_csv(os.path.join(res, 'discovery_ft_ngrams.csv'), index=False)
print('FT AI-core n-grams >= 5:', len(d2)); print(d2.head(40).to_string())
