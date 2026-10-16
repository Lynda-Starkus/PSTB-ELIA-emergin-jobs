"""Hacker News 'Who is hiring' posts -> role segment extraction + AI tier + canonical title."""
import sys, os, re, json, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lexicon as L
root = sys.argv[1]; lake = os.path.join(root, 'data-lake', 'lake'); os.makedirs(lake, exist_ok=True)
df = pd.read_parquet(os.path.join(root, 'data-lake', 'raw', 'hn', 'hn_whoishiring.parquet'))
ROLE_HINT = re.compile(r"engineer|developer|scientist|researcher|manager|designer|architect|analyst|lead|head|director|founder|cto|ceo|intern|devops|sre|ops|product|marketing|sales|recruit|writer|support|specialist|consultant|programmer|hacker|ml\b|ai\b|data", re.I)


def head_segments(text, n=4):
    head = text[:300]
    segs = [s.strip() for s in re.split(r"\s\|\s|\s[-–—]\s|\s/\s|\s•\s", head) if s.strip()]
    return segs[:n]


def role_of(text):
    segs = head_segments(text)
    for s in segs[1:]:
        if ROLE_HINT.search(s) and len(s) < 120: return s
    for s in segs:
        if ROLE_HINT.search(s) and len(s) < 120: return s
    return ""


df['role'] = df.text.fillna('').map(role_of)
df['title_norm'] = df.role.map(L.normalise_title)
df['canon'] = df.role.map(L.canon_title)
# title-level AI (role segment) and text-level AI
res = [L.ai_tier(t, r, lowercase_corpus=True) for t, r in zip(df.text.fillna(''), df.role)]
df['ai_tier'] = [r[0] for r in res]; df['ai_terms'] = [json.dumps(r[1]) for r in res]
df['seniority'] = df.role.map(L.seniority_of)
df['remote'] = df.text.str.contains(r"\bremote\b", case=False, regex=True)
df['year'] = df.month.str[:4]
df.to_parquet(os.path.join(lake, 'hn_classified.parquet'), index=False)
print('posts', len(df), 'with role', (df.role != '').sum())
print(df.groupby('year').apply(lambda g: pd.Series({'n': len(g), 'ai2+': (g.ai_tier >= 2).mean() * 100, 'ai3': (g.ai_tier == 3).mean() * 100})).round(1).to_string())
print(df.canon.value_counts().head(25).to_dict())
