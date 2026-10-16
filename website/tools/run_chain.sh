#!/usr/bin/env bash
# Rebuild the observatory bundle from the regenerated inputs, with the zip's own tools.
# Usage: bash tools/run_chain.sh   (from website/)
set -e
cd "$(dirname "$0")/.."
export NODE_OPTIONS=--max-old-space-size=16000
PY="G:/Linda/Bureau/PSTB/ELIA/metiers-ia-emergents/.venv/Scripts/python"
echo "== 1. build_data (HN series + titles)";      node tools/build_data.mjs
echo "== 2. mine_discovery (FR groups + HN n-grams)"; node tools/mine_discovery.mjs
echo "== 3. build (embed inputs into data.js)";      node tools/build.mjs
echo "== 4. outcomes (evidence pack for the tour)"; "$PY" tools/video/build_outcomes.py
echo "== 5. build again (embed outcomes)";          node tools/build.mjs
echo "== 6. tour chapters from the new numbers";    "$PY" tools/update_tour.py
echo "== 7. artifact variant";                      node tools/build.mjs
ls -la data/data.js dist/artifact.html
