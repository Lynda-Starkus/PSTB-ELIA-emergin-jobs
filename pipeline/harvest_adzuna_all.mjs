// Adzuna France, ALL categories (the /categories list), quota-aware, resumable, idempotent. Raw ads -> data-lake/raw/adzuna/all_jobs.ndjson
//
// Official limits per key (https://developer.adzuna.com/docs/terms_of_service): 25 hits/minute, 250/day, 1000/week, 2500/month.
//   * calls are spaced >= 2.6 s apart (23/min), even across two runs;
//   * every HTTP call is written to the ledger data-lake/raw/adzuna/_calls.json BEFORE it is sent (per-day counts, UTC days);
//   * a run may spend at most min(ADZUNA_DAILY_BUDGET [default 230], 250 - used today, 1000 - used over 7 days (rolling and ISO week),
//     2500 - used over 30 days (rolling and calendar month)), so repeated runs can never exceed the budget;
//   * HTTP 429 stops the run cleanly (cursor saved) and opens a cool-down (>= 15 min; a second 429 the same UTC day blocks that day).
//
// Strategy (maximise distinct ads per call): one search call returns up to 50 ads (results_per_page=50, sort_by=date, newest first).
//   * categories are visited by decreasing size (sizes of the last census, refreshed with --recount);
//   * a category with <= 4900 ads is one country-wide slice (a single query reaches at most 100 pages x 50 = 5000 ads);
//   * a larger category is cut into 13 metropolitan regions (`where`) x 6 salary bands (salary_min / salary_max; band 'all' = no salary
//     filter, the only way to reach ads without salary). A slice bigger than 4900 ads is sampled for ADZUNA_PAGES_PER_VISIT pages
//     (default 5 = its 250 newest ads) and the cursor then rotates to the next slice, so successive days reach different ads;
//     a slice of <= 4900 ads is read completely, and when the 'all' slice of a region is that small its salary bands are skipped;
//   * the cursor (category, region, band, page) is stored in all_jobs_manifest.json: the next run continues exactly there;
//   * a visit ends early after two consecutive pages with < 20 % unseen ads (slice already harvested): a duplicate-only slice costs 2 calls.
//
// Usage: node pipeline/harvest_adzuna_all.mjs [root] [--status] [--recount] [--check-regions] [--add-legacy=YYYY-MM-DD:N]
//   --status        prints budget, usage and cursor, makes no call;   --recount  refreshes the category sizes (1 call per category);
//   --check-regions 13-26 calls: checks that `where=<region>` really filters (falls back to location0/location1 per region);
//   --add-legacy    registers calls made by older scripts that have no ledger.
// Env (process env or <root>/.env): ADZUNA_APP_ID, ADZUNA_APP_KEY, ADZUNA_DAILY_BUDGET (230), ADZUNA_PAGES_PER_VISIT (5),
//   ADZUNA_SKIP_CATEGORIES / ADZUNA_ONLY_CATEGORIES (comma lists of tags), ADZUNA_COUNT_LEGACY=1 (also count unledgered past calls).
import { join } from 'node:path';
import { existsSync, readdirSync, mkdirSync, createReadStream } from 'node:fs';
import { createInterface } from 'node:readline';
import { sleep, nowIso, todayUtc, addDays, UA, num, bigIntSafe, rootAndFlags, loadEnv, makeLogger, readJson, writeJsonAtomic, ensureTrailingNewline, appendLines, acquireLock, redactUrl, norm } from './harvest_common.mjs';

const { root, flags, args } = rootAndFlags(import.meta.url);
const env = loadEnv(root);
const out = join(root, 'data-lake', 'raw', 'adzuna'); mkdirSync(out, { recursive: true });
const log = makeLogger(out, 'adzuna_all');

// ---------------------------------------------------------------- configuration
const MOCK = Boolean(env.ADZUNA_BASE_URL); // a custom base URL is only used by the offline tests
const BASE = (env.ADZUNA_BASE_URL || 'https://api.adzuna.com/v1/api/jobs/fr').replace(/\/+$/, '');
const LIMITS = { minute: 25, day: num(env.ADZUNA_LIMIT_DAY, 250), week: num(env.ADZUNA_LIMIT_WEEK, 1000), month: num(env.ADZUNA_LIMIT_MONTH, 2500) };
const BUDGET = Math.max(0, Math.min(Math.floor(num(env.ADZUNA_DAILY_BUDGET, 230)), LIMITS.day));
const GAP_MS = MOCK ? num(env.ADZUNA_GAP_MS, 2600) : Math.max(2400, num(env.ADZUNA_GAP_MS, 2600)); // 25 calls/min = 2.4 s minimum
const PAGES_PER_VISIT = Math.max(1, Math.floor(num(env.ADZUNA_PAGES_PER_VISIT, 5)));
const COUNT_LEGACY = env.ADZUNA_COUNT_LEGACY === '1';
const RPP = 50, MAX_PAGE = 100, MIN_NEW_RATIO = 0.2, CATEGORIES_TTL_DAYS = 14;
const SMALL_CATEGORY = num(env.ADZUNA_SMALL_SLICE, 4900); // a slice up to this size is read completely (a query reaches 5000 ads at most); lower only for offline tests
const csv = v => String(v || '').split(',').map(s => s.trim()).filter(Boolean);
const key = s => norm(s).replace(/ /g, '');

// 13 metropolitan regions, in the spelling of Adzuna's location tree (location.area[1] of the ads), largest labour markets first.
const REGIONS = [
  { name: 'Ile-de-France', match: ['iledefrance'] },
  { name: 'Auvergne-Rhône-Alpes', match: ['auvergnerhonealpes'] },
  { name: 'Occitanie', match: ['occitanie'] },
  { name: "Provence-Alpes-Côte d'Azur", match: ['provencealpescotedazur'] },
  { name: 'Nouvelle-Aquitaine', match: ['nouvelleaquitaine'] },
  { name: 'Hauts-De-France', match: ['hautsdefrance'] },
  { name: 'Pays de la Loire', match: ['paysdelaloire'] },
  { name: 'Grand-Est', match: ['grandest'] },
  { name: 'Bretagne', match: ['bretagne'] },
  { name: 'Normandie', match: ['normandie'] },
  { name: 'Bourgogne-Franche-Comté', match: ['bourgognefranchecomte'] },
  { name: 'Centre', match: ['centre', 'centrevaldeloire'] },
  { name: 'Corse', match: ['corse'] },
];
// Annual gross salary bands (EUR). 'all' = no salary filter (the only way to reach ads without a salary).
const BANDS = [
  { label: 'all' },
  { label: 'lt24k', salary_max: 24000 },
  { label: '24-30k', salary_min: 24000, salary_max: 30000 },
  { label: '30-40k', salary_min: 30000, salary_max: 40000 },
  { label: '40-55k', salary_min: 40000, salary_max: 55000 },
  { label: 'ge55k', salary_min: 55000 },
];
// A slice has a rank: -1 = country-wide slice of a small category, otherwise 10 * region index + band index.
const rankOf = s => (s.region ? REGIONS.indexOf(s.region) * 10 + BANDS.indexOf(s.band) : -1);
const regionOfRank = rk => (rk >= 0 ? REGIONS[Math.floor(rk / 10)] : null);
const bandOfRank = rk => (rk >= 0 ? BANDS[rk % 10] : BANDS[0]);

if (!env.ADZUNA_APP_ID || !env.ADZUNA_APP_KEY) {
  log('ADZUNA_APP_ID / ADZUNA_APP_KEY missing in', join(root, '.env'), '- register at https://developer.adzuna.com/signup');
  process.exit(0);
}

// ---------------------------------------------------------------- ledger (per-day call counts, persisted before each call)
const LEDGER = join(out, '_calls.json');
const ledger = readJson(LEDGER, null) || { schema: 1, days: {}, legacy: {}, last_call_at: 0, throttle: {} };
for (const k of ['days', 'legacy', 'throttle']) ledger[k] ||= {};
ledger.limits = { per_minute: 25, per_day: LIMITS.day, per_week: LIMITS.week, per_month: LIMITS.month, source: 'https://developer.adzuna.com/docs/terms_of_service' };
ledger.note = 'Calls made by harvest_adzuna_all.mjs (UTC days). legacy = past calls made by scripts without a ledger; counted only with ADZUNA_COUNT_LEGACY=1.';
const saveLedger = () => { for (const d of Object.keys(ledger.days)) if (d < addDays(todayUtc(), -400)) delete ledger.days[d]; writeJsonAtomic(LEDGER, ledger); };
const dayRec = (d = todayUtc()) => (ledger.days[d] ||= { calls: 0, status: {} });
function sumDays(from, to) {
  let s = 0; for (let d = from; d <= to; d = addDays(d, 1)) s += (ledger.days[d]?.calls || 0) + (COUNT_LEGACY ? (ledger.legacy[d]?.calls || 0) : 0); return s;
}
function usage() {
  const t = todayUtc(); const dow = new Date(t + 'T00:00:00Z').getUTCDay(); const weekStart = addDays(t, -((dow + 6) % 7)); // ISO week starts on Monday
  return { day: sumDays(t, t), week_rolling: sumDays(addDays(t, -6), t), week_calendar: sumDays(weekStart, t), month_rolling: sumDays(addDays(t, -29), t), month_calendar: sumDays(t.slice(0, 8) + '01', t) };
}
function remaining(u = usage()) {
  return Math.max(0, Math.min(BUDGET - u.day, LIMITS.day - u.day, LIMITS.week - Math.max(u.week_rolling, u.week_calendar), LIMITS.month - Math.max(u.month_rolling, u.month_calendar)));
}
const cooldownLeftMs = () => (ledger.throttle.cooldown_until ? Math.max(0, Date.parse(ledger.throttle.cooldown_until) - Date.now()) : 0);

// ---------------------------------------------------------------- --add-legacy / --status (no API call)
const addLegacy = args.findIndex(a => a.startsWith('--add-legacy'));
if (addLegacy >= 0) {
  const m = /^--add-legacy=(\d{4}-\d{2}-\d{2}):(\d+)$/.exec(args[addLegacy]);
  if (!m) { log('usage: --add-legacy=YYYY-MM-DD:N'); process.exit(1); }
  ledger.legacy[m[1]] = { calls: Number(m[2]), note: 'unledgered calls registered by hand', registered_at: nowIso() };
  saveLedger(); log('legacy usage registered', m[1], m[2], 'calls (not counted against the budget unless ADZUNA_COUNT_LEGACY=1)'); process.exit(0);
}
const MANIFEST = join(out, 'all_jobs_manifest.json');
const ALL = join(out, 'all_jobs.ndjson');
const manifest = readJson(MANIFEST, null) || {
  source: 'adzuna_fr_all_categories', schema: 1, created_at: nowIso(),
  totals: { ads: 0, search_calls: 0, all_calls: 0, runs: 0 }, categories: {}, plan: {}, cursor: null, recent_visits: [],
};
manifest.categories ||= {}; manifest.categories.counts ||= {}; manifest.categories.ads_by_category ||= {}; manifest.recent_visits ||= []; manifest.plan ||= {};
manifest.region_counts ||= {}; manifest.totals ||= { ads: 0, search_calls: 0, all_calls: 0, runs: 0 };
const saveManifest = () => { manifest.updated_at = nowIso(); writeJsonAtomic(MANIFEST, manifest); };
// How a region is filtered: `where=<region>` (the brief) or, for a region where that does not filter, `location0=France&location1=<region>` (hierarchy filter).
manifest.region_modes ||= {};
const modeOf = regionName => manifest.region_modes[regionName] || 'where';

if (flags.has('--status')) {
  const u = usage();
  log('status', JSON.stringify({ budget_per_day: BUDGET, usage: u, remaining_now: remaining(u), cooldown_min: Math.round(cooldownLeftMs() / 6e4), legacy: ledger.legacy, cursor: manifest.cursor, plan_cycle: manifest.plan.cycle, ads: manifest.totals.ads }));
  process.exit(0);
}

// ---------------------------------------------------------------- guards: cool-down after 429, single instance
if (ledger.throttle.blocked_day === todayUtc()) { log('blocked for today (two HTTP 429 on', todayUtc(), '); next run is possible tomorrow (UTC)'); process.exit(0); }
if (cooldownLeftMs() > 0) { log('cool-down after HTTP 429 still running for', Math.ceil(cooldownLeftMs() / 6e4), 'min (until', ledger.throttle.cooldown_until + ')'); process.exit(0); }
{ const u = usage(); if (remaining(u) <= 0) { log('no call left: budget', BUDGET, 'usage', JSON.stringify(u), 'limits', JSON.stringify(LIMITS)); process.exit(0); } }
const release = acquireLock(out, '_all_jobs.lock');
if (!release) { log('another harvest_adzuna_all run is active (lock _all_jobs.lock); exiting'); process.exit(0); }
let stopRequested = false;
process.on('SIGINT', () => { stopRequested = true; });
process.on('SIGTERM', () => { stopRequested = true; });

// ---------------------------------------------------------------- HTTP (every call goes through api())
class Stop extends Error { constructor(reason, detail) { super(reason); this.reason = reason; this.detail = detail; } }
const auth = `app_id=${encodeURIComponent(env.ADZUNA_APP_ID)}&app_key=${encodeURIComponent(env.ADZUNA_APP_KEY)}`;
let runCalls = 0; const runStatus = {};
function note429(resp) {
  const ra = Number(resp.headers.get('retry-after')); const t = todayUtc(); const th = ledger.throttle;
  th.last_429_at = nowIso(); th.count_by_day ||= {}; th.count_by_day[t] = (th.count_by_day[t] || 0) + 1;
  th.cooldown_until = new Date(Date.now() + Math.max(Number.isFinite(ra) ? ra * 1000 : 0, 15 * 60e3)).toISOString();
  if (th.count_by_day[t] >= 2) th.blocked_day = t; saveLedger();
}
async function api(url) {
  for (let attempt = 0; attempt < 3; attempt++) {
    if (stopRequested) throw new Stop('interrupted');
    if (remaining() <= 0) throw new Stop('budget');
    const wait = ledger.last_call_at + GAP_MS - Date.now(); if (wait > 0) await sleep(wait); // >= 2.6 s between two calls, even across runs
    const d = dayRec(); d.calls++; d.first_at ||= nowIso(); d.last_at = nowIso(); ledger.last_call_at = Date.now(); saveLedger(); // counted before it is sent
    runCalls++; manifest.totals.all_calls++;
    let r, txt;
    try { r = await fetch(url, { headers: { Accept: 'application/json', 'User-Agent': UA }, signal: AbortSignal.timeout(45000) }); txt = await r.text(); }
    catch (e) { d.status.neterr = (d.status.neterr || 0) + 1; saveLedger(); runStatus.neterr = (runStatus.neterr || 0) + 1; log('network error', e.cause?.code || e.message, redactUrl(url)); await sleep(5000 * (attempt + 1)); continue; }
    d.status[r.status] = (d.status[r.status] || 0) + 1; saveLedger(); runStatus[r.status] = (runStatus[r.status] || 0) + 1;
    if (r.status === 429) { note429(r); throw new Stop('http_429', 'Retry-After=' + r.headers.get('retry-after')); }
    if (r.status === 401 || r.status === 403) throw new Stop('auth_' + r.status, txt.slice(0, 160));
    if (r.status >= 500) { log('HTTP', r.status, '- retrying', redactUrl(url)); await sleep(8000 * (attempt + 1)); continue; }
    let json = null; try { json = JSON.parse(txt, bigIntSafe); } catch { /* not JSON */ }
    if (r.status === 200 && json === null) { log('HTTP 200 without JSON - retrying'); await sleep(5000); continue; }
    return { status: r.status, json: json || {} };
  }
  throw new Stop('server_errors');
}

// ---------------------------------------------------------------- existing data: ids already stored, per-category tally
async function scanExisting() {
  const ids = new Set(), byCat = {}; if (!existsSync(ALL)) return { ids, byCat };
  const rl = createInterface({ input: createReadStream(ALL, { encoding: 'utf8' }), crlfDelay: Infinity });
  for await (const line of rl) {
    if (!line) continue; let o; try { o = JSON.parse(line); } catch { continue; }
    if (o.id === undefined || o.id === null) continue; ids.add(String(o.id));
    const t = o.category?.tag || 'unknown'; byCat[t] = (byCat[t] || 0) + 1;
  }
  return { ids, byCat };
}

// ---------------------------------------------------------------- categories, ordering, slices
async function ensureCategories() {
  const c = manifest.categories; const fresh = c.list?.length && c.fetched_at && Date.now() - Date.parse(c.fetched_at) < CATEGORIES_TTL_DAYS * 864e5;
  if (!fresh) {
    const { status, json } = await api(`${BASE}/categories?${auth}`);
    if (status !== 200 || !Array.isArray(json.results)) throw new Stop('categories_failed', 'HTTP ' + status);
    c.list = json.results.map(x => ({ tag: x.tag, label: x.label })); c.fetched_at = nowIso(); log('categories', c.list.length, 'fetched');
  }
  if (!Object.keys(c.counts).length) { // size census of the previous harvest (category_counts_YYYY-MM-DD.json) seeds the ordering
    const files = readdirSync(out).filter(f => /^category_counts_\d{4}-\d{2}-\d{2}\.json$/.test(f)).sort();
    if (files.length) { Object.assign(c.counts, readJson(join(out, files[files.length - 1]), {}).counts || {}); c.counts_source = files[files.length - 1]; log('category sizes seeded from', c.counts_source); }
  }
  saveManifest();
}
async function recount() {
  const c = manifest.categories; log('recount: one call per category');
  for (const cat of c.list) {
    const { status, json } = await api(`${BASE}/search/1?${auth}&results_per_page=1&category=${encodeURIComponent(cat.tag)}`);
    if (status === 200 && typeof json.count === 'number') c.counts[cat.tag] = json.count;
  }
  c.counts_at = nowIso(); c.counts_source = 'recount ' + c.counts_at; saveManifest();
}
const SKIP = new Set(csv(env.ADZUNA_SKIP_CATEGORIES)), ONLY = csv(env.ADZUNA_ONLY_CATEGORIES);
const allowedTag = t => !SKIP.has(t) && (!ONLY.length || ONLY.includes(t));
function computeOrder() {
  const c = manifest.categories;
  return c.list.map(x => x.tag).filter(allowedTag).sort((a, b) => (c.counts[b] ?? 0) - (c.counts[a] ?? 0) || a.localeCompare(b));
}
const rcKey = (tag, regionName) => tag + '|' + regionName;
function slicesOf(tag) {
  const n = manifest.categories.counts[tag];
  if (n !== undefined && n !== null && n <= SMALL_CATEGORY) return [{ cat: tag, region: null, band: BANDS[0] }];
  const s = [];
  for (const region of REGIONS) for (const band of BANDS) {
    const rc = manifest.region_counts[rcKey(tag, region.name)];
    if (band.label !== 'all' && rc !== undefined && rc <= SMALL_CATEGORY) continue; // the 'all' slice of this region is fully readable: no bands
    s.push({ cat: tag, region, band });
  }
  return s;
}
function sliceUrl(sl, pg, mode = sl.region ? modeOf(sl.region.name) : 'where') {
  const q = new URLSearchParams({ results_per_page: String(RPP), sort_by: 'date', category: sl.cat });
  if (sl.region) { if (mode === 'where') q.set('where', sl.region.name); else { q.set('location0', 'France'); q.set('location1', sl.region.name); } }
  if (sl.band.salary_min !== undefined) q.set('salary_min', String(sl.band.salary_min));
  if (sl.band.salary_max !== undefined) q.set('salary_max', String(sl.band.salary_max));
  return `${BASE}/search/${pg}?${auth}&${q.toString().replace(/\+/g, '%20')}`;
}
const regionRatio = (rows, region) => rows.filter(r => (r.location?.area || []).some(a => region.match.includes(key(a)))).length / rows.length;
function bandStats(rows, band) { // diagnostic only: do the salary filters filter?
  const mids = rows.map(r => { const a = r.salary_min, b = r.salary_max; return a && b ? (a + b) / 2 : (a || b || null); }).filter(v => v !== null);
  const inBand = mids.filter(v => v >= (band.salary_min ?? 0) && v <= (band.salary_max ?? Infinity));
  return { with_salary: +(mids.length / rows.length).toFixed(2), in_band: mids.length ? +(inBand.length / mids.length).toFixed(2) : null };
}

// ---------------------------------------------------------------- main
const t0 = nowIso(); const { ids: seen, byCat } = await scanExisting(); ensureTrailingNewline(ALL);
const u0 = usage();
log(`start: ${seen.size} ads on disk | budget ${BUDGET}/day | today ${u0.day} | week(7d) ${u0.week_rolling}/${LIMITS.week} | month(30d) ${u0.month_rolling}/${LIMITS.month} | allowed now ${remaining(u0)} | gap ${GAP_MS} ms`);
const legacyInWindow = Object.entries(ledger.legacy).filter(([d]) => d >= addDays(todayUtc(), -29));
if (legacyInWindow.length && !COUNT_LEGACY) log('note: unledgered past calls not counted:', legacyInWindow.map(([d, v]) => `${d}=${v.calls}`).join(', '), '(ADZUNA_COUNT_LEGACY=1 to count them)');

let stopReason = 'done', stopDetail = null, newAds = 0, dupAds = 0, searchCalls = 0; const visitsThisRun = [];
let order = [], ci = 0, curRank = -1, page = 1, visitPages = 0, visit = null;
const adsAtStart = seen.size;
const saveCursor = () => {
  manifest.cursor = { category: order[ci], region: regionOfRank(curRank)?.name ?? null, band: bandOfRank(curRank).label, page, visit_pages: visitPages }; saveManifest();
};
function finishVisit(reason, sl) { // close the current visit and point the cursor to the slice after `sl`
  if (visit) {
    visit.end = reason; visit.at = nowIso(); manifest.recent_visits = [...manifest.recent_visits, visit].slice(-25); visitsThisRun.push(visit);
    log(`  visit end [${reason}] ${visit.category} | ${visit.region || 'country'} | ${visit.band}: ${visit.pages} page(s), ${visit.results} ads, ${visit.new} new, count=${visit.count}`);
  }
  const rk = rankOf(sl); visit = null; page = 1; visitPages = 0;
  curRank = rk < 0 ? 0 : (rk % 10 + 1 >= BANDS.length ? (Math.floor(rk / 10) + 1) * 10 : rk + 1); // next band, else first band of the next region
  if (slicesOf(order[ci]).some(s => rankOf(s) >= curRank)) saveCursor(); else nextCategory(); // the persisted cursor always names a real slice
}
function ingestRows(rows) { // append the ads not seen before (dedupe on the Adzuna id) and tally them
  const fresh = [];
  for (const r of rows) { if (r?.id === undefined || r.id === null) continue; const id = String(r.id); if (seen.has(id)) continue; seen.add(id); fresh.push(r); }
  appendLines(ALL, fresh); newAds += fresh.length; dupAds += rows.length - fresh.length;
  for (const r of fresh) { const t = r.category?.tag || 'unknown'; byCat[t] = (byCat[t] || 0) + 1; }
  return fresh;
}
async function checkRegions(tag) { // --check-regions: does `where=<region>` filter? one call per region (two when it does not), results are kept
  log(`check-regions on category ${tag}: where=<region>, newest 50 ads of each region`);
  for (const region of REGIONS) {
    for (const mode of ['where', 'location1']) {
      const { status, json } = await api(sliceUrl({ cat: tag, region, band: BANDS[0] }, 1, mode)); searchCalls++; manifest.totals.search_calls++;
      const rows = status === 200 && Array.isArray(json.results) ? json.results : []; ingestRows(rows);
      const ratio = rows.length ? regionRatio(rows, region) : null;
      log(`  ${region.name.padEnd(28)} [${mode}] count=${json.count ?? 'n/a'} ads=${rows.length} in-region=${ratio === null ? 'n/a' : Math.round(ratio * 100) + '%'}`);
      (manifest.region_check ||= {})[region.name] = { mode, category: tag, count: json.count ?? null, match: ratio === null ? null : +ratio.toFixed(2), at: nowIso() };
      if (ratio === null || ratio >= 0.5) { manifest.region_modes[region.name] = mode; if (typeof json.count === 'number') manifest.region_counts[rcKey(tag, region.name)] = json.count; break; }
      if (mode === 'location1') { (manifest.bad_regions ||= {})[region.name] = todayUtc(); log(`  WARN ${region.name}: neither where nor location1 filters; region skipped`); }
    }
  }
  saveManifest();
}
function nextCategory() {
  ci++; curRank = -1; page = 1; visitPages = 0;
  if (ci >= order.length) { // one full cycle over all categories: re-rank by the latest sizes and start again (next pass = fresh ads)
    manifest.plan = { cycle: (manifest.plan.cycle || 1) + 1, cycle_started_at: nowIso(), order: computeOrder() };
    order = manifest.plan.order.filter(allowedTag); ci = 0; log('cycle complete -> cycle', manifest.plan.cycle); if (!order.length) throw new Stop('no_categories');
  }
  saveCursor();
}
try {
  await ensureCategories();
  if (flags.has('--recount')) await recount();
  if (!manifest.plan.order?.length) manifest.plan = { cycle: 1, cycle_started_at: nowIso(), order: computeOrder() };
  order = manifest.plan.order.filter(allowedTag); if (!order.length) throw new Stop('no_categories');
  const c0 = manifest.cursor;
  ci = c0 ? Math.max(0, order.indexOf(c0.category)) : 0;
  if (c0 && c0.region) { const r = REGIONS.findIndex(x => x.name === c0.region), b = BANDS.findIndex(x => x.label === c0.band); curRank = r < 0 ? 0 : r * 10 + Math.max(0, b); }
  page = c0?.page || 1; visitPages = c0?.visit_pages || 0;
  manifest.settings = { results_per_page: RPP, sort_by: 'date', pages_per_visit: PAGES_PER_VISIT, small_slice_max: SMALL_CATEGORY, min_new_ratio: MIN_NEW_RATIO, regions: REGIONS.map(r => r.name), bands: BANDS, gap_ms: GAP_MS };
  saveCursor();
  if (flags.has('--check-regions')) { await checkRegions(order[0]); throw new Stop('check_regions_done'); }
  let consecutive400 = 0;
  while (true) {
    if (stopRequested) throw new Stop('interrupted');
    if (remaining() <= 0) throw new Stop('budget');
    const slices = slicesOf(order[ci]); const si = slices.findIndex(s => rankOf(s) >= curRank);
    if (si < 0) { nextCategory(); continue; } // every slice of this category has been visited
    const sl = slices[si];
    if (rankOf(sl) !== curRank) { curRank = rankOf(sl); page = 1; visitPages = 0; } // the saved slice vanished (e.g. bands skipped): take the next one
    if (sl.region && manifest.bad_regions?.[sl.region.name]) { finishVisit('bad_region', sl); continue; }
    const { status, json } = await api(sliceUrl(sl, page)); searchCalls++; manifest.totals.search_calls++;
    if (status === 400) {
      log('HTTP 400 for', sl.cat, sl.region?.name, sl.band.label, 'page', page, '-', JSON.stringify(json).slice(0, 160));
      if (++consecutive400 >= 3) throw new Stop('bad_request', 'three consecutive HTTP 400'); finishVisit('http_400', sl); continue;
    }
    if (status !== 200) { log('unexpected HTTP', status); throw new Stop('http_' + status); }
    consecutive400 = 0;
    const rows = Array.isArray(json.results) ? json.results : []; const count = typeof json.count === 'number' ? json.count : null;
    const fresh = ingestRows(rows); // real ads are kept even if the filter turns out not to filter
    if (!visit) visit = { category: sl.cat, region: sl.region?.name || null, band: sl.band.label, first_page: page, pages: 0, results: 0, new: 0, count: null };
    if (sl.region && page === 1 && rows.length >= 10) { // is the region filter really filtering?
      const ratio = regionRatio(rows, sl.region); visit.region_match = +ratio.toFixed(2);
      if (ratio < 0.5) {
        if (modeOf(sl.region.name) === 'where') { log(`WARN where=${sl.region.name} matches only ${Math.round(ratio * 100)}% of the ads -> this region switches to location0/location1`); manifest.region_modes[sl.region.name] = 'location1'; saveManifest(); visit = null; continue; }
        log(`WARN region ${sl.region.name}: filter ineffective in both modes (${Math.round(ratio * 100)}% match); region skipped`); (manifest.bad_regions ||= {})[sl.region.name] = todayUtc(); finishVisit('bad_region', sl); continue;
      }
    }
    if (sl.band.label !== 'all' && page === 1 && rows.length) visit.band_check = bandStats(rows, sl.band);
    visit.pages++; visit.results += rows.length; visit.new += fresh.length;
    if (count !== null) {
      visit.count = count;
      if (!sl.region) manifest.categories.counts[sl.cat] = count; // a country-wide slice refreshes the category size
      else if (sl.band.label === 'all') manifest.region_counts[rcKey(sl.cat, sl.region.name)] = count; // a small region needs no salary bands
    }
    log(`[${order[ci]} #${ci + 1}/${order.length} | ${sl.region?.name || 'country'} | ${sl.band.label} | p${page}] ${rows.length} ads, ${fresh.length} new, count=${count} | calls today ${dayRec().calls}/${BUDGET}`);
    const readable = count !== null && count <= SMALL_CATEGORY; // the whole slice fits in <= 100 pages: read it completely
    // A band slice starts with ads that its region's 'all' slice has just delivered (nested slices), so one seen-only page is tolerated;
    // two consecutive pages with < 20 % unseen ads mean that the slice is already harvested.
    visit.low = rows.length && fresh.length / rows.length < MIN_NEW_RATIO ? (visit.low || 0) + 1 : 0;
    let endReason = null; // why this visit stops after this page
    if (rows.length === 0) endReason = 'empty'; else if (rows.length < RPP) endReason = 'last_page'; else if (count !== null && page * RPP >= count) endReason = 'exhausted';
    else if (page >= MAX_PAGE) endReason = 'page_cap'; else if (visit.low >= 2) endReason = 'mostly_seen'; else if (!readable && visitPages + 1 >= PAGES_PER_VISIT) endReason = 'visit_cap';
    if (endReason) finishVisit(endReason, sl); else { page++; visitPages++; saveCursor(); }
  }
} catch (e) {
  if (e instanceof Stop) { stopReason = e.reason; stopDetail = e.detail || null; } else { stopReason = 'error'; stopDetail = String(e.stack || e).slice(0, 400); log('ERROR', stopDetail); process.exitCode = 1; }
} finally {
  if (visit) { visit.end = 'run_stopped:' + stopReason; visit.at = nowIso(); manifest.recent_visits = [...manifest.recent_visits, visit].slice(-25); visitsThisRun.push(visit); }
  const u1 = usage();
  manifest.totals.ads = seen.size; manifest.totals.runs++; manifest.categories.ads_by_category = byCat;
  manifest.last_run = {
    started_at: t0, ended_at: nowIso(), stop_reason: stopReason, stop_detail: stopDetail, daily_budget: BUDGET,
    calls: runCalls, search_calls: searchCalls, status: runStatus, new_ads: newAds, duplicate_ads: dupAds, ads_per_search_call: searchCalls ? +(newAds / searchCalls).toFixed(1) : 0,
    ads_on_disk_before: adsAtStart, ads_on_disk: seen.size, calls_today: u1.day, remaining_today: remaining(u1), usage: u1, slices_visited: visitsThisRun.length,
  };
  manifest.run_history = [...(manifest.run_history || []), { started_at: t0, mode: [...flags].join(' ') || 'harvest', daily_budget: BUDGET, calls: runCalls, search_calls: searchCalls, new_ads: newAds, duplicate_ads: dupAds, stop_reason: stopReason }].slice(-60);
  saveManifest(); release();
  log('RESULT', JSON.stringify({ stop_reason: stopReason, calls: runCalls, search_calls: searchCalls, new_ads: newAds, duplicate_ads: dupAds, ads_on_disk: seen.size, calls_today: u1.day, cursor: manifest.cursor }));
}
