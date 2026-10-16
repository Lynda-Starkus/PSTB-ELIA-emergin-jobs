import sys, os, json, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lexicon as L
root = sys.argv[1]; lake = os.path.join(root, 'data-lake', 'lake')


def work(chunk):
    out = []
    for title, text, rome in chunk:
        tier, terms = L.ai_tier(text, title)
        out.append((L.is_tech(rome, title), tier, json.dumps(terms, ensure_ascii=False), L.normalise_title(title), L.canon_title(title), L.seniority_of(title)))
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    df = pd.read_parquet(os.path.join(lake, 'ft_postings.parquet'), columns=['id', 'intitule', 'text', 'romeCode'])
    rows = list(zip(df.intitule.fillna(''), df.text.fillna(''), df.romeCode.fillna('')))
    n = 48; chunks = [rows[i::n] for i in range(n)]  # Windows WaitForMultipleObjects caps pools below 64 handles
    with Pool(n) as p: res = p.map(work, chunks)
    cols = [None] * len(rows)
    for i, r in enumerate(res):
        for j, v in enumerate(r): cols[i + j * n] = v
    out = pd.DataFrame(cols, columns=['is_tech', 'ai_tier', 'ai_terms', 'title_norm', 'canon', 'seniority']); out.insert(0, 'id', df.id.values)
    out.to_parquet(os.path.join(lake, 'ft_classified.parquet'), index=False)
    print('rows', len(out)); print('tech', int(out.is_tech.sum()), '%.2f%%' % (100 * out.is_tech.mean()))
    print('ai_tier', out.ai_tier.value_counts().sort_index().to_dict())
    print('canon', out.canon.value_counts().to_dict())
    print('tech & tier>=2', int(((out.is_tech) & (out.ai_tier >= 2)).sum()), '| tier3', int((out.ai_tier == 3).sum()))
