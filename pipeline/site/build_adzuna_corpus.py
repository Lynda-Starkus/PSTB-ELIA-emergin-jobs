# -*- coding: utf-8 -*-
"""Regenerate the private-sector title corpus of the ELIA observatory from the raw Adzuna harvest.

    website/data/corpus_adzuna.json   {collected_at, titles:[[title, year], ...]}

Schema and semantics: website/SPEC_DATA.md.  Reference file: _prior/PSTB-ELIA-jobs/data/corpus_adzuna.json
(written by _prior/PSTB-ELIA-jobs/tools/ingest_adzuna.mjs, which kept [title without HTML tags, year of `created`]
for ~1 500 ads returned by the "intelligence artificielle" / "machine learning" API searches).

Here the corpus is the whole IT category harvested on 14 October 2026
(data-lake/raw/adzuna/it_jobs_2026-10-14.ndjson, 11 895 distinct ads, one JSON object per line):
    title   -> HTML tags removed (same regex as the zip script), ads without title skipped
    created -> year as an integer (0 when missing, as in the zip script)
Output is compact JSON (no spaces), UTF-8, non-ASCII characters kept as is, like JSON.stringify.

Run:
    G:/Linda/Bureau/PSTB/ELIA/metiers-ia-emergents/.venv/Scripts/python pipeline/site/build_adzuna_corpus.py [project_root]
"""
import json
import re
import sys
from pathlib import Path

COLLECTED_AT = "2026-10-14T18:52:00Z"
RAW = Path("data-lake") / "raw" / "adzuna" / "it_jobs_2026-10-14.ndjson"
OUT = Path("website") / "data" / "corpus_adzuna.json"
TAG = re.compile(r"<[^>]+>")


def year_of(created):
    """Year of the `created` timestamp as an int; 0 when absent or malformed (zip script: `slice(0, 4) * 1 || 0`)."""
    head = str(created or "")[:4]
    return int(head) if head.isdigit() else 0


def main(root):
    titles = []
    n_ads = 0
    with open(root / RAW, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            ad = json.loads(line)
            n_ads += 1
            title = ad.get("title")
            if not title:
                continue
            titles.append([TAG.sub("", str(title)), year_of(ad.get("created"))])
    out = root / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        json.dump({"collected_at": COLLECTED_AT, "titles": titles}, fh, ensure_ascii=False, separators=(",", ":"))
    years = {}
    for _, y in titles:
        years[y] = years.get(y, 0) + 1
    print(f"{OUT.as_posix()}: {len(titles)} titles from {n_ads} ads; years {dict(sorted(years.items()))}")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2])
