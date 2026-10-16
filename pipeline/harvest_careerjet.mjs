// Careerjet Search API v4 - job aggregator (France). Same 60 AI / data / tech keywords as Jooble, locale fr_FR (country-wide), newest first.
// API   : GET https://search.api.careerjet.net/v4/query?locale_code=fr_FR&keywords=...&page=1..10&page_size=100&sort=date&user_ip=...&user_agent=...
//         auth HTTP Basic: API key as user name, empty password. Answer {type: JOBS, hits, pages, jobs: [{title, company, date, description (excerpt),
//         locations, salary, salary_min, salary_max, salary_type, salary_currency_code, url}]}. 400 = unsupported locale, 403 = missing user_ip / user_agent.
// Key   : a publisher account gives the key: https://www.careerjet.com/partners/register/as-publisher  (add CAREERJET_KEY=<key> to .env).
// Note  : user_ip / user_agent must describe the end user: CAREERJET_USER_IP (else this machine's public IP found through api.ipify.org, else 127.0.0.1)
//         and CAREERJET_USER_AGENT (default: the ELIA harvester name). The description excerpt is CAREERJET_FRAGMENT_SIZE characters (500; dropped
//         if the API refuses it, default 120).
// Limits: not published -> CAREERJET_DAILY_BUDGET (700 calls per UTC day), CAREERJET_DELAY_MS (700); ledger data-lake/raw/careerjet/_calls.json;
//         HTTP 429 stops the run and opens a 15 min cool-down.
// Output: data-lake/raw/careerjet/jobs.ndjson (one job per line, as returned + `_harvest`), jobs_manifest.json, _stdout.log
// Dedupe: the API has no job id: key = sha1(title | company | locations | date) of the normalised fields (the tracking `url` is kept in the record).
// Resumable like harvest_jooble.mjs (cursor keyword/page in the manifest, sweep repeated after CAREERJET_SWEEP_HOURS = 20 or with --force).
// Usage : node pipeline/harvest_careerjet.mjs [root] [--force] [--dry-run]
import { join } from 'node:path';
import { mkdirSync } from 'node:fs';
import { UA, KEYWORDS, num, nowIso, sha1, norm, rootAndFlags, loadEnv, makeLogger, readJson, writeJsonAtomic, sweepKeywords } from './harvest_common.mjs';

const { root, flags } = rootAndFlags(import.meta.url);
const env = loadEnv(root);
const dir = join(root, 'data-lake', 'raw', 'careerjet'); mkdirSync(dir, { recursive: true });
const log = makeLogger(dir, 'careerjet');
const REGISTER = 'https://www.careerjet.com/partners/register/as-publisher';
const manifestFile = join(dir, 'jobs_manifest.json');

if (!env.CAREERJET_KEY) {
  log('CAREERJET_KEY missing in', join(root, '.env'), '- create a publisher account at ' + REGISTER + ' to get the API key, then add  CAREERJET_KEY=<key>  to .env');
  const m = readJson(manifestFile, null) || { source: 'careerjet_search_api_v4', schema: 1, created_at: nowIso() };
  m.last_run = { at: nowIso(), status: 'skipped_no_api_key', register_url: REGISTER }; writeJsonAtomic(manifestFile, m);
  process.exit(0);
}
const BASE = (env.CAREERJET_BASE_URL || 'https://search.api.careerjet.net/v4/query'); // a custom base URL is only used by the offline tests
const budget = Math.floor(num(env.CAREERJET_DAILY_BUDGET, 700));
const delayMs = Math.max(env.CAREERJET_BASE_URL ? 0 : 300, num(env.CAREERJET_DELAY_MS, 700));
const maxPages = Math.min(10, Math.floor(num(env.CAREERJET_MAX_PAGES, 10))), patience = Math.floor(num(env.CAREERJET_PATIENCE, 2)), sweepHours = num(env.CAREERJET_SWEEP_HOURS, 20);
const fragment = Math.floor(num(env.CAREERJET_FRAGMENT_SIZE, 500));
const keywords = KEYWORDS;
if (flags.has('--dry-run')) { log(`dry run: ${keywords.length} keywords, locale fr_FR, up to ${maxPages} pages x 100 jobs each, budget ${budget} calls/day, delay ${delayMs} ms`); process.exit(0); }

let userIp = env.CAREERJET_USER_IP, ipSource = 'env';
if (!userIp) {
  try { const r = await fetch('https://api.ipify.org?format=json', { signal: AbortSignal.timeout(8000) }); userIp = (await r.json()).ip; ipSource = 'api.ipify.org'; }
  catch { userIp = '127.0.0.1'; ipSource = 'fallback'; }
}
const userAgent = env.CAREERJET_USER_AGENT || UA;
const auth = 'Basic ' + Buffer.from(env.CAREERJET_KEY + ':').toString('base64');
const fingerprint = j => sha1([j.title, j.company, j.locations, j.date].map(norm).join('|')).slice(0, 24);

await sweepKeywords({
  tag: 'careerjet', source: 'careerjet_search_api_v4', dir, log, flags, keywords, dataFile: join(dir, 'jobs.ndjson'), manifestFile,
  budget, delayMs, maxPages, patience, sweepHours,
  settings: { endpoint: 'GET ' + BASE, locale_code: 'fr_FR', page_size: 100, sort: 'date', fragment_size: fragment, user_ip_source: ipSource, keywords_count: keywords.length, max_pages: maxPages, patience, delay_ms: delayMs, daily_budget: budget },
  buildRequest: (kw, page, state) => {
    const q = new URLSearchParams({ locale_code: 'fr_FR', keywords: kw, page: String(page), page_size: '100', sort: 'date', user_ip: userIp, user_agent: userAgent });
    if (fragment && !state.no_fragment_size) q.set('fragment_size', String(fragment));
    return { url: `${BASE}?${q.toString().replace(/\+/g, '%20')}`, init: { method: 'GET', headers: { Authorization: auth, Accept: 'application/json', 'User-Agent': userAgent } } };
  },
  onBadRequest: ({ state }) => { if (state.no_fragment_size) return false; state.no_fragment_size = true; return true; }, // maybe fragment_size is refused: retry without it
  parse: json => ({ items: json.type === 'JOBS' && Array.isArray(json.jobs) ? json.jobs : [], total: typeof json.hits === 'number' ? json.hits : null, pages: typeof json.pages === 'number' ? json.pages : null }),
  keyOf: fingerprint,
});
