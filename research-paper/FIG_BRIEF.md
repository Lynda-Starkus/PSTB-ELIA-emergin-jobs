# Figure brief — ELIA paper (Technological Forecasting and Social Change)

Target look: figures of *Nature*, *Science* or *QJE* papers. Quiet, precise, information-dense, nothing decorative.
A reader should understand each panel from its marks and three or four short labels. The caption (in main.tex) carries the title.

## Non-negotiable rules (apply to every figure)

1. Use `pipeline/figstyle.py` (call `F.setup()` first, save with `F.save(fig, outdir, name)`; place axes with `fig.add_axes` or `F.axes_mm`).
   Arial 7 pt, tick labels 6 pt, panel letters `F.panel(fig, ax, 'a')` bold lowercase 8 pt outside the top-left corner of each panel.
2. No chart titles inside the figure. No sentences inside the figure. Labels of at most four words. No text boxes, no bounding boxes around text, no legends with frames.
3. Only left and bottom spines (0.5 pt), ticks outward, no gridlines. Bars and areas start at zero. Axis labels in sentence case with the unit in parentheses: `Share of postings (%)`.
4. Colours (from figstyle): violet = AI mentioned anywhere, rose = AI in the job title, slate = technology jobs / baseline, light grey = everything else; teal and amber only when a third or fourth category is unavoidable. Family colours from `F.FAMILY`, stage colours from `F.STAGE`. At most four hues per panel. No gradients, shadows, rounded bars, 3-D, pies, radars.
5. Direct labelling: put the series name (and final value when useful) at the right end of a line or next to a dot, with `F.label_end`. Use a legend only when there are more than four series, frameless and placed in empty space.
6. At most two annotations per panel, with thin leaders (`F.leader`). Event markers: a single hairline at November 2022 labelled `ChatGPT` in 6 pt grey; nothing else.
7. Numbers: thousands with thin spaces (`F.thousands`), percentages with one decimal when below 10. Counts ("n = …") only when essential, in 6 pt grey at the end of the row.
8. Sizes: double column 183 mm wide (`F.W2`), single column 89 mm (`F.W1`); heights given below. Keep margins tight but never clip labels (check the PNG).
9. Ranked categories: dot plots or horizontal bars sorted by value, confidence intervals as thin grey horizontal lines, the reference value as one thin dashed hairline labelled once.
10. Language of all labels: English (region and département names stay French). Sector names (NAF) translated to short English labels.
11. Keep the exact output file names and the PDF + PNG + SVG triplet. Do not touch main.tex.
12. After saving, open the PNG (Read tool) and check: nothing overlaps, nothing is clipped, no empty space larger than a panel, text sizes consistent, colours as specified, no legend box, no title. Iterate until it is right (at least two passes).

What to avoid, because the previous versions were rejected for it: titles inside panels, legends in boxes, monospace text columns pasted in the plot, boxes with bullet text, many colours, radars, long annotations, decorative backgrounds.

## Data (all under data-lake/lake/results unless stated)

* hn_monthly.csv (month, n, ai, core, ai_share, core_share, ai_share_ma3, core_share_ma3) — exclude the incomplete month 2026-10.
* hn_family_share_monthly.csv (month × family share), hn_canon_titles.csv (canon, label, family, total, first_seen, first_seen_5, last12, prev12, growth_12m, share_last12_pct).
* emergence_index.csv (canon, label, family, E, stage, N, G, B, P, *_rank, hn_first_5, hn_last12, hn_prev12, hn_employers_12m, fr_postings_2026, fr_employers, fr_depts, growth_12m).
* ft_ai_share_by_naf.csv / _by_region.csv / _by_dept.csv / _by_contract.csv / _by_size.csv (index = category; n, k, share, lo, hi as fractions).
* ft_segments.csv (segment rows; sal_p25, sal_median, sal_p75, cdi, exp_required, debutant, n, sal_n), ft_canon_titles.csv (canon index; n, employers, depts, sal_median, sal_n, cdi_share, exp_required, idf_share, label, family).
* data-lake/lake/ft_enriched.parquet (segment, sal_mid, experienceExige D/S/E, canon, region, dept) for distributions.
* csp_monthly.csv (month; n, tech, ai), csp_yearly.csv (year; ai_per_10k), csp_ai_canon.csv (canon, count), csp_ai_by_versant.csv.
* discovery_hn_ngrams.csv (ngram, n, first_seen, last12, prev12, growth, employers, employers_12m), discovery_ft_ngrams.csv (ngram, n, employers, depts, canon).
* skills_profile_by_segment.csv, skills_profile_by_canon_ft.csv, skills_profile_by_canon_hn.csv, skills_profile_hn_ai_by_year.csv (columns = ten families of pipeline/skills.py FAMILIES), skills_cooccurrence_ai_ft.csv (square matrix, diagonal = counts).
* data-lake/geo/departements.geojson (properties code, nom).
* Labels of canonical titles: pipeline/lexicon.py CANON_LABEL / CANON_FAMILY. Existing scripts pipeline/fig_*.py show how each file was read; reuse the data access, replace the design.

## Per-figure specification

**fig3_hn_series** (183 × 95 mm, panels a above b). a: two lines, 3-month centred mean, share of posts mentioning AI (violet) and share whose role title is an AI title (rose), April 2011 to September 2026; direct labels with the final values at the right end; ChatGPT hairline; y from 0 to 70 %. b: stacked area of the AI/data title families as share of posts, collapsed to five groups: "AI engineering" (AI engineering + new titles) rose, "ML engineering" light rose, "Other AI roles" (research, architecture & leadership, business, governance, training) violet, "Data roles" (science, engineering, analytics, leadership) blue #2b8fd6, "Other AI-labelled" grey; direct labels at the right end of each band (only if the band is thick enough, else a short leader). Thin white separators between bands.

**fig4_hn_first_appearance** (183 × 100 mm). Dumbbell timeline, one row per canonical title (exclude ai_other), sorted by the month of the fifth post: open circle = first post, filled circle = fifth post with area proportional to posts in the last 12 months; colour by group: AI titles rose, data titles blue, other grey (three colours only). A right-hand column in 6 pt grey with the posts in the last 12 months. ChatGPT hairline. A one-line key under the axis in 6 pt grey.

**fig5_ft_ai_share_breakdowns** (183 × 115 mm, 2 × 2 panels a–d). Dot plots sorted by share with Wilson 95 % intervals as thin grey lines; one hue (violet); the national share (0.76 %) as a dashed hairline labelled once per panel in 6 pt grey; n at the far right in 6 pt grey only for panel a. a: sector (NAF, translated: Information & communication, Real estate, Professional & technical services, Finance & insurance, Education, Manufacturing, Public administration, Transport, Water & waste, Arts & entertainment, Mining, Other services, Trade, Agriculture, Energy, Health & social work, Administrative & support services, Accommodation & food, Construction; drop T-U). b: regions (keep French names; drop Mayotte if n of AI = 0). c: contract type (Permanent, Fixed-term, Temp agency, Freelance, Commercial agent, Franchise, Seasonal, Intermittent, Insertion). d: establishment size as a dot plot ordered by size class from the smallest (top) to the largest (bottom), labels like "1–2", "3–5", … "10 000+", with "None / 0" first.

**fig6_ft_map_dept** (89 × 92 mm). Choropleth of metropolitan départements (drop 97x), sequential single-hue violet ramp from near-white to dark violet (use a power-norm 0.5 so that Paris does not flatten the rest), white boundaries 0.3 pt, no frame, no title. Compact horizontal colour bar bottom-left (3 ticks, label "Postings mentioning AI (%)"). Label the five highest départements directly on the map with thin leaders (Hauts-de-Seine, Paris, Essonne, Val-de-Marne, Yvelines or whatever the data says) in 6 pt.

**fig7_ft_salary_experience** (183 × 62 mm, a left wide, b right). a: posted annual salary by segment as range plots: thin grey line p10–p90, thick coloured line p25–p75, white-filled dot at the median, segments AI-core (rose), AI-related tech (violet), other tech (slate), AI mention non-tech (amber), all other (grey); median value in 6 pt at the right of each range, n in grey further right; x in k€, 10–100. b: experience requirement as 100 % horizontal stacked bars per segment: open to beginners (light grey), experience desired (slate 50 %), experience required (rose); percentages inside in 6 pt; category names written once above the first bar as direct labels.

**fig8_ft_canonical_titles** (183 × 95 mm). Three aligned columns sharing the y-axis (titles sorted by postings): a: postings 2026 as horizontal bars coloured by group (AI rose, data blue); b: distinct employers as dots; c: départements as dots; one thin grey vertical hairline per column at zero. Values at bar/dot ends only for column a. No monospace strings.

**fig9_csp_public_sector** (183 × 62 mm, a wide, b narrow). a: monthly AI mentions per 10 000 public-sector postings, light grey bars + rose 3-month centred mean; two thin slate linear trend segments (before and after November 2022) with 6 pt labels "trend before"/"trend after" and the slope per year; annual means as small ink numbers above each year. b: horizontal bars of the ten most frequent canonical titles in the public sector, coloured by group.

**fig10_emergence_index** (183 × 110 mm). a: Emergence Index as a dot plot (one dot per title, colour = stage, stage name in 6 pt in the stage colour right of the dot), sorted descending. b: the four components N, G, B, P as a heat strip of percentile ranks (light to violet) with the rank values in 5.5 pt (white on dark cells). c: two dot columns on log scales: posts in the last 12 months (HN) and French postings 2026, grey dots; column headers in 6 pt. Exclude ai_other and too-rare titles.

**fig11_discovered_titles** (183 × 72 mm). a: title n-grams first seen after November 2022 in international hiring: dot timeline, x = month of first appearance, y = n-grams ordered by first month, dot area ∝ posts, rose; the number of employers in 6 pt grey at the right margin; exclude n-grams containing "https", ".ai", "is ", "x". b: most frequent AI title n-grams in French AI-titled postings 2026: horizontal violet bars, employers and départements as two small grey numbers at the end.

**fig12_skills** (183 × 125 mm, 2 × 2 panels). a: skill families (rows) × segments as a dot plot: for each family four dots (AI-core rose, AI-related tech violet, other tech slate, AI mention non-tech amber) joined by a thin grey line from min to max; segment names as direct labels on the first row. b: dumbbell comparing two titles (AI engineer in rose, data scientist in blue) across the ten families, sorted by the AI-engineer value. c: skill content of international AI posts by year 2015–2026 as small multiples (2 rows × 3 columns of tiny panels, one family each: AI/ML modelling, Generative AI & LLM, Cloud/DevOps/MLOps, Data engineering, Software engineering, Governance), each with a single violet line, shared y 0–100 %, family name as a 6 pt label inside, ChatGPT hairline. d: co-occurrence network of the 30 most cited skills in French AI postings: nodes coloured by family (five grey-to-colour hues at most), edges thin grey with width ∝ Jaccard, labels 5.5 pt placed without overlap (increase repulsion, clamp to the panel), no frame, a two-line colour key in 6 pt text.
