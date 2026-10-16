# Data inputs of the ELIA observatory page (website/index.html)

The page `website/index.html` is the exact page delivered in the project zip (`_prior/PSTB-ELIA-jobs/index.html`). It must not be redesigned.
It reads one bundle, `website/data/data.js`, produced by the zip's own tools from JSON inputs in `website/data/`:

```
node tools/build_data.mjs      # .cache/hn/*.json + data/taxonomy.json + data/ft_fr.json (+ remoteok.json) -> data/series.json, data/data.js (window.ELIA_DATA)
node tools/mine_discovery.mjs  # data/corpus_ft.json + data/corpus_public.json + data/corpus_adzuna.json + .cache/hn -> data/discovery.json
node tools/build.mjs           # embeds sources.json, ft_regions.json, fr-regions.geojson, discovery.json, adzuna.json, csp_monthly.json, outcomes.json into data/data.js
python tools/video/build_outcomes.py   # -> data/outcomes.json (then node tools/build.mjs again)
```

The JSON inputs that must be REGENERATED from the new data lake (`data-lake/lake/*.parquet`) keep EXACTLY the schema of the
reference files in `_prior/PSTB-ELIA-jobs/data/` (same keys, same types, same nesting, same meaning). Reference examples:

* `ft_fr.json`      {collected_at, api, method, results:{<title_id>:{count, count_31j, terms:{<term>:count}}}}  (58 title ids = data/taxonomy.json titles)
* `ft_regions.json` {collected_at, api, titles_tracked:[{id,label,term}], regions:[{code,nom,total,recent,annee,titles:{<id>:{count,count_31j,count_annee}}}], quality:{total,cdi,debutants}, fde:{term,total,employers:[...]}}
* `corpus_ft.json`  {collected_at, calls, total, offers:[{id,t,d,r,c,dep}]}   t=title, d=YYYY-MM-DD, r=ROME code, c=contract code, dep=department
* `corpus_public.json` {collected_at, csp:[[title, year], ...], bpce:[], notes}
* `corpus_adzuna.json` {collected_at, titles:[[title, year], ...]}
* `csp_monthly.json` {collected_at, source, scanned, matched, no_region, months:[YYYY-MM...], regions:{<INSEE region code>:[count per month]}, total:[count per month]}
* `adzuna.json`     {collected_at, calls, global_count_ia, per_title:{<id>:{count, salary?:{p25,median,p75}}}, salary_ids:[...], companies:{fde:[{name,count}], ai_engineer:[...], agents:[...]}, locations:[{name,count}]}

## Data lake (Python, venv: G:/Linda/Bureau/PSTB/ELIA/metiers-ia-emergents/.venv/Scripts/python)

* `data-lake/lake/ft_postings.parquet` (1 075 585 France Travail offers, full text). Columns used: id, intitule, description, text (title + description, lower-cased), dateCreation, date_posted (timestamp), month, romeCode, typeContrat, experienceExige ('D' = débutant accepté, 'S', 'E'), entreprise.nom, dept (2-digit department, '2A','2B', '971'..'976'), ingest ('api:2026-10-14' = live stock harvested on 14 Oct 2026 = "offres en ligne"; 'hf:...' = archived dumps Jan–Jun 2026).
* `data-lake/lake/ft_enriched.parquet` same ids with is_tech, ai_any (AI mentioned), ai_core (AI in the title), region (region name), canon.
* `data-lake/lake/csp_postings.parquet` (1 614 346 public-sector postings): title, date_first_pub, date_posted, month, dept, versant, organisme, localisation.
* `data-lake/raw/adzuna/it_jobs_2026-10-14.ndjson` (11 895 Adzuna FR ads, IT category): title, created, company.display_name, salary_min, salary_max, location.area, description (truncated).
* Region mapping (department -> INSEE region code) as in `tools/ingest_csp_regions.mjs` (DEP2REG) and region names as in `tools/ingest_ft_regions.mjs` (REGIONS).

## Semantics to preserve

* "offres en ligne" (ft_fr.json counts, ft_regions.json) = the live stock only (ingest == 'api:2026-10-14'), collected_at = 2026-10-14T20:45:00Z.
  A term matches an offer when EITHER its words (stop-words dropped, accents and case ignored) occur in that order within a window of
  (number of words + 2) consecutive tokens of the title + description, OR all its words occur anywhere in the title alone. `count` = max over
  the title's terms; terms = [title_en, title_fr] + all aliases (deduplicated, length > 3, at most 6) for AI families, [title_en] for context families;
  `count_31j` = same restricted to date_posted >= collected_at - 31 days. (A plain bag-of-words over the whole text, as the France Travail API does,
  was tested and rejected: "Ingénieur de la connaissance" then matched 3 220 offers.)
* ft_regions.json: 10 tracked titles = top AI-family titles by ft_fr count (FDE forced in, as in the script); per region: count / count_31j / count_annee (created within 365 days);
  quality.total = sum of the tracked titles' ft_fr counts, cdi = matches with typeContrat == 'CDI', debutants = matches with experienceExige == 'D' (summed over tracked titles, on the best term of each);
  fde.employers = distinct entreprise.nom of the FDE matches (up to 10), fde.total = FDE count.
* corpus_ft.json: ALL 1 075 585 offers (both ingests), t = intitule, d = dateCreation[:10], r = romeCode, c = typeContrat, dep = dept; total = number of offers; calls = 0.
* corpus_public.json: ALL CSP postings as [title, year of date_first_pub or date_posted]; bpce = [] ; notes = 'CSP: archives Choisir le Service Public 2022-2026 (data.gouv.fr), via data lake ELIA'.
* csp_monthly.json: same lexical filter as `tools/ingest_csp_regions.mjs` (AI_LEX / AI_FALSE on the stripped title), month = date_first_pub (fallback date_posted), region from dept via DEP2REG; months from 2022-01 to 2026-09 (exclude the incomplete current month 2026-10); scanned = all rows, matched = AI rows, no_region = AI rows without region.
* corpus_adzuna.json: [title, year(created)] for the 11 895 raw ads.
* adzuna.json: preferably refreshed by `node tools/ingest_adzuna.mjs` (API keys in website/.env, ~117 calls, 2.6 s apart). If the API quota is exhausted (HTTP 429/403 repeatedly), build it from the raw ndjson (per_title counts by matching title_en / title_fr / aliases in the ad title, salaries p25/median/p75 from the midpoint of salary_min/salary_max of the matched ads, companies from company.display_name, locations from location.area[1]) and keep global_count_ia = 12860 from the reference file with a note.
