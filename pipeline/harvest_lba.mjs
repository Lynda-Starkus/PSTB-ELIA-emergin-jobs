// La bonne alternance - apprenticeship job offers in France, ROME technology and data families x 30 city centres (100 km radius).
// API   : GET https://api.apprentissage.beta.gouv.fr/api/job/v1/search  (operationId jobSearch, OpenAPI at /api/swagger.json)
//         query  latitude, longitude, radius (0-200 km, default 30), romes (comma list), no pagination: one response = all offers in range
// Auth  : header  Authorization: Bearer <LBA_API_KEY>   (free key, "production" type: https://api.apprentissage.beta.gouv.fr/en/compte/profil)
// Limit : 60 calls/minute per key (x-ratelimit-* headers, retry-after on 429). Calls are spaced LBA_DELAY_MS (1300) apart.
// Reads : any valid key can read job offers (no habilitation needed).
// Output: data-lake/raw/lba/offers.ndjson (one offer per line, as returned + a `_harvest` block; the recruiter phone number is dropped)
//         data-lake/raw/lba/offers_manifest.json (counts, timestamps, sweep cursor), _stdout.log
// Dedupe: identifier.id (La bonne alternance id) or, for France Travail offers that have none, "<partner_label>:<partner_job_id>".
// Resumable: a sweep = 30 cities x 20 ROME chunks (the 5 data/AI codes M1889 M1405 M1419 M1423 M1435 first, then M1801-M1896, 5 per call);
//         the manifest stores the next query, so an interrupted sweep continues where it stopped. A chunk whose answer reaches
//         LBA_SATURATION (100) offers is re-queried code by code. A finished sweep is not repeated before LBA_SWEEP_HOURS (20) unless --force
//         (the offers are refreshed once a day at 3:00 Paris time on the provider side).
// --export (optional, documented but not run yet: it needs a key): GET /job/v1/export (2 calls/min) answers {url, lastUpdate}; the file behind `url`
//         (valid 2 min, same structure as the search answer) holds ALL offers of the country in one download. They are filtered on the ROME codes above
//         (LBA_EXPORT_ALL=1 keeps everything) and stored with the same dedupe. If it works, it replaces the 600 calls of the grid.
// Usage : node pipeline/harvest_lba.mjs [root] [--force] [--dry-run] [--export]
// Env   : LBA_API_KEY (.env), LBA_RADIUS_KM (100), LBA_ROMES_PER_CALL (5), LBA_DELAY_MS (1300), LBA_MAX_CALLS (900 per run), LBA_EXCLUDE_PARTNERS
import { join } from 'node:path';
import { mkdirSync } from 'node:fs';
import { sleep, nowIso, UA, num, bigIntSafe, rootAndFlags, loadEnv, makeLogger, readJson, writeJsonAtomic, loadKeys, ensureTrailingNewline, appendLines, acquireLock, sha1 } from './harvest_common.mjs';

const { root, flags } = rootAndFlags(import.meta.url);
const env = loadEnv(root);
const out = join(root, 'data-lake', 'raw', 'lba'); mkdirSync(out, { recursive: true });
const log = makeLogger(out, 'lba');
const REGISTER = 'https://api.apprentissage.beta.gouv.fr/en/compte/profil';
const MANIFEST = join(out, 'offers_manifest.json'), OFFERS = join(out, 'offers.ndjson');
const manifest = readJson(MANIFEST, null) || { source: 'la_bonne_alternance_job_search', schema: 1, created_at: nowIso(), totals: { offers: 0, calls: 0, runs: 0, sweeps_completed: 0 }, by_partner: {}, by_rome: {} };
const save = () => { manifest.updated_at = nowIso(); writeJsonAtomic(MANIFEST, manifest); };

if (!env.LBA_API_KEY) {
  log('LBA_API_KEY missing in', join(root, '.env'), '- create a free API key (type production) at ' + REGISTER + ' and add  LBA_API_KEY=<key>  to .env');
  manifest.last_run = { at: nowIso(), status: 'skipped_no_api_key', register_url: REGISTER }; save();
  process.exit(0);
}

// ---------------------------------------------------------------- configuration
const MOCKISH = Boolean(env.LBA_BASE_URL); // a custom base URL is only used by the offline tests
const BASE = (env.LBA_BASE_URL || 'https://api.apprentissage.beta.gouv.fr/api').replace(/\/+$/, '');
const KEY = env.LBA_API_KEY;
const RADIUS = Math.min(200, Math.max(1, num(env.LBA_RADIUS_KM, 100)));
const PER_CALL = Math.max(1, Math.floor(num(env.LBA_ROMES_PER_CALL, 5)));
const DELAY_MS = Math.max(MOCKISH ? 0 : 1100, num(env.LBA_DELAY_MS, 1300)); // documented limit: 60 calls/min = 1.0 s minimum
const MAX_CALLS = Math.floor(num(env.LBA_MAX_CALLS, 900));
const SATURATION = Math.floor(num(env.LBA_SATURATION, 100));
const SWEEP_HOURS = num(env.LBA_SWEEP_HOURS, 20);
const EXCLUDE = String(env.LBA_EXCLUDE_PARTNERS || '').split(',').map(s => s.trim()).filter(Boolean); // e.g. "France Travail" (already harvested directly)

// 30 city centres (lat, lon): the regional capitals' catchments plus peripheral areas that a 100 km disc around a metropolis would miss.
const CITIES = [
  ['Paris', 48.8566, 2.3522], ['Lille', 50.6292, 3.0573], ['Amiens', 49.8941, 2.2958], ['Rouen', 49.4432, 1.0999], ['Caen', 49.1829, -0.3707],
  ['Rennes', 48.1173, -1.6778], ['Brest', 48.3904, -4.4861], ['Nantes', 47.2184, -1.5536], ['Le Mans', 48.0061, 0.1996], ['Tours', 47.3941, 0.6848],
  ['Orleans', 47.9029, 1.9093], ['Reims', 49.2583, 4.0317], ['Metz', 49.1193, 6.1757], ['Strasbourg', 48.5734, 7.7521], ['Dijon', 47.3220, 5.0415],
  ['Besancon', 47.2378, 6.0241], ['Lyon', 45.7640, 4.8357], ['Grenoble', 45.1885, 5.7245], ['Clermont-Ferrand', 45.7772, 3.0870], ['Limoges', 45.8336, 1.2611],
  ['Poitiers', 46.5802, 0.3404], ['La Rochelle', 46.1603, -1.1511], ['Bordeaux', 44.8378, -0.5792], ['Pau', 43.2951, -0.3708], ['Toulouse', 43.6047, 1.4442],
  ['Montpellier', 43.6108, 3.8767], ['Perpignan', 42.6887, 2.8948], ['Marseille', 43.2965, 5.3698], ['Nice', 43.7102, 7.2620], ['Ajaccio', 41.9192, 8.7386],
].map(([name, lat, lon]) => ({ name, lat, lon }));

// ROME 4.x codes (ROME v4.61): data / AI first, then the whole M18 family "Systemes d'information et de telecommunication" (M1801-M1896).
const CORE = ['M1889', 'M1405', 'M1419', 'M1423', 'M1435']; // AI engineer, data scientist, data analyst, chief data officer, tracking verifier
const DATA_IT = ['M1811', 'M1873', 'M1851', 'M1872', 'M1824', 'M1894']; // data engineer, embedded AI, BI analyst/consultant/developer, database manager
const M18 = Array.from({ length: 96 }, (_, i) => 'M18' + String(i + 1).padStart(2, '0'));
const REST = [...new Set([...DATA_IT, ...M18])].filter(c => !CORE.includes(c));
const CHUNKS = [CORE]; for (let i = 0; i < REST.length; i += PER_CALL) CHUNKS.push(REST.slice(i, i + PER_CALL));
const ROME_SET = new Set(CHUNKS.flat());
const TOTAL_Q = CITIES.length * CHUNKS.length;

if (flags.has('--dry-run')) { log(`dry run: ${CITIES.length} cities x ${CHUNKS.length} chunks = ${TOTAL_Q} queries, radius ${RADIUS} km, delay ${DELAY_MS} ms (~${Math.round(TOTAL_Q * DELAY_MS / 60000)} min); ${ROME_SET.size} ROME codes`); process.exit(0); }

const release = acquireLock(out, '_lba.lock');
if (!release) { log('another harvest_lba run is active (lock _lba.lock); exiting'); process.exit(0); }
let stop = false; process.on('SIGINT', () => { stop = true; }); process.on('SIGTERM', () => { stop = true; });

// ---------------------------------------------------------------- HTTP
class Stop extends Error { constructor(reason, detail) { super(reason); this.reason = reason; this.detail = detail; } }
let lastCall = 0, runCalls = 0; const runStatus = {}; const warned = new Set();
async function apiGet(path, qs) { // authenticated GET of the La bonne alternance API, paced, 429-aware
  const url = `${BASE}${path}${qs && String(qs) ? '?' + qs : ''}`;
  for (let attempt = 0; attempt < 4; attempt++) {
    if (stop) throw new Stop('interrupted');
    if (runCalls >= MAX_CALLS) throw new Stop('max_calls');
    const wait = lastCall + DELAY_MS - Date.now(); if (wait > 0) await sleep(wait);
    lastCall = Date.now(); runCalls++; manifest.totals.calls++;
    let r, txt;
    try { r = await fetch(url, { headers: { Authorization: 'Bearer ' + KEY, Accept: 'application/json', 'User-Agent': UA }, signal: AbortSignal.timeout(60000) }); txt = await r.text(); }
    catch (e) { runStatus.neterr = (runStatus.neterr || 0) + 1; log('network error', e.cause?.code || e.message); await sleep(3000 * (attempt + 1)); continue; }
    runStatus[r.status] = (runStatus[r.status] || 0) + 1;
    const rem = Number(r.headers.get('x-ratelimit-remaining')), reset = Number(r.headers.get('x-ratelimit-reset'));
    if (r.status === 429) {
      const ra = Number(r.headers.get('retry-after')) || reset || 60; manifest.rate_limited = (manifest.rate_limited || 0) + 1;
      if (ra > 180 || attempt >= 2) throw new Stop('http_429', 'retry-after ' + ra + ' s');
      log(`HTTP 429 - waiting ${ra} s (retry-after)`); await sleep((ra + 1) * 1000); continue;
    }
    if (r.status === 401 || r.status === 403) throw new Stop('auth_' + r.status, txt.slice(0, 200));
    if (r.status >= 500) { log('HTTP', r.status, '- retrying'); await sleep(5000 * (attempt + 1)); continue; }
    if (Number.isFinite(rem) && rem <= 1 && Number.isFinite(reset) && reset > 0 && reset < 120) await sleep((reset + 1) * 1000); // quota window almost used
    let json = null; try { json = JSON.parse(txt, bigIntSafe); } catch { /* not JSON */ }
    if (r.status === 200 && json === null) { log('HTTP 200 without JSON - retrying'); await sleep(3000); continue; }
    return { status: r.status, json: json || {} };
  }
  throw new Stop('server_errors');
}

// ---------------------------------------------------------------- ingestion
const keys = await loadKeys(OFFERS, o => o._harvest?.key); ensureTrailingNewline(OFFERS);
const offerKey = j => { const id = j.identifier || {}; return String(id.id || (id.partner_job_id ? `${id.partner_label || 'partner'}:${id.partner_job_id}` : 'sha1:' + sha1(JSON.stringify(j)).slice(0, 20))); };
let newOffers = 0, dupOffers = 0, maxJobs = manifest.max_jobs_per_response || 0; const invalid = new Set(manifest.invalid_romes || []); const saturated = manifest.saturated_queries || [];
function ingestJobs(jobs, origin) { // origin = {city, romes} of the query, stored in the `_harvest` block
  const rows = [];
  for (const j of jobs) {
    const k = offerKey(j); if (keys.has(k)) { dupOffers++; continue; } keys.add(k);
    if (j.apply && 'phone' in j.apply) delete j.apply.phone; // data minimisation: no contact phone is kept in the lake
    rows.push({ _harvest: { key: k, fetched_at: nowIso(), ...origin }, ...j });
    const label = j.identifier?.partner_label || 'unknown'; manifest.by_partner[label] = (manifest.by_partner[label] || 0) + 1;
    for (const c of j.offer?.rome_codes || []) manifest.by_rome[c] = (manifest.by_rome[c] || 0) + 1;
  }
  appendLines(OFFERS, rows); newOffers += rows.length; return rows.length;
}
function ingest(json, city, codes) {
  const jobs = Array.isArray(json.jobs) ? json.jobs : []; maxJobs = Math.max(maxJobs, jobs.length);
  for (const w of json.warnings || []) { const m = `${w.code}: ${w.message}`; if (!warned.has(m)) { warned.add(m); log('API warning', m); } }
  ingestJobs(jobs, { city: city.name, romes: codes.join(',') }); return jobs.length;
}
async function searchCodes(city, codes) {
  const qs = new URLSearchParams({ latitude: String(city.lat), longitude: String(city.lon), radius: String(RADIUS), romes: codes.join(',') });
  for (const p of EXCLUDE) qs.append('partners_to_exclude', p);
  const { status, json } = await apiGet('/job/v1/search', qs);
  if (status === 400) {
    if (codes.length > 1) { for (const c of codes) await searchCodes(city, [c]); return 0; } // isolate the offending code
    if (!invalid.has(codes[0])) { invalid.add(codes[0]); log('HTTP 400 for ROME', codes[0], JSON.stringify(json).slice(0, 160)); }
    return 0;
  }
  if (status !== 200) { log('unexpected HTTP', status, 'for', city.name, codes.join(',')); return 0; }
  const n = ingest(json, city, codes);
  if (n >= SATURATION) {
    if (codes.length > 1) { log(`  ${city.name} ${codes.join(',')}: ${n} offers >= ${SATURATION}, querying code by code`); for (const c of codes) await searchCodes(city, [c]); }
    else { saturated.push(`${city.name}|${codes[0]}`); log(`  WARN ${city.name} ${codes[0]}: ${n} offers in one answer (possible server-side cap)`); }
  }
  return n;
}
async function runExport() { // one signed download of the whole country, filtered on our ROME families
  const { status, json } = await apiGet('/job/v1/export');
  if (status !== 200 || !json.url) throw new Stop('export_failed', 'HTTP ' + status + ' ' + JSON.stringify(json).slice(0, 200));
  const sameOrigin = new URL(json.url).origin === new URL(BASE).origin; // never send the API key to another host (signed storage URL)
  log(`export ready (lastUpdate ${json.lastUpdate}); downloading from ${new URL(json.url).host}${sameOrigin ? '' : ' without the API key'}`);
  const res = await fetch(json.url, { headers: { Accept: 'application/json', 'User-Agent': UA, ...(sameOrigin ? { Authorization: 'Bearer ' + KEY } : {}) }, signal: AbortSignal.timeout(600000) });
  if (!res.ok) throw new Stop('export_download_failed', 'HTTP ' + res.status);
  const size = Number(res.headers.get('content-length')) || 0; const maxMb = num(env.LBA_EXPORT_MAX_MB, 800);
  if (size > maxMb * 1048576) throw new Stop('export_too_large', `${(size / 1048576).toFixed(0)} MB > LBA_EXPORT_MAX_MB=${maxMb}`);
  const data = JSON.parse(await res.text(), bigIntSafe);
  const all = Array.isArray(data) ? data : (Array.isArray(data.jobs) ? data.jobs : (Array.isArray(data.offers) ? data.offers : []));
  if (!all.length) throw new Stop('export_unexpected_format', 'no offer list found; top-level ' + (Array.isArray(data) ? 'array' : typeof data === 'object' && data ? 'keys ' + Object.keys(data).slice(0, 8).join(',') : typeof data));
  const offers = all.filter(j => j && j.offer); // the file may also list recruiters (companies open to unsolicited applications): not offers
  const inScope = env.LBA_EXPORT_ALL === '1' ? offers : offers.filter(j => (j.offer.rome_codes || []).some(c => ROME_SET.has(c)));
  const added = ingestJobs(inScope, { city: 'export', romes: '' });
  manifest.export = { at: nowIso(), last_update: json.lastUpdate, bytes: size || null, entries_in_file: all.length, offers_in_file: offers.length, in_scope: inScope.length, new: added, scope: env.LBA_EXPORT_ALL === '1' ? 'all offers' : 'ROME M18xx + M1405 M1419 M1423 M1435 M1889' };
  log(`export: ${all.length} entries, ${offers.length} offers, ${inScope.length} in scope, ${added} new`);
}

// ---------------------------------------------------------------- main
const t0 = nowIso(); const offersBefore = keys.size; let stopReason = 'sweep_complete', stopDetail = null, q = 0;
const ageH = iso => (Date.now() - Date.parse(iso)) / 3600e3;
let sw = manifest.sweep;
if (!flags.has('--export')) {
  if (sw && sw.completed_at && !flags.has('--force') && ageH(sw.started_at) < SWEEP_HOURS) {
    log(`last sweep #${sw.n} started ${sw.started_at} and completed ${sw.completed_at} (${ageH(sw.started_at).toFixed(1)} h ago, < ${SWEEP_HOURS} h): nothing to do (--force to sweep again)`);
    release(); process.exit(0);
  }
  if (!sw || sw.completed_at) sw = manifest.sweep = { n: (sw?.n || 0) + 1, started_at: nowIso(), completed_at: null, next_query: 0, total_queries: TOTAL_Q };
  sw.total_queries = TOTAL_Q; q = sw.next_query || 0;
  log(`start sweep #${sw.n}: ${offersBefore} offers on disk | query ${q}/${TOTAL_Q} | radius ${RADIUS} km | ${PER_CALL} ROME/call | delay ${DELAY_MS} ms | max ${MAX_CALLS} calls`);
} else log(`start export: ${offersBefore} offers on disk`);
try {
  if (flags.has('--export')) { await runExport(); stopReason = 'export_done'; }
  else {
    for (; q < TOTAL_Q; q++) {
      const city = CITIES[Math.floor(q / CHUNKS.length)], codes = CHUNKS[q % CHUNKS.length];
      const before = newOffers; const n = await searchCodes(city, codes);
      log(`[${q + 1}/${TOTAL_Q}] ${city.name} ${codes.join(',')} -> ${n} offers, ${newOffers - before} new | calls ${runCalls}`);
      sw.next_query = q + 1;
      if ((q + 1) % 5 === 0) { manifest.totals.offers = keys.size; save(); }
    }
    sw.completed_at = nowIso(); manifest.totals.sweeps_completed++;
  }
} catch (e) {
  if (e instanceof Stop) { stopReason = e.reason; stopDetail = e.detail || null; if (sw && !flags.has('--export')) sw.next_query = q; if (e.reason.startsWith('auth_')) { log('API key refused (' + e.reason + '): check LBA_API_KEY, create a new key at ' + REGISTER); process.exitCode = 1; } }
  else { stopReason = 'error'; stopDetail = String(e.stack || e).slice(0, 400); log('ERROR', stopDetail); process.exitCode = 1; if (sw && !flags.has('--export')) sw.next_query = q; }
} finally {
  const mode = flags.has('--export') ? 'export' : 'sweep';
  manifest.totals.offers = keys.size; manifest.totals.runs++; manifest.max_jobs_per_response = maxJobs; manifest.invalid_romes = [...invalid]; manifest.saturated_queries = saturated.slice(-40);
  manifest.settings = { endpoint: BASE + '/job/v1/search', auth: 'Authorization: Bearer <LBA_API_KEY>', radius_km: RADIUS, romes_per_call: PER_CALL, delay_ms: DELAY_MS, cities: CITIES.map(c => c.name), rome_chunks: CHUNKS, exclude_partners: EXCLUDE };
  manifest.last_run = { mode, started_at: t0, ended_at: nowIso(), stop_reason: stopReason, stop_detail: stopDetail, calls: runCalls, status: runStatus, new_offers: newOffers, duplicate_offers: dupOffers, offers_on_disk_before: offersBefore, offers_on_disk: keys.size, ...(mode === 'sweep' ? { sweep: sw.n, next_query: sw.next_query, sweep_completed: Boolean(sw.completed_at) } : {}) };
  manifest.run_history = [...(manifest.run_history || []), { started_at: t0, mode, ...(mode === 'sweep' ? { sweep: sw.n } : {}), calls: runCalls, new_offers: newOffers, duplicate_offers: dupOffers, stop_reason: stopReason }].slice(-60);
  save(); release();
  log('RESULT', JSON.stringify({ mode, stop_reason: stopReason, calls: runCalls, new_offers: newOffers, duplicate_offers: dupOffers, offers_on_disk: keys.size, ...(mode === 'sweep' ? { sweep: sw.n, next_query: sw.next_query, of: TOTAL_Q, max_jobs_in_one_answer: maxJobs } : { export: manifest.export }) }));
}
