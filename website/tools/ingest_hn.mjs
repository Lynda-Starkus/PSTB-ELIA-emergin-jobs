// Ingestion Hacker News « Ask HN: Who is hiring? » via l'API publique Algolia.
// Récupère chaque fil mensuel (2011 → aujourd'hui), garde les annonces de premier
// niveau (texte nettoyé, tronqué) dans .cache/hn/<YYYY-MM>.json pour que la
// classification (tools/build_data.mjs) soit rejouable sans re-crawler.
// Usage : node tools/ingest_hn.mjs
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const CACHE = join(root, '.cache', 'hn');
mkdirSync(CACHE, { recursive: true });

const ALG = 'https://hn.algolia.com/api/v1/search_by_date';
const UA = { 'User-Agent': 'ELIA-observatory/1.0 (laboratoire PST&B; usage recherche)' };
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function getJSON(url, tries = 4) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { headers: UA });
      if (r.status === 429 || r.status >= 500) { await sleep(1200 * (i + 1)); continue; }
      if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + url);
      return await r.json();
    } catch (e) {
      if (i === tries - 1) throw e;
      await sleep(1200 * (i + 1));
    }
  }
}

const MONTHS_EN = { january:'01', february:'02', march:'03', april:'04', may:'05', june:'06',
  july:'07', august:'08', september:'09', october:'10', november:'11', december:'12' };

function clean(html) {
  return String(html)
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&#x2F;/g, '/')
    .replace(/\s+/g, ' ').toLowerCase().slice(0, 1100);
}

// 1 — tous les fils « Who is hiring » du compte whoishiring
const stories = await getJSON(`${ALG}?tags=story,author_whoishiring&hitsPerPage=1000`);
const threads = new Map(); // month -> {id, points}
for (const h of stories.hits) {
  const m = /who is hiring\??\s*\((\w+)\s+(\d{4})\)/i.exec(h.title || '');
  if (!m) continue;
  const mon = MONTHS_EN[m[1].toLowerCase()]; if (!mon) continue;
  const key = `${m[2]}-${mon}`;
  const prev = threads.get(key);
  if (!prev || (h.num_comments || 0) > prev.num) threads.set(key, { id: h.objectID, num: h.num_comments || 0 });
}
const months = [...threads.keys()].sort();
console.log(`fils mensuels trouvés : ${months.length} (${months[0]} → ${months[months.length - 1]})`);

// 2 — annonces de premier niveau par fil (avec cache)
let done = 0, fetched = 0;
for (const month of months) {
  const out = join(CACHE, month + '.json');
  if (existsSync(out)) { done++; continue; }
  const { id } = threads.get(month);
  const texts = [];
  let page = 0, nbPages = 1;
  while (page < nbPages && page < 6) {
    const js = await getJSON(`${ALG}?tags=comment,story_${id}&hitsPerPage=1000&page=${page}`);
    nbPages = js.nbPages || 1;
    for (const h of js.hits) {
      if (String(h.parent_id) !== String(id)) continue;   // premier niveau uniquement
      if (!h.comment_text) continue;
      texts.push(clean(h.comment_text));
    }
    page++;
    await sleep(140);
  }
  writeFileSync(out, JSON.stringify({ month, story: id, total: texts.length, texts }), 'utf8');
  done++; fetched++;
  if (fetched % 12 === 0) console.log(`  ${done}/${months.length} fils (dernier : ${month}, ${texts.length} annonces)`);
}
writeFileSync(join(CACHE, 'index.json'), JSON.stringify({ months, crawled_at: new Date().toISOString() }), 'utf8');
console.log(`cache HN complet : ${done}/${months.length} mois (${fetched} crawlés, reste en cache).`);
