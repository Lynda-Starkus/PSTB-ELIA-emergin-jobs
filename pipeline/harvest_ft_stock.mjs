// Full harvest of the France Travail live stock (API Offres d'emploi v2), all sectors, all fields.
// Slicing: creation day × region (× department when a cell exceeds the 3 150 cap). Output: NDJSON per day.
import { readFileSync, writeFileSync, existsSync, appendFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
const root = process.argv[2]; const out = join(root, 'data-lake', 'raw', 'ft_api'); mkdirSync(out, { recursive: true });
const env = {}; for (const l of readFileSync(join(root, '.env'), 'utf8').split(/\r?\n/)) { const m = /^([A-Z_]+)=(.+)$/.exec(l.trim()); if (m) env[m[1]] = m[2]; }
const sleep = ms => new Promise(r => setTimeout(r, ms));
const TOKEN_URL = 'https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire';
const SEARCH = 'https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search';
async function getToken() { const body = new URLSearchParams({ grant_type: 'client_credentials', client_id: env.FT_CLIENT_ID, client_secret: env.FT_CLIENT_SECRET, scope: 'api_offresdemploiv2 o2dsoffre' }); const r = await fetch(TOKEN_URL, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body }); if (!r.ok) throw new Error('OAuth ' + r.status); return (await r.json()).access_token; }
let token = await getToken(); let calls = 0; let kept = 0;
async function req(params, range, tries = 6) {
  const qs = new URLSearchParams({ ...params, sort: '1', range });
  for (let i = 0; i < tries; i++) {
    let r; try { r = await fetch(SEARCH + '?' + qs, { headers: { Authorization: 'Bearer ' + token, Accept: 'application/json' } }); } catch (e) { await sleep(1500 * (i + 1)); continue; }
    calls++;
    if (r.status === 204) return { total: 0, rows: [] };
    if (r.status === 401) { token = await getToken(); continue; }
    if (r.status === 429 || r.status >= 500) { await sleep(1200 * (i + 1)); continue; }
    if (r.status === 200 || r.status === 206) { const cr = r.headers.get('content-range') || ''; const total = Number((/\/(\d+)\s*$/.exec(cr) || [])[1] || 0); const js = await r.json().catch(() => ({})); return { total, rows: js.resultats || [] }; }
    if (r.status === 400) return { total: 0, rows: [] };
    await sleep(800);
  }
  return { total: 0, rows: [] };
}
const DEPTS = { '11': ['75', '77', '78', '91', '92', '93', '94', '95'], '24': ['18', '28', '36', '37', '41', '45'], '27': ['21', '25', '39', '58', '70', '71', '89', '90'], '28': ['14', '27', '50', '61', '76'], '32': ['02', '59', '60', '62', '80'], '44': ['08', '10', '51', '52', '54', '55', '57', '67', '68', '88'], '52': ['44', '49', '53', '72', '85'], '53': ['22', '29', '35', '56'], '75': ['16', '17', '19', '23', '24', '33', '40', '47', '64', '79', '86', '87'], '76': ['09', '11', '12', '30', '31', '32', '34', '46', '48', '65', '66', '81', '82'], '84': ['01', '03', '07', '15', '26', '38', '42', '43', '63', '69', '73', '74'], '93': ['04', '05', '06', '13', '83', '84'], '94': ['2A', '2B'], '01': ['971'], '02': ['972'], '03': ['973'], '04': ['974'], '06': ['976'] };
async function drain(params, file, seen) {
  for (let s = 0; s < 3150; s += 150) {
    const { rows } = await req(params, s + '-' + Math.min(s + 149, 3149));
    const lines = []; for (const r of rows) { if (r && r.id && !seen.has(r.id)) { seen.add(r.id); lines.push(JSON.stringify(r)); } }
    if (lines.length) { appendFileSync(file, lines.join('\n') + '\n'); kept += lines.length; }
    await sleep(120);
    if (rows.length < 150) break;
  }
}
const start = new Date(process.argv[3] || '2026-05-20'); const end = new Date(process.argv[4] || new Date().toISOString().slice(0, 10));
const log = join(out, '_harvest.log');
for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
  const day = d.toISOString().slice(0, 10); const file = join(out, `ft_${day}.ndjson`);
  if (existsSync(file + '.done')) continue;
  const seen = new Set(); if (existsSync(file)) writeFileSync(file, '');
  const win = { minCreationDate: day + 'T00:00:00Z', maxCreationDate: day + 'T23:59:59Z' };
  const { total } = await req(win, '0-0'); await sleep(120);
  if (total === 0) { writeFileSync(file + '.done', '0'); continue; }
  if (total <= 3150) await drain(win, file, seen);
  else for (const [reg, deps] of Object.entries(DEPTS)) {
    const { total: tr } = await req({ ...win, region: reg }, '0-0'); await sleep(120);
    if (tr === 0) continue;
    if (tr <= 3150) await drain({ ...win, region: reg }, file, seen);
    else for (const dep of deps) await drain({ ...win, departement: dep }, file, seen);
  }
  // offers whose lieuTravail has no region (rare) — national pass only if total small; otherwise accept loss
  writeFileSync(file + '.done', String(seen.size));
  appendFileSync(log, `${new Date().toISOString()} ${day} total=${total} kept=${seen.size} calls=${calls}\n`);
  console.log(day, 'total', total, 'kept', seen.size, 'calls', calls);
}
console.log('DONE kept', kept, 'calls', calls);
