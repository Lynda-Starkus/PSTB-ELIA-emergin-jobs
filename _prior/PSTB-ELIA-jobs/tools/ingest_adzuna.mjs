// Ingestion Adzuna (api.adzuna.com, pays FR) — secteur privé agrégé.
// Budget prudent (quota gratuit ~250 appels/jour, 25/min → 2,6 s entre appels) :
//   - comptage FR par intitulé IA (what_phrase)            ~45 appels
//   - histogrammes de salaires affichés (12 titres majeurs) ~12
//   - top employeurs (FDE, AI engineer, agents)              3
//   - répartition géographique « intelligence artificielle » 1
//   - corpus privé pour la fouille (2 requêtes paginées)    ~30
// Sortie : data/adzuna.json + data/corpus_adzuna.json
// Usage : node tools/ingest_adzuna.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const env = {};
for (const line of readFileSync(join(root, '.env'), 'utf8').split(/\r?\n/)) {
  const m = /^([A-Z_]+)=(.+)$/.exec(line.trim()); if (m) env[m[1]] = m[2];
}
if (!env.ADZUNA_APP_ID || !env.ADZUNA_APP_KEY){ console.error('clés Adzuna absentes (.env)'); process.exit(1); }
const BASE = 'https://api.adzuna.com/v1/api/jobs/fr';
const AUTH = `app_id=${env.ADZUNA_APP_ID}&app_key=${env.ADZUNA_APP_KEY}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
let calls = 0;

async function get(path, tries = 3){
  for (let i = 0; i < tries; i++){
    const r = await fetch(`${BASE}${path}${path.includes('?') ? '&' : '?'}${AUTH}&content-type=application/json`);
    calls++;
    if (r.status === 429){ console.log('   (429 — pause 65 s)'); await sleep(65000); continue; }
    if (!r.ok){ if (i === tries - 1) return null; await sleep(3000); continue; }
    return r.json().catch(() => null);
  }
  return null;
}
const enc = encodeURIComponent;

const tax = JSON.parse(readFileSync(join(root, 'data', 'taxonomy.json'), 'utf8'));
const ctx = new Map(tax.families.map(f => [f.id, !!f.is_context]));
const aiTitles = tax.titles.filter(t => !ctx.get(t.family));

/* 1 — comptages par intitulé */
const per_title = {};
for (const t of aiTitles){
  const js = await get(`/search/1?what_phrase=${enc(t.title_en)}&results_per_page=1`);
  per_title[t.id] = { count: js && typeof js.count === 'number' ? js.count : null };
  await sleep(2600);
}
console.log(`comptages : ${aiTitles.length} intitulés (${calls} appels)`);

/* 2 — salaires affichés (histogrammes) pour les 12 plus présents */
const topIds = Object.entries(per_title).filter(([, v]) => v.count > 3)
  .sort((a, b) => b[1].count - a[1].count).slice(0, 12).map(([id]) => id);
const pct = (hist, p) => {
  const buckets = Object.entries(hist).map(([k, v]) => [Number(k), v]).sort((a, b) => a[0] - b[0]);
  const total = buckets.reduce((s, [, v]) => s + v, 0);
  if (!total) return null;
  let acc = 0;
  for (const [sal, v] of buckets){ acc += v; if (acc / total >= p) return sal; }
  return buckets[buckets.length - 1][0];
};
for (const id of topIds){
  const t = tax.titles.find(x => x.id === id);
  const js = await get(`/histogram?what_phrase=${enc(t.title_en)}`);
  if (js && js.histogram && Object.keys(js.histogram).length){
    per_title[id].salary = { p25: pct(js.histogram, .25), median: pct(js.histogram, .5), p75: pct(js.histogram, .75) };
  }
  await sleep(2600);
}
console.log(`salaires : ${topIds.length} histogrammes (${calls} appels)`);

/* 3 — top employeurs */
const companies = {};
for (const [key, q] of [['fde', 'forward deployed engineer'], ['ai_engineer', 'AI engineer'], ['agents', 'AI agent']]){
  const js = await get(`/top_companies?what=${enc(q)}`);
  companies[key] = js && js.leaderboard ? js.leaderboard.slice(0, 8).map(c => ({ name: c.canonical_name, count: c.count })) : [];
  await sleep(2600);
}
console.log('employeurs :', Object.values(companies).map(a => a.length).join('/'));

/* 4 — géo */
const geo = await get(`/geodata?what=${enc('intelligence artificielle')}`);
const locations = geo && geo.locations ? geo.locations.slice(0, 20).map(l => ({ name: l.location && l.location.display_name, count: l.count })) : [];
await sleep(2600);

/* 5 — corpus privé pour la fouille */
const corpus = [];
for (const [q, pages] of [['intelligence artificielle', 20], ['machine learning', 10]]){
  for (let p = 1; p <= pages; p++){
    const js = await get(`/search/${p}?what=${enc(q)}&results_per_page=50&sort_by=date`);
    if (!js || !js.results || !js.results.length) break;
    for (const r of js.results){
      if (r.title) corpus.push([String(r.title).replace(/<[^>]+>/g, ''), (r.created || '').slice(0, 4) * 1 || 0]);
    }
    await sleep(2600);
  }
}
console.log(`corpus privé : ${corpus.length} offres (${calls} appels au total)`);

/* global */
const g = await get(`/search/1?what=${enc('intelligence artificielle')}&results_per_page=1`);
const global_count = g && g.count || null;

writeFileSync(join(root, 'data', 'adzuna.json'), JSON.stringify({
  collected_at: new Date().toISOString(), calls, global_count_ia: global_count,
  per_title, salary_ids: topIds, companies, locations,
}, null, 1), 'utf8');
writeFileSync(join(root, 'data', 'corpus_adzuna.json'), JSON.stringify({
  collected_at: new Date().toISOString(), titles: corpus,
}), 'utf8');
console.log(`data/adzuna.json + corpus_adzuna.json écrits — ${calls} appels, « intelligence artificielle » FR : ${global_count} offres.`);
