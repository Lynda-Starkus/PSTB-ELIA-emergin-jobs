// Ingestion France Travail — API « Offres d'emploi » v2 (francetravail.io).
// OAuth2 client_credentials puis, pour chaque intitulé de la taxonomie, comptage
// des offres en ligne (total et publiées ≤ 31 jours) via l'en-tête Content-Range.
// Identifiants lus dans .env (jamais journalisés). Usage :
//   SMOKE=1 node tools/ingest_francetravail.mjs   → test jeton + 1 requête
//   node tools/ingest_francetravail.mjs           → collecte complète (data/ft_fr.json)
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const env = {};
for (const line of readFileSync(join(root, '.env'), 'utf8').split(/\r?\n/)) {
  const m = /^([A-Z_]+)=(.+)$/.exec(line.trim());
  if (m) env[m[1]] = m[2];
}
if (!env.FT_CLIENT_ID || !env.FT_CLIENT_SECRET) { console.error('IDENTIFIANTS ABSENTS (.env)'); process.exit(1); }

const sleep = ms => new Promise(r => setTimeout(r, ms));
const TOKEN_URL = 'https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire';
const SEARCH = 'https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search';

async function getToken() {
  const body = new URLSearchParams({
    grant_type: 'client_credentials',
    client_id: env.FT_CLIENT_ID,
    client_secret: env.FT_CLIENT_SECRET,
    scope: 'api_offresdemploiv2 o2dsoffre',
  });
  const r = await fetch(TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  if (!r.ok) throw new Error('OAuth ' + r.status + ' — ' + (await r.text()).slice(0, 180));
  const js = await r.json();
  console.log('jeton OK (expire dans ' + js.expires_in + ' s, scope ' + (js.scope || '?') + ')');
  return js.access_token;
}

let token = await getToken();

async function countFor(params, tries = 4) {
  const qs = new URLSearchParams({ ...params, range: '0-0' });
  for (let i = 0; i < tries; i++) {
    const r = await fetch(SEARCH + '?' + qs, { headers: { Authorization: 'Bearer ' + token, Accept: 'application/json' } });
    if (r.status === 204) return 0;
    if (r.status === 401 && i === 0) { token = await getToken(); continue; }
    if (r.status === 429 || r.status >= 500) { await sleep(900 * (i + 1)); continue; }
    if (r.status === 200 || r.status === 206) {
      const cr = r.headers.get('content-range') || r.headers.get('Content-Range') || '';
      const m = /\/(\d+)\s*$/.exec(cr);
      if (m) return Number(m[1]);
      const js = await r.json().catch(() => null);
      return js && js.resultats ? js.resultats.length : 0;
    }
    if (r.status === 400) return 0; // terme rejeté par l'API
    throw new Error('search HTTP ' + r.status);
  }
  return null;
}

if (process.env.SMOKE) {
  const n = await countFor({ motsCles: 'forward deployed engineer' });
  console.log('SMOKE forward deployed engineer →', n, 'offres en ligne');
  process.exit(n === null ? 1 : 0);
}

const tax = JSON.parse(readFileSync(join(root, 'data', 'taxonomy.json'), 'utf8'));
const famCtx = new Map(tax.families.map(f => [f.id, !!f.is_context]));
const results = {};
let calls = 0;
for (const t of tax.titles) {
  const ctx = famCtx.get(t.family);
  const terms = [...new Set([t.title_en, t.title_fr, ...(ctx ? [] : (t.aliases || []).slice(0, 1))]
    .filter(s => s && s.length > 3))].slice(0, ctx ? 1 : 3);
  const perTerm = {};
  let best = 0, best31 = 0;
  for (const term of terms) {
    const c = await countFor({ motsCles: term }); calls++; await sleep(220);
    const c31 = await countFor({ motsCles: term, publieeDepuis: '31' }); calls++; await sleep(220);
    if (c !== null) { perTerm[term] = c; if (c > best) { best = c; best31 = c31 ?? 0; } }
  }
  results[t.id] = { count: best, count_31j: best31, terms: perTerm };
  if (calls % 40 < 2) console.log(`  …${calls} requêtes (dernier : ${t.id} → ${best})`);
}
const out = { collected_at: new Date().toISOString(), api: 'France Travail — Offres d\'emploi v2', method: 'comptage Content-Range par mots-clés d\'intitulé (max. des termes)', results };
writeFileSync(join(root, 'data', 'ft_fr.json'), JSON.stringify(out, null, 1), 'utf8');
const totalAI = Object.entries(results).filter(([id]) => { const t = tax.titles.find(x => x.id === id); return t && !famCtx.get(t.family); })
  .reduce((s, [, v]) => s + (v.count || 0), 0);
console.log(`data/ft_fr.json écrit — ${calls} requêtes, ${Object.keys(results).length} intitulés, ≈${totalAI} offres IA en ligne (France).`);
