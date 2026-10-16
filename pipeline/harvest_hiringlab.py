#!/usr/bin/env python
"""Indeed Hiring Lab job postings tracker, France -> data-lake/raw/hiringlab/ and data-lake/lake/results/hiringlab_fr.csv

Source   : https://github.com/hiring-lab/job_postings_tracker  (folder FR/), files published by Indeed Hiring Lab.
Licence  : Creative Commons Attribution 4.0 International (CC BY 4.0) - cite "Indeed Hiring Lab" as the source.
Content  : daily index of job postings on Indeed (7-day trailing average, seasonally adjusted, 1 Feb 2020 = 100), refreshed weekly:
           aggregate_job_postings_FR.csv (total / new postings, SA and NSA), job_postings_by_sector_FR.csv (34 sectors),
           regional_fr.csv (12 regions, published with region codes only).
Branch   : the brief says "main" but the repository's default branch is "master" ("main" answers 404): the script probes
           main, then the default branch reported by the GitHub API, then master.

Usage    : python pipeline/harvest_hiringlab.py [project_root] [--force]
Idempotent: a file is downloaded only when its git blob sha differs from the one on GitHub (--force downloads again);
           the long CSV is rebuilt on every run; a small manifest records licence, download date, hashes and row counts.
Optional : GITHUB_TOKEN in .env or in the environment lifts the 60 requests/hour limit of the GitHub API (4 requests are used).
"""
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO = "hiring-lab/job_postings_tracker"
FOLDER = "FR"
WANTED = ["aggregate_job_postings_FR.csv", "job_postings_by_sector_FR.csv", "regional_fr.csv"]
BRANCH_CANDIDATES = ["main", "master"]
UA = "ELIA-research-harvester/1.0 (academic study of emerging AI jobs in France; published files only)"
LICENCE = {
    "name": "Creative Commons Attribution 4.0 International",
    "spdx": "CC-BY-4.0",
    "url": "https://creativecommons.org/licenses/by/4.0/",
    "attribution": "Indeed Hiring Lab, Job Postings Tracker (https://github.com/hiring-lab/job_postings_tracker)",
}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def load_token(root):
    tok = os.environ.get("GITHUB_TOKEN", "")
    env = root / ".env"
    if not tok and env.exists():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"^\s*GITHUB_TOKEN\s*=\s*(\S+)\s*$", line)
            if m:
                tok = m.group(1).strip("\"'")
    return tok


def http_get(url, token="", tries=4, timeout=120, accept=None):
    """GET with retries; returns (status, bytes). 404 is returned, other HTTP errors are retried."""
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    if token and "api.github.com" in url:
        headers["Authorization"] = "Bearer " + token
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, b""
            last = f"HTTP {e.code}"
            if e.code == 403 and "api.github.com" in url:  # rate limit of the unauthenticated GitHub API
                last = "HTTP 403 (GitHub API rate limit?)"
                break
        except Exception as e:  # network error, timeout
            last = repr(e)
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    root = Path(args[0]).resolve() if args else Path(__file__).resolve().parent.parent
    raw = root / "data-lake" / "raw" / "hiringlab"
    res_dir = root / "data-lake" / "lake" / "results"
    raw.mkdir(parents=True, exist_ok=True)
    res_dir.mkdir(parents=True, exist_ok=True)
    logf = raw / "_stdout.log"

    def log(*a):
        line = " ".join(str(x) for x in a)
        print(line, flush=True)
        with open(logf, "a", encoding="utf-8") as f:
            f.write(f"{now_iso()} [hiringlab] {line}\n")

    token = load_token(root)
    started = now_iso()
    manifest_path = raw / "hiringlab_manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}

    # ---- repository facts: default branch, licence, last commit (GitHub API)
    default_branch, licence_api, pushed_at = None, None, None
    try:
        st, body = http_get(f"https://api.github.com/repos/{REPO}", token, accept="application/vnd.github+json")
        if st == 200:
            info = json.loads(body)
            default_branch = info.get("default_branch")
            licence_api = (info.get("license") or {}).get("spdx_id")
            pushed_at = info.get("pushed_at")
            log(f"repository: default branch '{default_branch}', licence {licence_api}, last push {pushed_at}")
    except Exception as e:
        log("GitHub API unavailable for repository info:", e)

    # ---- branch: probe the paths (main first, as in the brief, then the default branch, then master)
    cands = []
    for b in BRANCH_CANDIDATES[:1] + [default_branch] + BRANCH_CANDIDATES[1:]:
        if b and b not in cands:
            cands.append(b)
    branch = None
    for b in cands:
        st, _ = http_get(f"https://raw.githubusercontent.com/{REPO}/{b}/{FOLDER}/{WANTED[0]}", token)
        log(f"probe branch '{b}': FR/{WANTED[0]} -> HTTP {st}")
        if st == 200:
            branch = b
            break
    if not branch:
        log("ERROR: no branch serves FR/" + WANTED[0])
        sys.exit(1)

    # ---- folder listing (sha + size of every file) and last commit
    listing = {}
    try:
        st, body = http_get(f"https://api.github.com/repos/{REPO}/contents/{FOLDER}?ref={branch}", token, accept="application/vnd.github+json")
        if st == 200:
            listing = {x["name"]: x for x in json.loads(body) if x.get("type") == "file"}
            extra = sorted(n for n in listing if n.endswith(".csv") and n not in WANTED)
            log("FR folder:", ", ".join(f"{n} ({listing[n]['size']} B)" for n in sorted(listing)), ("| not downloaded: " + ", ".join(extra)) if extra else "")
    except Exception as e:
        log("could not list the FR folder through the API (continuing with the known file names):", e)
    commit = {}
    try:
        st, body = http_get(f"https://api.github.com/repos/{REPO}/commits/{branch}", token, accept="application/vnd.github+json")
        if st == 200:
            c = json.loads(body)
            commit = {"sha": c.get("sha"), "date": (c.get("commit", {}).get("committer") or {}).get("date")}
    except Exception as e:
        log("could not read the last commit:", e)

    # ---- download what changed
    files = []
    for name in WANTED:
        url = f"https://raw.githubusercontent.com/{REPO}/{branch}/{FOLDER}/{name}"
        dest = raw / name
        remote_sha = (listing.get(name) or {}).get("sha")
        local = dest.read_bytes() if dest.exists() else None
        if local is not None and remote_sha and blob_sha(local) == remote_sha and not force:
            data, status = local, "unchanged"
        else:
            st, data = http_get(url, token)
            if st == 404:
                log(f"{name}: not found on branch '{branch}' (skipped)")
                continue
            head = data[:200].decode("utf-8", "replace").splitlines()[0] if data else ""
            if not head.lower().startswith("date,"):
                raise RuntimeError(f"{name}: unexpected header {head!r}; previous file kept")
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, dest)
            status = "downloaded" if local is None else "updated"
        files.append({"name": name, "url": url, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "git_blob_sha": blob_sha(data), "status": status})
        log(f"{name}: {status} ({len(data)} bytes)")
    if not files:
        log("ERROR: nothing available")
        sys.exit(1)

    # ---- provenance copies: README (definitions) and LICENSE
    for src, dst in (("README.md", "_source_README.md"), ("LICENSE", "_source_LICENSE.txt")):
        try:
            st, body = http_get(f"https://raw.githubusercontent.com/{REPO}/{branch}/{src}", token)
            if st == 200:
                (raw / dst).write_bytes(body)
        except Exception as e:
            log(f"could not copy {src}:", e)

    # ---- long table: date, variable, value
    parts, per_file = [], {}
    by_name = {f["name"]: f for f in files}
    if "aggregate_job_postings_FR.csv" in by_name:
        a = pd.read_csv(raw / "aggregate_job_postings_FR.csv", dtype=str)
        for variable, label_sa, label_nsa in (("total postings", "aggregate", "aggregate (NSA)"), ("new postings", "aggregate (new postings)", "aggregate (new postings, NSA)")):
            sub = a[a["variable"] == variable]
            parts.append(pd.DataFrame({"date": sub["date"], "variable": label_sa, "value": sub["indeed_job_postings_index_SA"]}))
            parts.append(pd.DataFrame({"date": sub["date"], "variable": label_nsa, "value": sub["indeed_job_postings_index_NSA"]}))
        per_file["aggregate_job_postings_FR.csv"] = a
    if "job_postings_by_sector_FR.csv" in by_name:
        s = pd.read_csv(raw / "job_postings_by_sector_FR.csv", dtype=str)
        name = s["display_name"].where(s["variable"] == "total postings", s["display_name"] + " (new postings)")
        parts.append(pd.DataFrame({"date": s["date"], "variable": name, "value": s["indeed_job_postings_index"]}))
        per_file["job_postings_by_sector_FR.csv"] = s
    if "regional_fr.csv" in by_name:
        r = pd.read_csv(raw / "regional_fr.csv", dtype=str)
        parts.append(pd.DataFrame({"date": r["date"], "variable": "region:" + r["region"], "value": r["indeed_job_postings_index"]}))
        per_file["regional_fr.csv"] = r
    long = pd.concat(parts, ignore_index=True)
    long = long[long["value"].notna() & (long["value"].str.strip() != "")]
    long["_v"] = pd.to_numeric(long["value"], errors="coerce")
    if long["_v"].isna().any():
        raise RuntimeError("non numeric values in the Hiring Lab files")
    long = long.drop(columns="_v").sort_values(["date", "variable"], kind="stable").reset_index(drop=True)
    out_csv = res_dir / "hiringlab_fr.csv"
    long.to_csv(out_csv, index=False, quoting=csv.QUOTE_MINIMAL, lineterminator="\n", encoding="utf-8")

    for f in files:
        d = per_file[f["name"]]
        f["rows"], f["date_min"], f["date_max"] = int(len(d)), str(d["date"].min()), str(d["date"].max())

    # ---- headline numbers
    last_date = str(long["date"].max())
    latest = {"date": None}
    if "aggregate_job_postings_FR.csv" in per_file:
        a = per_file["aggregate_job_postings_FR.csv"]
        tot = a[a["variable"] == "total postings"].sort_values("date").iloc[-1]
        new = a[a["variable"] == "new postings"].sort_values("date").iloc[-1]
        latest = {
            "date": str(tot["date"]),
            "aggregate_total_postings_SA": float(tot["indeed_job_postings_index_SA"]),
            "aggregate_total_postings_NSA": float(tot["indeed_job_postings_index_NSA"]),
            "aggregate_new_postings_SA": float(new["indeed_job_postings_index_SA"]),
        }
    manifest.update({
        "source": "indeed_hiring_lab_job_postings_tracker_fr",
        "repository": f"https://github.com/{REPO}",
        "folder": FOLDER,
        "branch": branch,
        "branch_note": "the brief assumed 'main' (HTTP 404); the repository default branch is '" + str(default_branch or branch) + "'",
        "source_commit": commit,
        "repository_pushed_at": pushed_at,
        "licence": {**LICENCE, "github_api_spdx": licence_api},
        "downloaded_at": started,
        "download_date": started[:10],
        "files": files,
        "result_csv": {"path": str(out_csv.relative_to(root)).replace("\\", "/"), "rows": int(len(long)), "variables": int(long["variable"].nunique()), "date_min": str(long["date"].min()), "date_max": last_date,
                       "columns": ["date", "variable", "value"],
                       "naming": "aggregate = total postings SA (headline); '(NSA)' = not seasonally adjusted; '(new postings)' = postings on Indeed for 7 days or fewer; "
                                 "sector series carry the Indeed sector label; regions are 'region:<code>' with the codes as published (no label table is published)"},
        "latest_fr_aggregate": latest,
        "index_definition": "% of 1 Feb 2020 level (=100), 7-day trailing average, seasonally adjusted (SA) or not (NSA)",
        "updated_at": now_iso(),
    })
    manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")

    log(f"wrote {out_csv} ({len(long)} rows, {long['variable'].nunique()} variables, {long['date'].min()} -> {last_date})")
    print(f"Last date available: {last_date}")
    if latest.get("date"):
        print(f"Latest FR aggregate index (total postings, seasonally adjusted, 2020-02-01 = 100): {latest['aggregate_total_postings_SA']} on {latest['date']} "
              f"(NSA {latest['aggregate_total_postings_NSA']}; new postings SA {latest['aggregate_new_postings_SA']})")
    print(f"Licence: {LICENCE['name']} ({LICENCE['spdx']}) - cite Indeed Hiring Lab. Downloaded {started[:10]}.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as e:  # network down, GitHub unreachable, unexpected file: one clear line, non-zero exit
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
