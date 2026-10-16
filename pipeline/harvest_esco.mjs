// Walk the ESCO skills hierarchy through the public API; store one JSON line per concept (all language labels).
import { appendFileSync, writeFileSync, existsSync, readFileSync, mkdirSync } from 'node:fs'; import { join } from 'node:path';
const root = process.argv[2]; const out = join(root, 'data-lake', 'raw', 'esco'); mkdirSync(out, { recursive: true });
const file = join(out, 'esco_skills_concepts.ndjson'); const seen = new Set();
if (existsSync(file)) for (const l of readFileSync(file, 'utf8').split('\n')) { if (l) try { seen.add(JSON.parse(l).uri); } catch (e) { } } else writeFileSync(file, '');
const sleep = ms => new Promise(r => setTimeout(r, ms)); let calls = 0;
async function get(uri, kind) {
  const u = `https://ec.europa.eu/esco/api/resource/${kind}?uri=${encodeURIComponent(uri)}&language=fr`;
  for (let i = 0; i < 6; i++) { try { const r = await fetch(u, { headers: { 'User-Agent': 'ELIA-observatory/1.0 (PST&B; recherche)', Accept: 'application/json' } }); calls++; if (r.status === 200) return r.json(); if (r.status === 404) return null; await sleep(1000 * (i + 1)); } catch (e) { await sleep(1500 * (i + 1)); } }
  return null;
}
const queue = [['http://data.europa.eu/esco/concept-scheme/skills', 'taxonomy']];
const pick = o => o ? Object.fromEntries(Object.entries(o).map(([k, v]) => [k, v])) : null;
while (queue.length) {
  const [uri, kind] = queue.shift(); if (seen.has(uri)) continue;
  const js = await get(uri, kind); if (!js) { seen.add(uri); continue; }
  const links = js._links || {}; const rec = { uri, kind, className: js.className, title: js.title, preferredLabel: pick(js.preferredLabel), alternativeLabel: pick(js.alternativeLabel), description: js.description ? Object.fromEntries(Object.entries(js.description).filter(([k]) => ['fr', 'en'].includes(k)).map(([k, v]) => [k, v.literal])) : null, skillType: js.skillType, reuseLevel: js.reuseLevel, broader: (links.broaderConcept || links.broaderSkill || []).map(x => x.uri), status: js.status };
  appendFileSync(file, JSON.stringify(rec) + '\n'); seen.add(uri);
  for (const key of ['hasTopConcept', 'narrowerConcept', 'narrowerSkill']) for (const x of (links[key] || [])) if (!seen.has(x.uri)) queue.push([x.uri, x.className === 'Skill' ? 'skill' : 'concept']);
  if (calls % 200 === 0) console.log('calls', calls, 'seen', seen.size, 'queue', queue.length);
  await sleep(60);
}
console.log('DONE concepts', seen.size, 'calls', calls);
