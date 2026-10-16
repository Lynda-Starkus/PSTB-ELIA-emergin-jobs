"""CSP public-sector postings (titles + RMFP metier + competences) -> tech / AI tiers / canonical titles."""
import sys, os, json, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lexicon as L
root = sys.argv[1]; lake = os.path.join(root, 'data-lake', 'lake')


def work(chunk):
    out = []
    for title, metier, comp in chunk:
        text = f"{title}\n{metier}\n{comp}"
        tier, terms = L.ai_tier(text, title)
        out.append((L.is_tech('', f"{title} {metier}"), tier, json.dumps(terms, ensure_ascii=False), L.normalise_title(title), L.canon_title(title) or L.canon_title(metier), L.seniority_of(title)))
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    df = pd.read_parquet(os.path.join(lake, 'csp_postings.parquet'), columns=['ref', 'title', 'metier_rmfp', 'competences', 'month'])
    rows = list(zip(df.title.fillna(''), df.metier_rmfp.fillna(''), df.competences.fillna('')))
    n = 48; chunks = [rows[i::n] for i in range(n)]  # Windows WaitForMultipleObjects caps pools below 64 handles
    with Pool(n) as p: res = p.map(work, chunks)
    cols = [None] * len(rows)
    for i, r in enumerate(res):
        for j, v in enumerate(r): cols[i + j * n] = v
    out = pd.DataFrame(cols, columns=['is_tech', 'ai_tier', 'ai_terms', 'title_norm', 'canon', 'seniority']); out.insert(0, 'ref', df.ref.values); out['month'] = df.month.values
    out.to_parquet(os.path.join(lake, 'csp_classified.parquet'), index=False)
    print('rows', len(out), 'tech', int(out.is_tech.sum()), 'ai_tier', out.ai_tier.value_counts().sort_index().to_dict())
    print(out[out.ai_tier >= 2].groupby(out.month.str[:4]).size().to_dict())
    print(out.canon.value_counts().head(20).to_dict())
