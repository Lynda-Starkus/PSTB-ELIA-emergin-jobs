# ELIA — Emerging AI occupations in France: research plan v1

Author of this plan: Claude (working session of 14 October 2026), for validation by Linda Belkessa.
Status: **draft for validation**. Everything below is executed with the defaults marked "default" unless you change them. Section 8 lists exactly what I need from you.

---

## 0. Reality check from today's data reconnaissance

I probed every source that the previous attempt listed plus the mass sources it did not use. These are measured numbers, not estimates.

| Source | What it gives | Measured volume (14 Oct 2026) | Full description? | Status |
|---|---|---|---|---|
| France Travail API Offres v2 (your key works) | All sectors, 36 fields incl. description, ROME, NAF, contract, salary, experience, commune | **481,494 live offers**; ~15–25k new offers per day; stock covers mostly June–Oct 2026 | Yes (median 1.3k chars) | Harvest launched today (full stock, day × region slicing) |
| HuggingFace `France-Travail-ML` dumps (Apache-2.0) | Same API, archived Jan–Jun 2026 | **601,213 offers** | Yes | Downloaded (730 MB parquet) |
| Choisir le Service Public (DGAFP, data.gouv) | Public sector, Dec 2022 → Sep 2026, weekly archives | **~2.6M rows** (titles, métier, category, location, level; **no description**) | No | Downloading all 6 archives |
| Adzuna France API (your key works) | Private boards aggregate | **1,025,829 live ads**, 16,050 in `it-jobs` | Truncated to 500 chars | IT category harvest planned |
| Hacker News "Who is hiring" (cached by the previous attempt) | International tech, 2011 → 2026 | **91,660 posts** | Yes | Available |
| Web Data Commons JobPosting (schema.org from Common Crawl) | Global, yearly | 4–5M postings/year globally but only **~100k/yr** French-hosted | Yes | Not worth it alone |
| Common Crawl archives (direct) | Historical pages of WTTJ, Indeed FR, APEC, HelloWork, free-work, LinkedIn | Index server timed out today; volumes unknown | Yes | To be re-probed |
| DARES **JOCAS** (daily scraping of the main French boards since 2018) | The reference French OJA database | Millions/year, all sectors | Yes | **Requires an access request** (DARES / Adisp / CASD) |
| CEDEFOP–Eurostat **Skills-OVATE / WIH** | 32-country OJA, ISCO × ESCO skills × NUTS-2, quarterly | Aggregates only; microdata on request to the WIH team | n/a | Aggregates usable for benchmarking |
| Lightcast France (PwC AI Jobs Barometer uses it) | 45k sites, ESCO/ISCO-coded | ~166k AI-related FR postings in 2024 (PwC) | Yes | Commercial licence, contact sales-europe@lightcast.io |

**Two consequences for the pitch.**

1. Tech is a small share of French postings: in the France Travail corpus, ROME M18 (informatique) is **1.6 %** of offers and postings mentioning AI are **0.9 %**. Across the open sources we can reach in weeks, "3 million **tech** job descriptions in France" is not attainable; roughly 100–150k tech descriptions per year is what the open French flow contains.
2. "**3+ million job postings in France**" (all sectors, 2022–2026) is attainable now: FT 2026 stock + HF dumps (~1.0M with descriptions) + CSP public sector (2.6M titles with metadata) + Adzuna (1.0M, short text). The tech/AI sub-corpus is then ~150–200k postings with full text, which is in line with the published literature (Bäck et al. 2021 used 480k Finnish ads for all sectors; Alekseeva et al. 2021 used Burning Glass).

**Default pitch I will build towards:** "We analysed more than 3 million job postings published in France between 2022 and 2026, isolated 150,000+ tech postings and 30,000+ AI postings with their full text, and tracked 15 years of international tech hiring (Hacker News, 91,660 posts) to date the emergence of every AI role."

If you want the literal "3M tech descriptions" claim, the only routes are JOCAS (free for research but months of procedure) or Lightcast (paid). Both are in the inputs list (Section 8).

---

## 1. Data strategy (three tiers)

**Tier A — open, harvested now (weeks 1–2).**
- France Travail API: full live stock today, then a **daily incremental harvest** (new offers by `minCreationDate`, ~20k/day). A scheduled job is in `pipeline/`. After 6 months this alone adds ~3.5M descriptions.
- HuggingFace FT dumps (Jan–Jun 2026).
- CSP archives 2022–2026 (public sector; titles, métier, catégorie, lieu, niveau).
- Adzuna FR: `it-jobs` category in full (16k, with company, salary estimates), plus monthly counts per title for all categories.
- Hacker News 2011–2026 (international reference series).
- Taxonomies: ROME 4.0 (data.gouv, 1,911 fiches / 14,301 appellations, with competences), ESCO 1.2 (13.9k skills, French labels), ISCO-08.

**Tier B — archival reconstruction of French tech history (weeks 2–6).**
- Common Crawl extraction of job pages of French boards (schema.org JobPosting in HTML), 2017–2026, for WTTJ, APEC, HelloWork, free-work, Indeed FR, LinkedIn public pages. Legally clean (archived public pages, research use). Volume to be measured once the index responds; this is the only open route to a French time series before 2026.
- DARES "offres collectées" monthly series and Skills-OVATE aggregates for macro validation.

**Tier C — partnership data (months).**
- JOCAS (DARES) access request; Lightcast academic quote; APEC and WTTJ data partnerships (ELIA letterhead). These upgrade the claim to several million tech descriptions and give the 2018–2026 French series.

**Legal and ethical framing.** API terms (France Travail, Adzuna) allow research use; CSP and ROME are Licence Ouverte; Common Crawl is public archival data; no personal data is kept (contact fields dropped at ingestion); employer names kept only for aggregate statistics.

---

## 2. Scientific protocol (rigour)

1. **Corpus construction.** Unified schema (`posting_id, source, title, text, date_posted, employer, naf, rome, contract, experience, salary_min/max, lat/lon, dept, region`). Deduplication at three levels: exact ID, exact text hash, near-duplicate (MinHash on title+text, Jaccard ≥ 0.9), and cross-source dedup for FT partner reposts. Language identification (fastText lid.176), keeping French and English.
2. **Scope definition, pre-registered.** Three nested sets with explicit rules written before any result is read: (i) *Tech* = ROME M18xx ∪ M14 data roles ∪ lexical tech titles; (ii) *AI-related* = ≥1 AI-skill mention in text (ESCO AI skill cluster + curated lexicon with homonym exclusions such as "IA-IPR"); (iii) *AI-core* = AI term in the **title** or ≥3 distinct AI skills in text. Sensitivity analysis on the thresholds.
3. **Title normalisation.** Gender marks (H/F, (e)), seniority tokens, locations, contract tokens removed; canonical title via rules + embedding clustering (multilingual-e5-large on the two L40S GPUs), manual review of the top 500 clusters.
4. **Skill extraction.** Two independent extractors: (a) ESCO/ROME lexical matcher with French and English surface forms; (b) embedding matcher (sentence chunks → nearest ESCO skill, cosine ≥ τ calibrated on 1,000 annotated postings). Agreement between extractors is reported; disagreements adjudicated with an LLM judge (Claude) **only on a held-out validation sample**, never to produce the published numbers. Skills aggregated into families (ESCO hierarchy: ML/AI, data engineering, software, cloud/MLOps, product, governance/ethics/regulation, domain knowledge, transversal).
5. **Emergence measurement (the methodological contribution).** For each canonical title t and month m: volume, share of tech postings, employer breadth (number of distinct employers), geographic breadth (departments), persistence (months with ≥1 posting in the last 12). An **Emergence Index** combines first-appearance date, 12-month growth (log-ratio with Bayesian shrinkage for small counts), breadth and persistence; titles are classified into lifecycle stages (*appearing, diffusing, established, fading, renamed*) with transition rules. Renaming is detected when two titles have skill-profile cosine ≥ 0.9 and anti-correlated volumes.
6. **Statistics.** Bootstrap 95 % CIs on all shares (1,000 resamples by employer cluster); seasonality handled with 3-month centred means and month fixed effects; source fixed effects in every regression; counts below 10 suppressed in publication. Changes before/after November 2022 tested with interrupted time series on the HN series and on CSP.
7. **Validation.** Stratified sample of 1,000 postings annotated by 2 annotators (AI-related yes/no, canonical title, up to 5 skills); Cohen's κ reported; precision/recall of the classifiers against this sample. External validation of volumes against DARES monthly series, Skills-OVATE France aggregates and the PwC/Indeed figures.
8. **Reproducibility.** DuckDB lake on `data-lake/`, versioned scripts in `pipeline/`, a frozen corpus snapshot with hash and a data statement in the paper appendix; code and aggregated data released with the paper.

---

## 3. Research questions and target analyses

| RQ | Question | Analyses and plots | Why interesting / expected non-obvious finding |
|---|---|---|---|
| RQ1 | Which AI job titles emerged in France since 2022, when, and are they new roles or renamed ones? | Emergence Index ranking; first-appearance timeline (Fig. 1 dumbbell); renaming map (skill-profile cosine vs volume anti-correlation) | Hypothesis: most "new" titles are relabels (Data Scientist → ML Engineer → AI Engineer); a minority (Forward Deployed Engineer, Agent Engineer, AI Governance/Compliance) are structurally new |
| RQ2 | What is the skill architecture of AI jobs, by family, and how does it differ from classical tech jobs? | Skill-family distributions (stacked bars, 95 % CI); radar charts per role; skill co-occurrence network with community detection | Expected: engineering/MLOps skills outweigh modelling skills in AI postings; governance/regulatory skills (AI Act) appear earlier in France than internationally |
| RQ3 | How fast do AI roles diffuse across employers, sectors (NAF) and territory, and who hires them? | Diffusion curves (employer breadth over time), sector heatmap, regional map (shares and location quotients), employer concentration (Gini / top-10 share) | Expected: AI demand concentrates in IT consulting (ESN) rather than product companies, and in Île-de-France; public sector lag quantified with CSP |
| RQ4 | Do AI roles pay a premium and demand more experience than comparable tech roles? | Salary distributions (FT salary field, Adzuna), hedonic regression with region, contract, experience, employer size; experience requirement shares | Expected: a premium of 10–20 % that shrinks for "AI-washed" titles; entry-level share lower than in classical dev roles |
| RQ5 | How does the French trajectory compare with the international frontier? | HN 2011–2026 series by family (streamgraph), lead/lag estimation (cross-correlation of first-appearance dates), AI share of tech postings FR vs HN | Expected lag of 6–18 months FR vs HN for new titles; faster for roles tied to regulation |
| RQ6 | Which titles are fading and what replaces them? | Lifecycle transitions (Sankey), prompt-engineer case study | Expected: prompt engineering absorbed into other roles within 24 months |
| RQ7 (exploratory) | Can emergence be predicted early? | Survival model on 2023–2024 cohorts (which appearing titles reached "established"), features: breadth, skill novelty, employer type | Policy value: an early-warning indicator for training providers (PST&B) |

Deeper descriptive layers that go into the paper and the website: distribution of contract types, remote/hybrid mentions, language of postings, required diplomas, the "AI mention outside tech" share by sector (AI diffusion into non-tech jobs, which the CSP + FT all-sector corpus uniquely allows).

---

## 4. Research paper

**Target (default): *Technological Forecasting and Social Change* (Elsevier), FNEGE rank 2 / CNRS 2 (2022 lists), Scopus Q1, ABS 3.** It publishes exactly this type of work (Bone, Stephany & Ehlinger 2025, "Skills or degree? Skill-based hiring for AI and green jobs", TFSC 214; several OJA-based skill-demand studies), accepts 7–10 page empirical contributions, and values the methodological indicator plus policy relevance. Alternatives if you prefer: *Research Policy* (FNEGE 1, harder, more theory), *Journal of Business Research* (FNEGE 2), *Labour Economics* (economics audience), *International Journal of Information Management* (FNEGE 2, IS audience). Template: Elsevier `elsarticle`, 1.5-column preprint style, author-year citations.

**Outline (7 pages).** 1 Introduction (RQs, contributions) · 2 Related work (new work and emerging occupations; OJA-based AI skill demand; French and European evidence) · 3 Data (sources, pipeline figure, corpus statement table) · 4 Method (scope rules, skill extraction, Emergence Index and lifecycle; conceptual diagram) · 5 Results (RQ1–RQ6, 5 figures + 3 tables) · 6 Discussion and implications (training, policy, firms) · 7 Conclusion and limitations. Appendix online: annotation protocol, lexicon, robustness.

**Figures planned.** Fig. 1 pipeline + lifecycle diagram (TikZ); Fig. 2 emergence timeline (dumbbell/first appearance vs breakout, FR vs HN); Fig. 3 skill-family distributions with CIs + radar panel per role; Fig. 4 diffusion curves and sector × region heatmap/map; Fig. 5 salary and experience premium (forest plot); Fig. 6 lifecycle Sankey. Tables: corpus statement; top-25 emerging titles with index components; classifier validation (κ, P/R).

The paper draft is written with your EJOR style (short declarative sentences, RQ list, enumerated contributions, measured numbers in the abstract, a "status of this draft" box marking preliminary numbers).

never use tikz generate and plots in high quality all plots and conceptual famepwk 
---

## 5. One-pager (journalists and general public, French, PST&B identity)

Results to feature (chosen to be visual and quotable): (1) the headline count "3 millions d'offres analysées"; (2) the AI share of postings and its growth (one big number + sparkline); (3) the **five roles that did not exist before 2022** with their first-appearance month; (4) the **skills radar** of the AI engineer versus the data scientist; (5) the **map** of where AI hires (Île-de-France share, top-5 regions); (6) **salaries**: median AI vs tech; (7) the **fading** title (prompt engineer) as the counter-intuitive story; (8) a small "how we did it" pipeline strip. Format: A4 portrait, PDF + PNG + HTML, brand tokens from `assets/brand.json` (violet #6520ff, rose #ff1845, Archivo + Spline Sans Mono), fewer than 150 words.

---

## 6. Website (decision of 15 Oct 2026: the zip's page, verbatim, on the new data)

Linda rejected a redesigned page: the observatory is the exact page delivered in the zip (`_prior/PSTB-ELIA-jobs/index.html`, seven scenes: ouverture, panorama épinglé, accélérations, France, carte, détection d'intitulés, référentiel, méthodologie, with theme switch and guided tour). Only the data and the data-driven texts change:

1. Inputs regenerated from the lake in the zip's own schemas (`pipeline/site/build_ft.py`, `build_csp.py`, `build_adzuna_corpus.py`; Adzuna refreshed through the zip's `tools/ingest_adzuna.mjs`): France Travail counts per title on the live stock (phrase or title match, all aliases), regions, quality, 1 075 585 FT titles + 1 614 346 CSP titles + 11 895 Adzuna titles for the discovery mining, public-sector monthly series by region.
2. The zip's chain rebuilt unchanged: `node tools/build_data.mjs` (HN series from the 2011–2026 cache) → `node tools/mine_discovery.mjs` → `node tools/build.mjs` → `python tools/video/build_outcomes.py` → `python tools/update_tour.py` (rewrites the guided-tour chapter texts from the new numbers) → `node tools/build.mjs`; one command: `bash tools/run_chain.sh` in `website/`.
3. Headless check `python tools/test_page.py` (console errors, hero counters, scene screenshots, tour).
4. Later additions (explorer, comparator, skills network, lifecycle Sankey) will be proposed as extra scenes in the same visual grammar, never as a new layout. The first redesigned version is archived in `website_v2_claude/` for reference only.
7. **Baromètre mensuel** auto-generated (new titles this month, movers).
8. **Méthodologie et données** page with corpus statement, sources status, download of aggregated CSVs, citation.
9. FR/EN toggle, light/dark themes (kept), shareable deep links per view, accessibility pass (contrast, keyboard).
10. Embedded guided tour (kept) updated to the new results.

Comments: All these funcs need to have viz which is advaned highly interactive ... etc, there needs also a functionality which shows scrollytelling and especially the stockmarket of jobs please 

---

## 7. What I execute now, with defaults

- Harvest FT stock (running), CSP (running), Adzuna IT, HN, ROME 4.0, ESCO; build the DuckDB lake; run dedup, language ID, scope classification, title normalisation, skill extraction v1; compute Emergence Index v1; produce all figures; write the paper draft (LaTeX, elsarticle), the one-pager, and the website v2 in `research-paper/`, `dissemination/`, `website/`.
- Numbers in the draft are labelled preliminary until the daily harvest and the archival reconstruction extend the series.

## 8. Inputs I need from you (none blocks the work above)

1. **Pitch decision**: accept "3M+ job postings in France, 150k+ tech, 30k+ AI, full text" (default) or require "3M tech descriptions" (then approve the JOCAS request and/or a Lightcast quote).

take th most rich and complete option

2. **Target journal**: TFSC (default) or one of the alternatives in Section 4.
3. **Access requests you must sign/send** (I draft the emails): DARES for JOCAS; CEDEFOP WIH team for Skills-OVATE microdata; Lightcast Europe for an academic quote; optional APEC and WTTJ partnerships.
4. **Annotation**: two people (or you + one colleague) for the 1,000-posting validation sample, ~6 hours each; or authorise me to use an LLM judge for a first pass with you validating 200 items.

LLM JUDGE 

5. **Compute/credentials**: France Travail and Adzuna keys are in `.env` (copied from the zip). A daily harvest should run on this machine (I will leave a scheduled task); confirm it can stay on.

yes 
6. **Author details**: ORCID, corresponding author e-mail, funding statement, and whether Armand Derhy's affiliation is ELIA/PST&B only.
yes armand elia pstb only 
7. **Style assets**: the official PST&B charte (logo files, fonts) if one exists beyond `assets/brand.json`.
8. **Website hosting**: where the site is deployed (static host, pstb.fr subdomain?) and whether a monthly refresh job is acceptable.
for now free tier hoting later we will put it in ours servers
9. **Language of the one-pager**: French (default) or bilingual.
french


COMMENT GENERAL: ALWAYS KEEP PROGRESS BAR AND REMOTE CONTROL I NEED TO HAVE A DASHBOARD TO SUPERVISE EVERYTHING CHECK PLOTS RESULTS AND PROGRESS OF DIFFERENT TASKS

---

## 10. Deliverables produced on 14 October 2026 (v0, all regenerable)

| Deliverable | Where | State |
|---|---|---|
| Data lake | `data-lake/lake/*.parquet`, `data-lake/lake/results/*.csv`, `summary.json` | FT 1 075 585 (full text) · CSP 1 614 346 · HN 91 851 · Adzuna IT 11 895 · ESCO 14 125 · ROME 4.0 |
| Pipeline | `pipeline/*.py`, `pipeline/*.mjs` | harvest (stock + daily task `ELIA-FT-daily-harvest` 03:30), build, classify, analysis, emergence, discovery, skills, validation, figures, paper numbers, site data, one-pager, dashboard |
| Validation | `pipeline/validation/` (`judge_*.jsonl`, `check_list_for_linda.xlsx`, round 1 archived) | AI mention P 90 % / R 98 % (κ 0.86); tech P 88 % / R 92 %; AI title P 79 % / R 96 %; 226 disagreements to check |
| Paper | `research-paper/main.tex` (elsarticle 5p two-column, TFSC), `numbers.tex` (auto), `refs.bib`, `fig/` (11 figures PDF/PNG/SVG, 600 dpi), `main.pdf` | v0.2 compiled (12 pages); figures redesigned on 15 Oct to journal conventions (`research-paper/FIG_BRIEF.md`, `pipeline/figstyle.py`): Figure 1 is now a data-drawn study-design figure (sources on one time axis, nested scopes, index read on a real series, lifecycle stages) |
| One-pager | `dissemination/onepager/onepager.{html,pdf,png}` (A4, French) | v0.2 in the zip's visual language (paper sheet, Bricolage Grotesque / Hanken Grotesk, hairline rows, SVG sketches drawn from the data) |
| Requests | `dissemination/requests/01_DARES_JOCAS.md`, `02_CEDEFOP_WIH.md`, `03_Lightcast_academic.md` | to sign and send |
| Website | `website/index.html` (the zip's page, unchanged) + `website/data/data.js` (rebuilt from the lake, 360 KB) + `website/dist/artifact.html` | hero: 2 701 826 titles analysed, 91 660 international posts, 8 633 private-sector AI ads, France Travail live AI offers; discovery over 2.7 M titles; public-sector monthly map 2022–2026; 19 tour chapters regenerated from the data |
| Dashboard | `dashboard/index.html` (artifact https://claude.ai/artifact/3evi7HRxjAfcoSJusuQ7Vp) | updated at each milestone |
| Website preview | artifact https://claude.ai/artifact/CaXsnhprsdF1zcpYjXJToU | private preview of `website/` |

**Known limits of v0 (next iterations):** French time series limited to 2026 until the daily harvest and JOCAS/Lightcast arrive; embedding-based skill extractor and renaming test not yet run; hedonic salary regression pending; HN texts truncated at 1 100 characters (re-crawl planned); paper to be tightened to the 7-page target and proof-read; 200 validation items to be checked by Linda.

## 9. Decisions recorded from your comments (14 Oct 2026, evening)

| Topic | Decision | How it is applied |
|---|---|---|
| Figures | **No TikZ.** All plots and conceptual diagrams are generated as high-quality vector/raster images (matplotlib/plotly → PDF + PNG + SVG), including the pipeline and lifecycle diagrams. | `pipeline/figures/*.py`, outputs in `research-paper/fig/` |
| Pitch / data | **Richest and most complete option**: open sources now + Common Crawl reconstruction + JOCAS and Lightcast requests (emails drafted for you in `dissemination/requests/`). | Section 1, all three tiers |
| Validation | **LLM judge** for the annotation of the validation sample, with 200 items for you to check. | `pipeline/validation/` |
| Daily harvest | Yes, this machine stays on; a scheduled task runs the France Travail harvest daily. | `pipeline/schedule_daily.ps1` |
| Authors | Armand Derhy: ELIA, PST&B only. | paper front matter |
| Hosting | Free-tier static hosting for now (Cloudflare/GitHub Pages ready), own servers later. | `website/` is a static bundle |
| One-pager | French. | `dissemination/onepager/` |
| Website | Every functionality gets an advanced, highly interactive visualisation; a scrollytelling layer is kept; a new **"Bourse des métiers"** (stock-market view of job titles: tickers, index value, monthly variation, sparklines, sector indices, top movers) is added. | Section 6 item 11 |
| Supervision | A **dashboard** with progress bars per task, latest plots, key numbers and logs, published as a private Claude artifact and regenerated at each milestone (`dashboard/`). You can follow it remotely. | `pipeline/dashboard.py` |