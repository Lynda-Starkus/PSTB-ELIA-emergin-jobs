# Daily pipeline: harvest France Travail offers of the last 2 days, then append a line to the dashboard log.
$root = "G:\Linda\Bureau\PSTB\ELIA\metiers-ia-emergents"
$log = Join-Path $root "data-lake\raw\ft_api\_daily_task.log"
"$(Get-Date -Format s) start" | Out-File -Append -Encoding utf8 $log
& "C:\Program Files\nodejs\node.exe" (Join-Path $root "pipeline\harvest_ft_daily.mjs") $root 2 2>&1 | Out-File -Append -Encoding utf8 $log
# Added 15 Oct 2026 - Adzuna France, all categories. Quota-aware: per-day ledger data-lake\raw\adzuna\_calls.json, budget = ADZUNA_DAILY_BUDGET (default 230 calls/day;
# official limits 25/min, 250/day, 1000/week, 2500/month); it stops cleanly on HTTP 429 and when the budget is spent, so it is safe to run every day.
$env:ADZUNA_DAILY_BUDGET = "80"   # 2 500 calls/month allowed: 80/day keeps a steady series all month
"$(Get-Date -Format s) adzuna_all start" | Out-File -Append -Encoding utf8 $log
& "C:\Program Files\nodejs\node.exe" (Join-Path $root "pipeline\harvest_adzuna_all.mjs") $root 2>&1 | Out-File -Append -Encoding utf8 $log
# Added 15 Oct 2026 - Indeed Hiring Lab job postings index for France (CC BY 4.0, refreshed weekly): downloads only changed files, rebuilds data-lake\lake\results\hiringlab_fr.csv.
"$(Get-Date -Format s) hiringlab start" | Out-File -Append -Encoding utf8 $log
& (Join-Path $root ".venv\Scripts\python.exe") (Join-Path $root "pipeline\harvest_hiringlab.py") $root 2>&1 | Out-File -Append -Encoding utf8 $log
"$(Get-Date -Format s) end" | Out-File -Append -Encoding utf8 $log
