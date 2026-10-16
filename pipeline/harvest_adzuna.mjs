// Adzuna FR: full it-jobs category (all pages) + per-category live counts. Output NDJSON + JSON.
import { readFileSync, appendFileSync, writeFileSync, mkdirSync } from 'node:fs'; import { join } from 'node:path';
const root = process.argv[2]; const out = join(root, 'data-lake', 'raw', 'adzuna'); mkdirSync(out, { recursive: true });
const env = {}; for (const l of readFileSync(join(root, '.env'), 'utf8').split(/\r?\n/)) { const m = /^([A-Z_]+)=(.+)$/.exec(l.trim()); if (m) env[m[1]] = m[2]; }
const auth = `app_id=${env.ADZUNA_APP_ID}&app_key=${env.ADZUNA_APP_KEY}`; const base = 'https://api.adzuna.com/v1/api/jobs/fr';
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function j(u) { for (let i = 0; i < 5; i++) { try { const r = await fetch(u); if (r.status === 429) { await sleep(5000 * (i + 1)); continue; } const t = await r.text(); return [r.status, JSON.parse(t)]; } catch (e) { await sleep(2000 * (i + 1)); } } return [0, {}]; }
const [, cats] = await j(`${base}/categories?${auth}`); const counts = {};
for (const c of cats.results || []) { const [, x] = await j(`${base}/search/1?${auth}&results_per_page=1&category=${c.tag}`); counts[c.tag] = x.count; await sleep(300); }
writeFileSync(join(out, `category_counts_${new Date().toISOString().slice(0, 10)}.json`), JSON.stringify({ collected_at: new Date().toISOString(), counts }, null, 1));
console.log('category counts', counts);
const file = join(out, `it_jobs_${new Date().toISOString().slice(0, 10)}.ndjson`); writeFileSync(file, '');
let n = 0; const seen = new Set();
for (const sort of ['date', 'salary', 'relevance']) {
  for (let p = 1; p <= 400; p++) {
    const [s, x] = await j(`${base}/search/${p}?${auth}&results_per_page=50&category=it-jobs&sort_by=${sort}`);
    if (s !== 200 || !x.results || !x.results.length) { console.log('stop', sort, p, s); break; }
    const lines = []; for (const r of x.results) if (!seen.has(r.id)) { seen.add(r.id); lines.push(JSON.stringify(r)); }
    if (lines.length) appendFileSync(file, lines.join('\n') + '\n'); n += lines.length;
    if (p % 20 === 0) console.log(sort, p, 'unique', seen.size);
    await sleep(350);
  }
}
console.log('DONE unique it-jobs', seen.size);
