"""Stratified validation sample (1 000 postings) for LLM-judge annotation: 300 AI-core, 300 AI-related (text only), 200 tech without AI, 200 random non-tech.
Each record: id, source, title, text excerpt (first 1 500 chars), our labels. Judges never see the labels (a blind file is written separately)."""
import sys, os, json, pandas as pd
root = sys.argv[1]; lake = os.path.join(root, 'data-lake', 'lake'); out = os.path.join(root, 'pipeline', 'validation'); os.makedirs(out, exist_ok=True)
ft = pd.read_parquet(os.path.join(lake, 'ft_enriched.parquet'), columns=['id', 'intitule', 'is_tech', 'ai_any', 'ai_core', 'ai_terms', 'canon', 'romeLibelle'])
txt = pd.read_parquet(os.path.join(lake, 'ft_postings.parquet'), columns=['id', 'description']).set_index('id').description
strata = [('ai_core', ft[ft.ai_core], 300), ('ai_text', ft[ft.ai_any & ~ft.ai_core], 300), ('tech_noai', ft[ft.is_tech & ~ft.ai_any], 200), ('other', ft[~ft.is_tech & ~ft.ai_any], 200)]
rows = []
for name, d, n in strata:
    s = d.sample(min(n, len(d)), random_state=42)
    for r in s.itertuples():
        rows.append({'id': r.id, 'stratum': name, 'title': r.intitule, 'rome': r.romeLibelle, 'text': (txt.get(r.id) or '')[:5000], 'label_is_tech': bool(r.is_tech), 'label_ai_any': bool(r.ai_any), 'label_ai_core': bool(r.ai_core), 'label_canon': r.canon, 'ai_terms': r.ai_terms})
df = pd.DataFrame(rows).sample(frac=1, random_state=7).reset_index(drop=True); df['k'] = range(len(df))
df.to_parquet(os.path.join(out, 'sample_1000_with_labels.parquet'), index=False)
blind = df[['k', 'id', 'title', 'rome', 'text']]
for i in range(0, len(blind), 50):
    blind.iloc[i:i + 50].to_json(os.path.join(out, f'blind_{i // 50:02d}.jsonl'), orient='records', lines=True, force_ascii=False)
print('sample', len(df), df.stratum.value_counts().to_dict(), 'batches', (len(blind) + 49) // 50)
