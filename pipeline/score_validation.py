"""Score the rule-based classifier against the LLM-judge annotations: precision / recall / F1 per label and per stratum, Cohen's kappa, confusion; export the 200-item check list for Linda."""
import sys, os, glob, json, pandas as pd, numpy as np
root = sys.argv[1]; v = os.path.join(root, 'pipeline', 'validation'); res = os.path.join(root, 'data-lake', 'lake', 'results')
lab = pd.read_parquet(os.path.join(v, 'sample_1000_with_labels.parquet'))
rows = []
for f in sorted(glob.glob(os.path.join(v, 'judge_*.jsonl'))):
    for l in open(f, encoding='utf-8'):
        l = l.strip()
        if l:
            try: rows.append(json.loads(l))
            except Exception: pass
j = pd.DataFrame(rows).drop_duplicates('k'); j['k'] = j.k.astype(int)
d = lab.merge(j, on='k', how='inner', suffixes=('', '_judge'))
print('judged', len(d), 'of', len(lab))
def prf(y, p):
    y = y.astype(bool); p = p.astype(bool); tp = (y & p).sum(); fp = (~y & p).sum(); fn = (y & ~p).sum()
    pr = tp / max(1, tp + fp); rc = tp / max(1, tp + fn); f1 = 2 * pr * rc / max(1e-9, pr + rc)
    po = (y == p).mean(); pe = y.mean() * p.mean() + (1 - y.mean()) * (1 - p.mean()); k = (po - pe) / max(1e-9, 1 - pe)
    return dict(n=len(y), positives_judge=int(y.sum()), positives_rule=int(p.sum()), precision=pr, recall=rc, f1=f1, agreement=po, kappa=k)
out = []
if 'ai_job' not in d.columns: d['ai_job'] = d['ai_any']
d['ai_job'] = d['ai_job'].fillna(False).astype(bool)
# stricter rule-based flag (sensitivity): AI in title, >= 2 distinct terms, or one technical term
import sys as _s; _s.path.insert(0, os.path.join(root, 'pipeline')); import lexicon as L
d['label_ai_strict'] = [L.ai_substantive(json.loads(t) if isinstance(t, str) else [], 3 if c else (2 if a else 0)) if a else False for t, a, c in zip(d.ai_terms, d.label_ai_any, d.label_ai_core)]
for name, yc, pc in [('is_tech', 'is_tech', 'label_is_tech'), ('ai_any', 'ai_any', 'label_ai_any'), ('ai_job', 'ai_job', 'label_ai_any'), ('ai_job_strict', 'ai_job', 'label_ai_strict'), ('ai_core', 'ai_core', 'label_ai_core')]:
    r = prf(d[yc], d[pc]); r['label'] = name; r['stratum'] = 'all'; out.append(r)
    for s, g in d.groupby('stratum'):
        r = prf(g[yc], g[pc]); r['label'] = name; r['stratum'] = s; out.append(r)
# canonical title agreement among postings where both assign a canon
both = d[d.label_canon.notna() & d.canon.notna()]
canon_agree = (both.label_canon == both.canon).mean() if len(both) else np.nan
sc = pd.DataFrame(out)[['label', 'stratum', 'n', 'positives_judge', 'positives_rule', 'precision', 'recall', 'f1', 'agreement', 'kappa']]
sc.to_csv(os.path.join(res, 'validation_scores.csv'), index=False)
print(sc.round(3).to_string()); print('canon agreement (both assigned):', round(canon_agree, 3), 'n =', len(both))
extra = {'canonAgree': f'{100 * canon_agree:.0f}', 'nCanonBoth': str(len(both)), 'nJudged': str(len(d))}
# share of rule-positive AI mentions that the judge ties to the job itself (vs employer boilerplate), among judge-confirmed mentions
conf = d[d.label_ai_any & d.ai_any]; extra['aiJobShare'] = f'{100 * conf.ai_job.mean():.0f}' if len(conf) else 'NA'
json.dump(extra, open(os.path.join(res, 'validation_extra.json'), 'w'), indent=1)
# disagreements -> check list for Linda (200 items: all disagreements first, then random agreements)
d['disagree'] = (d.is_tech != d.label_is_tech) | (d.ai_any != d.label_ai_any) | (d.ai_core != d.label_ai_core)
chk = pd.concat([d[d.disagree], d[~d.disagree].sample(min(200, (~d.disagree).sum()), random_state=1)]).head(200)
chk[['k', 'id', 'stratum', 'title', 'rome', 'text', 'label_is_tech', 'is_tech', 'label_ai_any', 'ai_any', 'label_ai_core', 'ai_core', 'label_canon', 'canon', 'note', 'disagree']].rename(columns={'is_tech': 'judge_is_tech', 'ai_any': 'judge_ai_any', 'ai_core': 'judge_ai_core', 'canon': 'judge_canon'}).to_excel(os.path.join(v, 'check_list_for_linda.xlsx'), index=False)
print('disagreements', int(d.disagree.sum()), '-> check_list_for_linda.xlsx')
