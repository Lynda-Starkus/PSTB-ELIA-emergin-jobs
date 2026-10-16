"""ESCO skills crawl (NDJSON) -> tidy parquet: one row per concept with fr/en labels, alt labels, type, broader groups, top-level pillar."""
import sys, os, json, pandas as pd
sys.stdout.reconfigure(encoding='utf-8')
root = sys.argv[1]; src = os.path.join(root, 'data-lake', 'raw', 'esco', 'esco_skills_concepts.ndjson'); dst = os.path.join(root, 'data-lake', 'lake', 'esco_skills.parquet')
recs = [json.loads(l) for l in open(src, encoding='utf-8') if l.strip()]
by = {r['uri']: r for r in recs}
def labels(r, lang):
    pl = (r.get('preferredLabel') or {}).get(lang); al = (r.get('alternativeLabel') or {}).get(lang) or []
    if isinstance(al, str): al = [al]
    return pl, al
def path_to_top(uri, depth=0):
    r = by.get(uri)
    if not r or depth > 12: return []
    bs = r.get('broader') or []
    if not bs: return [uri]
    return path_to_top(bs[0], depth + 1) + [uri]
rows = []
for r in recs:
    fr, fr_alt = labels(r, 'fr'); en, en_alt = labels(r, 'en')
    p = path_to_top(r['uri']); groups = [by[u].get('title') or (by[u].get('preferredLabel') or {}).get('en') for u in p[:-1] if u in by]
    rows.append({'uri': r['uri'], 'kind': r['kind'], 'className': r.get('className'), 'label_fr': fr, 'label_en': en, 'alt_fr': json.dumps(fr_alt, ensure_ascii=False), 'alt_en': json.dumps(en_alt, ensure_ascii=False),
                 'skillType': r.get('skillType'), 'reuseLevel': r.get('reuseLevel'), 'desc_fr': (r.get('description') or {}).get('fr'), 'desc_en': (r.get('description') or {}).get('en'), 'depth': len(p) - 1,
                 'group1': groups[1] if len(groups) > 1 else None, 'group2': groups[2] if len(groups) > 2 else None, 'group3': groups[3] if len(groups) > 3 else None, 'n_alt': len(fr_alt) + len(en_alt)})
df = pd.DataFrame(rows); df.to_parquet(dst, index=False)
print('concepts', len(df)); print(df.className.value_counts().to_dict()); print(df.skillType.value_counts(dropna=False).to_dict())
print(df.group1.value_counts().head(15).to_dict())
sk = df[df.className == 'Skill']; print('skills', len(sk), 'with fr label', sk.label_fr.notna().sum(), 'short fr (<=3 words)', (sk.label_fr.fillna('').str.split().str.len().between(1, 3)).sum())
print(sk[sk.label_en.fillna('').str.contains('machine learning|artificial intelligence|deep learning|natural language|computer vision', case=False)][['label_en', 'label_fr', 'skillType', 'group1', 'group2']].head(30).to_string())
