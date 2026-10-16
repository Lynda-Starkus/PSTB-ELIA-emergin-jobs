// Shared helpers of the harvesters added on 15 Oct 2026 (Adzuna all categories, La bonne alternance, Jooble, Careerjet).
// House style kept: project root = first non-flag argument (default: parent folder of pipeline/), credentials from <root>/.env
// (process.env wins), raw data under data-lake/raw/<source>/ as NDJSON, a _stdout.log next to the data, idempotent + resumable runs
// (dedupe on the source id, append only new records, small JSON manifest with counts and timestamps).
import { readFileSync, writeFileSync, appendFileSync, existsSync, mkdirSync, renameSync, openSync, readSync, closeSync, statSync, unlinkSync, createReadStream } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createInterface } from 'node:readline';
import { createHash } from 'node:crypto';

export const sleep = ms => new Promise(r => setTimeout(r, ms));
export const nowIso = () => new Date().toISOString();
// HARVEST_TODAY (YYYY-MM-DD) is a test hook used to simulate "tomorrow"; never set it in production.
export const todayUtc = () => process.env.HARVEST_TODAY || new Date().toISOString().slice(0, 10);
export const addDays = (d, n) => { const x = new Date(d + 'T00:00:00Z'); x.setUTCDate(x.getUTCDate() + n); return x.toISOString().slice(0, 10); };
export const UA = 'ELIA-research-harvester/1.0 (academic study of emerging AI jobs in France; API access only)';
export const num = (v, d) => { if (v === undefined || v === null || v === '') return d; const x = Number(v); return Number.isFinite(x) ? x : d; };

// Exact decimal ids: JSON.parse would round integers above 2^53 (Jooble ids are 64-bit); Node >= 22 gives the source text to the reviver.
export const bigIntSafe = (k, v, ctx) => (typeof v === 'number' && Number.isInteger(v) && !Number.isSafeInteger(v) && ctx && ctx.source) ? ctx.source : v;

export function rootAndFlags(metaUrl) {
  const args = process.argv.slice(2);
  const flags = new Set(args.filter(a => a.startsWith('--')));
  const pos = args.filter(a => !a.startsWith('--'));
  const root = pos[0] ? resolve(pos[0]) : resolve(dirname(fileURLToPath(metaUrl)), '..');
  return { root, flags, args };
}

const PLACEHOLDER = /^(x{3,}|\.{3}|<.*>|your[-_ ]?(api[-_ ]?)?key.*|changeme|todo|none|null|undefined)$/i;
export const isPlaceholder = v => !v || PLACEHOLDER.test(String(v).trim());

export function loadEnv(root) {
  const env = {}; const f = join(root, '.env');
  if (existsSync(f)) {
    for (const raw of readFileSync(f, 'utf8').split(/\r?\n/)) {
      const l = raw.trim(); if (!l || l.startsWith('#')) continue;
      const m = /^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(l); if (!m) continue;
      let v = m[2].trim(); if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
      if (v && !isPlaceholder(v)) env[m[1]] = v; // empty or placeholder value = key not provided yet
    }
  }
  for (const [k, v] of Object.entries(process.env)) if (v !== undefined && v !== '') env[k] = v;
  return env;
}

export function makeLogger(dir, tag) {
  mkdirSync(dir, { recursive: true });
  const f = join(dir, '_stdout.log');
  return (...a) => {
    const line = a.map(x => (typeof x === 'string' ? x : JSON.stringify(x))).join(' ');
    console.log(line);
    try { appendFileSync(f, `${nowIso()} [${tag}] ${line}\n`); } catch { /* log must never break a harvest */ }
  };
}

export function readJson(file, fallback = null) { try { return JSON.parse(readFileSync(file, 'utf8')); } catch { return fallback; } }
export function writeJsonAtomic(file, obj) {
  const tmp = file + '.tmp'; writeFileSync(tmp, JSON.stringify(obj, null, 1));
  for (let i = 0; i < 6; i++) {
    try { renameSync(tmp, file); return; } catch (e) { if (i === 5) throw e; Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 50 * (i + 1)); }
  }
}

// ---- NDJSON store: ids of what is already on disk, safe append -------------------------------------------------------------------
export async function loadKeys(file, keyOf) {
  const keys = new Set(); if (!existsSync(file)) return keys;
  const rl = createInterface({ input: createReadStream(file, { encoding: 'utf8' }), crlfDelay: Infinity });
  for await (const line of rl) {
    if (!line) continue; let o; try { o = JSON.parse(line, bigIntSafe); } catch { continue; } // tolerate a torn last line
    const k = keyOf(o); if (k !== undefined && k !== null && k !== '') keys.add(String(k));
  }
  return keys;
}
export function ensureTrailingNewline(file) {
  if (!existsSync(file)) return; const n = statSync(file).size; if (!n) return;
  const fd = openSync(file, 'r'); const b = Buffer.alloc(1); readSync(fd, b, 0, 1, n - 1); closeSync(fd);
  if (b[0] !== 10) appendFileSync(file, '\n');
}
export function appendLines(file, objs) { if (objs.length) appendFileSync(file, objs.map(o => JSON.stringify(o)).join('\n') + '\n'); }
export function countLines(file) {
  if (!existsSync(file)) return 0; let n = 0; const buf = readFileSync(file); for (let i = 0; i < buf.length; i++) if (buf[i] === 10) n++; return n;
}

// ---- single-instance lock (a stale lock is stolen when its pid is dead or it is older than staleMs) --------------------------------
export function acquireLock(dir, name, staleMs = 3 * 3600e3) {
  const f = join(dir, name);
  for (let i = 0; i < 2; i++) {
    try {
      const fd = openSync(f, 'wx'); writeFileSync(fd, JSON.stringify({ pid: process.pid, at: nowIso() })); closeSync(fd);
      return () => { try { unlinkSync(f); } catch { /* already gone */ } };
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
      let stale = false;
      try {
        const st = statSync(f); const info = readJson(f, {});
        let alive = true; if (info.pid) { try { process.kill(info.pid, 0); } catch (err) { alive = err.code === 'EPERM'; } }
        stale = !alive || Date.now() - st.mtimeMs > staleMs;
      } catch { stale = true; }
      if (!stale) return null;
      try { unlinkSync(f); } catch { /* raced */ }
    }
  }
  return null;
}

export const redactUrl = u => String(u).replace(/(app_id|app_key|api_key|key)=[^&]+/gi, '$1=***').replace(/(\/api\/)[A-Za-z0-9-]{16,}/, '$1***');
export const sha1 = s => createHash('sha1').update(s).digest('hex');
export const norm = s => String(s || '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

// ---- per-day call ledger for the keyed harvesters (daily budget, persisted) -----------------------------------------------------
export function makeDayLedger(file) {
  const led = readJson(file, null) || { schema: 1, days: {} }; led.days ||= {};
  const day = () => (led.days[todayUtc()] ||= { calls: 0, status: {} });
  const save = () => { for (const d of Object.keys(led.days)) if (d < addDays(todayUtc(), -400)) delete led.days[d]; writeJsonAtomic(file, led); };
  return {
    led,
    used: () => day().calls,
    record: () => { const d = day(); d.calls++; d.last_at = nowIso(); save(); },
    status: s => { const d = day(); d.status[s] = (d.status[s] || 0) + 1; save(); },
    save,
  };
}

// Search keywords shared by Jooble and Careerjet: AI / data / tech job titles, French and English (60).
export const KEYWORDS = [
  // AI and machine learning
  'ingénieur intelligence artificielle', 'AI engineer', 'ingénieur machine learning', 'machine learning engineer', 'data scientist',
  'ingénieur deep learning', 'MLOps', 'ingénieur NLP traitement du langage', 'NLP engineer', 'computer vision',
  'vision par ordinateur', 'LLM', 'IA générative', 'generative AI', 'prompt engineer',
  'chef de projet IA', 'AI product manager', 'chercheur intelligence artificielle', 'AI researcher', 'ingénieur IA embarquée',
  // data
  'data engineer', 'ingénieur data', 'data analyst', 'analyste de données', 'business intelligence',
  'développeur décisionnel', 'data architect', 'architecte data', 'chief data officer', 'data manager',
  'data steward', 'analytics engineer', 'ingénieur big data', 'ingénieur statisticien',
  // software, cloud, security, product
  'développeur full stack', 'développeur web', 'développeur python', 'développeur java', 'développeur javascript',
  'développeur react', 'développeur .net', 'développeur mobile', 'ingénieur logiciel', 'software engineer',
  'ingénieur devops', 'devops engineer', 'ingénieur cloud', 'architecte cloud', 'site reliability engineer',
  'administrateur systèmes et réseaux', 'ingénieur cybersécurité', 'analyste SOC', 'pentester', 'RSSI',
  'chef de projet informatique', 'product owner', 'scrum master', 'architecte logiciel', 'ingénieur test qualité logiciel',
  'développeur embarqué',
];

// ---- keyword x page sweep shared by Jooble and Careerjet ------------------------------------------------------------------------
export class Stop extends Error { constructor(reason, detail) { super(reason); this.reason = reason; this.detail = detail; } }

// A sweep goes through `keywords`; for each keyword it asks page 1, 2, ... until a page is empty, the API says there is no further page,
// `patience` consecutive pages bring no unseen record, or maxPages is reached. Calls are counted per UTC day in <dir>/_calls.json (daily budget),
// spaced delayMs apart; HTTP 429 stops the run cleanly and opens a 15 min cool-down. The cursor (keyword, page) lives in the manifest, so a run that
// stops (budget, 429, crash) continues there; a completed sweep is not repeated before sweepHours unless --force.
// cfg: tag, source, dir, log, flags, keywords, dataFile, manifestFile, budget, delayMs, maxPages, patience, sweepHours, settings,
//      buildRequest(kw, page, state) -> {url, init}, parse(json) -> {items, total, pages}, keyOf(item) -> string, recordOf(item) -> object,
//      onBadRequest({state, json, txt}) -> true when the request was adapted and must be retried, authStatuses
export async function sweepKeywords(cfg) {
  const { tag, source, dir, log, flags, keywords, dataFile, manifestFile, budget, delayMs, maxPages, patience = 2, sweepHours = 20, settings = {},
    buildRequest, parse, keyOf, recordOf = x => x, onBadRequest, authStatuses = [401, 403] } = cfg;
  mkdirSync(dir, { recursive: true });
  const manifest = readJson(manifestFile, null) || { source, schema: 1, created_at: nowIso(), totals: { records: 0, calls: 0, runs: 0, sweeps_completed: 0 }, state: {} };
  manifest.state ||= {};
  const save = () => { manifest.updated_at = nowIso(); writeJsonAtomic(manifestFile, manifest); };
  const ledger = makeDayLedger(join(dir, '_calls.json'));
  const cd = ledger.led.cooldown_until;
  if (cd && Date.parse(cd) > Date.now()) { log('cool-down after HTTP 429 until', cd, '- nothing to do'); return; }
  let sw = manifest.sweep; const ageH = iso => (Date.now() - Date.parse(iso)) / 3600e3;
  if (sw && sw.completed_at && !flags.has('--force') && ageH(sw.started_at) < sweepHours) {
    log(`last sweep #${sw.n} started ${sw.started_at} and completed ${sw.completed_at} (${ageH(sw.started_at).toFixed(1)} h ago, < ${sweepHours} h): nothing to do (--force to sweep again)`); return;
  }
  if (ledger.used() >= budget) { log(`daily budget ${budget} calls already used today (UTC ${todayUtc()}): nothing to do`); return; }
  if (!sw || sw.completed_at) sw = manifest.sweep = { n: (sw?.n || 0) + 1, started_at: nowIso(), completed_at: null, kw_idx: 0, page: 1, keywords: [] };
  sw.keywords ||= [];
  const release = acquireLock(dir, `_${tag}.lock`);
  if (!release) { log(`another ${tag} run is active (lock _${tag}.lock); exiting`); return; }
  let stop = false; process.on('SIGINT', () => { stop = true; }); process.on('SIGTERM', () => { stop = true; });
  let lastCall = 0, runCalls = 0; const runStatus = {};

  async function request(kw, page) {
    for (let attempt = 0; attempt < 4; attempt++) {
      if (stop) throw new Stop('interrupted');
      if (ledger.used() >= budget) throw new Stop('budget');
      const wait = lastCall + delayMs - Date.now(); if (wait > 0) await sleep(wait);
      lastCall = Date.now(); ledger.record(); runCalls++; manifest.totals.calls++;
      const { url, init } = buildRequest(kw, page, manifest.state);
      let r, txt;
      try { r = await fetch(url, { ...init, signal: AbortSignal.timeout(60000) }); txt = await r.text(); }
      catch (e) { ledger.status('neterr'); runStatus.neterr = (runStatus.neterr || 0) + 1; log('network error', e.cause?.code || e.message, redactUrl(url)); await sleep(3000 * (attempt + 1)); continue; }
      ledger.status(r.status); runStatus[r.status] = (runStatus[r.status] || 0) + 1;
      if (r.status === 429) {
        const ra = Number(r.headers.get('retry-after')); ledger.led.cooldown_until = new Date(Date.now() + Math.max(Number.isFinite(ra) ? ra * 1000 : 0, 15 * 60e3)).toISOString(); ledger.save();
        throw new Stop('http_429', 'cool-down until ' + ledger.led.cooldown_until);
      }
      if (authStatuses.includes(r.status)) {
        const cf = r.headers.get('cf-mitigated'); // Cloudflare answers an HTML "Just a moment" page: key unknown / not active, or client blocked
        throw new Stop('auth_' + r.status, cf ? `Cloudflare challenge (cf-mitigated: ${cf}): the key is unknown or not active yet, or this client is blocked; no attempt is made to bypass it` : txt.slice(0, 200));
      }
      if (r.status >= 500) { log('HTTP', r.status, '- retrying'); await sleep(5000 * (attempt + 1)); continue; }
      let json = null; try { json = JSON.parse(txt, bigIntSafe); } catch { /* not JSON */ }
      if (r.status === 400 && onBadRequest && onBadRequest({ state: manifest.state, json, txt })) { log('HTTP 400 - request adapted, retrying:', JSON.stringify(manifest.state)); save(); continue; }
      if (r.status === 200 && json === null) { log('HTTP 200 without JSON - retrying'); await sleep(3000); continue; }
      return { status: r.status, json: json || {}, txt };
    }
    throw new Stop('server_errors');
  }

  const keys = await loadKeys(dataFile, o => o._harvest?.key); ensureTrailingNewline(dataFile);
  const before = keys.size, t0 = nowIso(); let newRecs = 0, dups = 0, stopReason = 'sweep_complete', stopDetail = null;
  log(`start sweep #${sw.n}: ${before} records on disk | keyword ${sw.kw_idx + 1}/${keywords.length} page ${sw.page} | calls today ${ledger.used()}/${budget} | delay ${delayMs} ms`);
  try {
    for (let ki = sw.kw_idx; ki < keywords.length; ki++) {
      const kw = keywords[ki]; let page = ki === sw.kw_idx ? sw.page : 1, low = 0;
      const st = sw.keywords[ki]?.keyword === kw ? sw.keywords[ki] : { keyword: kw, pages: 0, items: 0, new: 0, total: null };
      while (page <= maxPages) {
        const { status, json, txt } = await request(kw, page);
        if (status !== 200) { log(`HTTP ${status} for "${kw}" page ${page}: ${txt.slice(0, 160)} - keyword skipped`); st.error = status; break; }
        const p = parse(json); st.pages++; st.items += p.items.length; if (p.total !== null && p.total !== undefined) st.total = p.total;
        const rows = []; let n = 0;
        for (const it of p.items) {
          const k = keyOf(it); if (!k || keys.has(k)) { dups++; continue; }
          keys.add(k); rows.push({ _harvest: { key: k, fetched_at: nowIso(), keyword: kw, page }, ...recordOf(it) }); n++;
        }
        appendLines(dataFile, rows); newRecs += n; st.new += n;
        log(`[${ki + 1}/${keywords.length}] "${kw}" p${page}: ${p.items.length} items, ${n} new${st.total != null ? ', total ' + st.total : ''} | calls ${runCalls}`);
        low = n === 0 ? low + 1 : 0;
        const last = p.items.length === 0 || (p.pages !== null && p.pages !== undefined && page >= p.pages) || low >= patience;
        page++; sw.kw_idx = ki; sw.page = page; sw.keywords[ki] = st;
        if (last) break;
      }
      sw.kw_idx = ki + 1; sw.page = 1; sw.keywords[ki] = st; manifest.totals.records = keys.size; save();
    }
    sw.completed_at = nowIso(); manifest.totals.sweeps_completed++;
  } catch (e) {
    if (e instanceof Stop) { stopReason = e.reason; stopDetail = e.detail || null; if (e.reason.startsWith('auth_')) { log('request refused (' + e.reason + '):', stopDetail); process.exitCode = 1; } }
    else { stopReason = 'error'; stopDetail = String(e.stack || e).slice(0, 400); log('ERROR', stopDetail); process.exitCode = 1; }
  } finally {
    manifest.totals.records = keys.size; manifest.totals.runs++; manifest.settings = settings;
    manifest.last_run = { started_at: t0, ended_at: nowIso(), stop_reason: stopReason, stop_detail: stopDetail, calls: runCalls, status: runStatus, new_records: newRecs, duplicate_records: dups, records_on_disk_before: before, records_on_disk: keys.size, calls_today: ledger.used(), daily_budget: budget, sweep: sw.n, next_keyword: sw.kw_idx, next_page: sw.page, sweep_completed: Boolean(sw.completed_at) };
    manifest.run_history = [...(manifest.run_history || []), { started_at: t0, sweep: sw.n, calls: runCalls, new_records: newRecs, duplicate_records: dups, stop_reason: stopReason }].slice(-60);
    save(); release();
    log('RESULT', JSON.stringify({ stop_reason: stopReason, calls: runCalls, new_records: newRecs, duplicate_records: dups, records_on_disk: keys.size, calls_today: ledger.used(), sweep: sw.n, keyword: `${sw.kw_idx}/${keywords.length}` }));
  }
}
