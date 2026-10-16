// Jooble REST API - job aggregator (France). 60 AI / data / tech keywords (French and English) x location "France", paginated until nothing new.
// API   : POST https://jooble.org/api/<JOOBLE_KEY>   JSON body {"keywords": "...", "location": "France", "page": N}
//         answer {"totalCount": N, "jobs": [{title, location, snippet, salary, source, type, link, company, updated, id}]}  (snippet = truncated text)
// Key   : free, on request through the form of https://jooble.org/api/about  (name, position, email, website, phone). Add JOOBLE_KEY=<key> to .env.
// Limits: set per key by Jooble (not published) -> JOOBLE_DAILY_BUDGET (1000 calls per UTC day) and JOOBLE_DELAY_MS (800) are conservative defaults;
//         ledger in data-lake/raw/jooble/_calls.json; HTTP 429 stops the run and opens a 15 min cool-down.
// Output: data-lake/raw/jooble/jobs.ndjson (one job per line, as returned + a `_harvest` block; `id` kept as an exact decimal string because Jooble ids
//         exceed 2^53), jobs_manifest.json (counts, timestamps, cursor), _stdout.log
// Dedupe: job id. Resumable: the manifest keeps the sweep cursor (keyword, page); a finished sweep is not repeated before JOOBLE_SWEEP_HOURS (20)
//         unless --force. A keyword stops at the first empty page, after JOOBLE_PATIENCE (2) consecutive pages without new job, or at JOOBLE_MAX_PAGES (50).
// Usage : node pipeline/harvest_jooble.mjs [root] [--force] [--dry-run]
import { join } from 'node:path';
import { mkdirSync } from 'node:fs';
import { UA, KEYWORDS, num, nowIso, rootAndFlags, loadEnv, makeLogger, readJson, writeJsonAtomic, sweepKeywords } from './harvest_common.mjs';

const { root, flags } = rootAndFlags(import.meta.url);
const env = loadEnv(root);
const dir = join(root, 'data-lake', 'raw', 'jooble'); mkdirSync(dir, { recursive: true });
const log = makeLogger(dir, 'jooble');
const REGISTER = 'https://jooble.org/api/about';
const manifestFile = join(dir, 'jobs_manifest.json');

if (!env.JOOBLE_KEY) {
  log('JOOBLE_KEY missing in', join(root, '.env'), '- request a free API key with the form at ' + REGISTER + ' then add  JOOBLE_KEY=<key>  to .env');
  const m = readJson(manifestFile, null) || { source: 'jooble_rest_api', schema: 1, created_at: nowIso() };
  m.last_run = { at: nowIso(), status: 'skipped_no_api_key', register_url: REGISTER }; writeJsonAtomic(manifestFile, m);
  process.exit(0);
}
const BASE = (env.JOOBLE_BASE_URL || 'https://jooble.org/api').replace(/\/+$/, ''); // a custom base URL is only used by the offline tests
const LOCATION = env.JOOBLE_LOCATION || 'France';
const budget = Math.floor(num(env.JOOBLE_DAILY_BUDGET, 1000));
const delayMs = Math.max(env.JOOBLE_BASE_URL ? 0 : 300, num(env.JOOBLE_DELAY_MS, 800));
const maxPages = Math.floor(num(env.JOOBLE_MAX_PAGES, 50)), patience = Math.floor(num(env.JOOBLE_PATIENCE, 2)), sweepHours = num(env.JOOBLE_SWEEP_HOURS, 20);
const keywords = KEYWORDS;
if (flags.has('--dry-run')) { log(`dry run: ${keywords.length} keywords x location "${LOCATION}", up to ${maxPages} pages each, budget ${budget} calls/day, delay ${delayMs} ms`); process.exit(0); }

await sweepKeywords({
  tag: 'jooble', source: 'jooble_rest_api', dir, log, flags, keywords, dataFile: join(dir, 'jobs.ndjson'), manifestFile,
  budget, delayMs, maxPages, patience, sweepHours,
  settings: { endpoint: 'POST ' + BASE + '/<key>', body: '{keywords, location, page}', location: LOCATION, keywords_count: keywords.length, max_pages: maxPages, patience, delay_ms: delayMs, daily_budget: budget },
  // `page` is sent as a number; the first HTTP 400 flips it to a string (and the other way round), the choice that works is kept in the manifest
  buildRequest: (kw, page, state) => ({
    url: `${BASE}/${encodeURIComponent(env.JOOBLE_KEY)}`,
    init: { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'User-Agent': UA }, body: JSON.stringify({ keywords: kw, location: LOCATION, page: state.page_type === 'string' ? String(page) : page }) },
  }),
  onBadRequest: ({ state }) => { if (state.page_flipped) return false; state.page_flipped = true; state.page_type = state.page_type === 'string' ? 'number' : 'string'; return true; },
  parse: json => ({ items: Array.isArray(json.jobs) ? json.jobs : [], total: typeof json.totalCount === 'number' ? json.totalCount : (json.totalCount ?? null), pages: null }),
  keyOf: job => (job.id !== undefined && job.id !== null ? String(job.id) : (job.link || '')),
  recordOf: job => ({ ...job, id: job.id !== undefined && job.id !== null ? String(job.id) : job.id }),
});
