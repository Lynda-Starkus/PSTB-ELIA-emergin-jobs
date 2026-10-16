"""Run the dictionary skill extractor on the tech ∪ AI subset of France Travail and on all HN posts -> skill tables and family profiles per canonical title."""
import sys, os, json, numpy as np, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skills as S, lexicon as L
root = sys.argv[1]; lake = os.path.join(root, 'data-lake', 'lake'); res = os.path.join(lake, 'results')

def work(chunk):
    return [json.dumps(S.extract(t)) for t in chunk]

def run(texts, n=40):
    chunks = [texts[i::n] for i in range(n)]
    with Pool(n) as p: parts = p.map(work, chunks)
    out = [None] * len(texts)
    for i, part in enumerate(parts):
        for j, v in enumerate(part): out[i + j * n] = v
    return out

def profiles(df, key, min_n=20):
    rows = []
    for k, g in df.groupby(key):
        if len(g) < min_n: continue
        fam = {f: 0 for f in S.FAMILIES}; any_skill = 0; top = {}
        for s in g.skills:
            sk = json.loads(s); any_skill += bool(sk)
            fams = set(S.TERM2FAM.get(x) for x in sk)
            for f in fams:
                if f: fam[f] += 1
            for x in sk: top[x] = top.get(x, 0) + 1
        row = {key: k, 'n': len(g), 'with_skill': any_skill}; row.update({f: fam[f] / len(g) for f in S.FAMILIES})
        row['top_skills'] = json.dumps(sorted(top.items(), key=lambda x: -x[1])[:25], ensure_ascii=False); rows.append(row)
    return pd.DataFrame(rows)

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    ft = pd.read_parquet(os.path.join(lake, 'ft_enriched.parquet'), columns=['id', 'is_tech', 'ai_any', 'ai_core', 'canon', 'segment', 'naf_section', 'region'])
    sub = ft[ft.is_tech | ft.ai_any].copy()
    txt = pd.read_parquet(os.path.join(lake, 'ft_postings.parquet'), columns=['id', 'text']).set_index('id').text
    sub['skills'] = run(list(txt.reindex(sub.id).fillna('').values))
    sub.to_parquet(os.path.join(lake, 'ft_skills.parquet'), index=False)
    profiles(sub, 'segment', 1).to_csv(os.path.join(res, 'skills_profile_by_segment.csv'), index=False)
    profiles(sub[sub.canon.notna()], 'canon', 15).to_csv(os.path.join(res, 'skills_profile_by_canon_ft.csv'), index=False)
    # co-occurrence among AI postings (top 60 skills)
    ai = sub[sub.ai_any]; cnt = {}
    for s in ai.skills:
        for x in json.loads(s): cnt[x] = cnt.get(x, 0) + 1
    top = [k for k, _ in sorted(cnt.items(), key=lambda x: -x[1])[:60]]; idx = {k: i for i, k in enumerate(top)}
    M = np.zeros((len(top), len(top)), dtype=int)
    for s in ai.skills:
        xs = [idx[x] for x in json.loads(s) if x in idx]
        for a in xs:
            for b in xs: M[a, b] += 1
    pd.DataFrame(M, index=top, columns=top).to_csv(os.path.join(res, 'skills_cooccurrence_ai_ft.csv'))
    pd.Series(cnt).sort_values(ascending=False).head(150).to_csv(os.path.join(res, 'skills_top_ai_ft.csv'))
    print('FT subset', len(sub), 'AI', len(ai), 'top skills', top[:20])
    hn = pd.read_parquet(os.path.join(lake, 'hn_classified.parquet'), columns=['text', 'canon', 'ai_tier', 'month'])
    hn['skills'] = run(list(hn.text.fillna('').values))
    hn[['month', 'canon', 'ai_tier', 'skills']].to_parquet(os.path.join(lake, 'hn_skills.parquet'), index=False)
    profiles(hn[hn.canon.notna()], 'canon', 15).to_csv(os.path.join(res, 'skills_profile_by_canon_hn.csv'), index=False)
    hn['year'] = hn.month.str[:4]; profiles(hn[hn.ai_tier >= 2], 'year', 50).to_csv(os.path.join(res, 'skills_profile_hn_ai_by_year.csv'), index=False)
    print('HN done')
