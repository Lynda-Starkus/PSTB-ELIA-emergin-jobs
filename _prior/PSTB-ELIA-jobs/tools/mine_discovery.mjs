// Fouille des intitulés — découverte de groupes et sous-groupes émergents.
//
// Corpus France (FT + CSP + BPCE) :
//   1. normalisation des intitulés (genre, niveaux, ponctuation, casse) ;
//   2. filtre lexical IA (le périmètre de l'étude) ;
//   3. regroupement par similarité de Jaccard sur les ensembles de tokens
//      (union-find, seuil 0,55) — groupes d'intitulés équivalents ;
//   4. score de sous-groupe : taille × fraîcheur (part ≤ 31 j, offres FT datées)
//      × bonus hors-nomenclature (ni taxonomie ELIA, ni appellation classique) ;
//   5. sortie : groupes classés, exemples bruts à l'appui, candidats « émergents ».
//
// Archive HN (2011→2026, 91 660 annonces) : détection d'APPARITIONS — n-grammes
// de rôles (…engineer/scientist/officer/…) vus pour la première fois ≥ 2022,
// avec volume, vélocité 12 mois et premier mois d'apparition.
//
// Déterministe, sans dépendance. Sortie : data/discovery.json
// Usage : node tools/mine_discovery.mjs
import { readFileSync, writeFileSync, existsSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const tax = JSON.parse(readFileSync(join(root, 'data', 'taxonomy.json'), 'utf8'));

/* ============ corpus France ============ */
const ft = existsSync(join(root, 'data', 'corpus_ft.json')) ? JSON.parse(readFileSync(join(root, 'data', 'corpus_ft.json'), 'utf8')) : { offers: [] };
const pub = existsSync(join(root, 'data', 'corpus_public.json')) ? JSON.parse(readFileSync(join(root, 'data', 'corpus_public.json'), 'utf8')) : { csp: [], bpce: [] };
const NOW = Date.now(), D31 = 31 * 864e5;

const LEVEL_WORDS = /\b(senior|sr|junior|jr|lead|head of|principal|staff|confirm[ée]e?|exp[ée]riment[ée]e?|d[ée]butant e?|stagiaire|stage|alternance|alternant e?|apprenti e?|intern(ship)?|cdi|cdd|freelance|consultant e? senior)\b/g;
function normalize(t){
  let s = String(t).toLowerCase()
    .replace(/\((h\/f|f\/h|m\/f|f\/m|h\/f\/x|x\/f\/h|it)\)/g, ' ')
    .replace(/\b(h\/f|f\/h|m\/f|f\/m)\b/g, ' ')
    .replace(/[“”"«»()\[\]{}]/g, ' ')
    .replace(/\s[-–—|/]\s.*$/, ' ')          /* coupe les suffixes « — Paris / CDI » */
    .replace(/\b(cdi|cdd|t[ée]l[ée]travail|remote|paris|lyon|france)\b/g, ' ')
    .replace(LEVEL_WORDS, ' ')
    .replace(/[^a-z0-9àâäéèêëîïôöùûüç&+.#-]+/g, ' ')
    .replace(/\s+/g, ' ').trim();
  return s;
}
const STOP = new Set(['de','du','des','la','le','les','un','une','et','en','d','l','pour','chez','au','aux','sur','a','à','of','the','and','in','ai']);
const tokens = s => new Set(s.split(' ').filter(w => w.length > 1 && !STOP.has(w)));
const jacc = (a, b) => {
  let inter = 0; for (const x of a) if (b.has(x)) inter++;
  return inter / (a.size + b.size - inter || 1);
};

const AI_LEX = /\b(ia|intelligence artificielle|a\.i\.|genai|gen ai|g[ée]n[ée]rative|llm|gpt|machine learning|deep learning|ml ?ops|llm ?ops|data scien|nlp|computer vision|prompt|rag|agent (ia|ai)|agents? autonomes?|chatbot|copilot|mistral|openai|anthropic|hugging ?face|mod[èe]les? de (langage|fondation)|ai act|red team|fine ?tun|annotation|labell?ing|spee?ch|vision par ordinateur)\b|\bai\b/;
/* homonymes d'acronymes à exclure : « IA » = inspecteur d'académie (éducation nationale), etc. */
const AI_FALSE = /ia[- ]?ipr|\bipr\b|inspecteur|inspectrice|rectorat|dasen|acad[ée]mie|instruction en famille|\bien\b.{0,20}degr/;

const rows = [];
for (const o of ft.offers || []){
  rows.push({ t: o.t, n: normalize(o.t), src: 'FT', recent: o.d && (NOW - Date.parse(o.d)) < D31, y: o.d ? Number(o.d.slice(0, 4)) : 0 });
}
for (const it of pub.csp || []){
  const t = Array.isArray(it) ? it[0] : it, y = Array.isArray(it) ? (it[1] || 0) : 0;
  rows.push({ t, n: normalize(t), src: 'CSP', recent: null, y });
}
for (const t of pub.bpce || []) rows.push({ t, n: normalize(t), src: 'BPCE', recent: null, y: 0 });
const adz = existsSync(join(root, 'data', 'corpus_adzuna.json')) ? JSON.parse(readFileSync(join(root, 'data', 'corpus_adzuna.json'), 'utf8')) : null;
for (const it of (adz && adz.titles) || []) rows.push({ t: it[0], n: normalize(it[0]), src: 'ADZ', recent: null, y: it[1] || 0 });
const corpusTotal = rows.length;
const aiRows = rows.filter(r => r.n && AI_LEX.test(r.n) && !AI_FALSE.test(r.n));
console.log(`corpus FR : ${corpusTotal} intitulés (FT ${ft.offers.length} · CSP ${pub.csp.length} · BPCE ${pub.bpce.length}) — périmètre IA : ${aiRows.length}`);

/* dédup exact avant clustering (compte conservé) */
const uniq = new Map();
for (const r of aiRows){
  const e = uniq.get(r.n) || { n: r.n, toks: tokens(r.n), count: 0, recent: 0, dated: 0, srcs: {}, ex: new Map(), years: {} };
  e.count++;
  if (r.recent !== null){ e.dated++; if (r.recent) e.recent++; }
  if (r.y) e.years[r.y] = (e.years[r.y] || 0) + 1;
  e.srcs[r.src] = (e.srcs[r.src] || 0) + 1;
  e.ex.set(r.t, (e.ex.get(r.t) || 0) + 1);
  uniq.set(r.n, e);
}
const items = [...uniq.values()].filter(e => e.n.length > 2);

/* union-find sur Jaccard ≥ .55 (candidats appariés via token partagé pour éviter O(n²) plein) */
const parent = items.map((_, i) => i);
const find = i => { while (parent[i] !== i){ parent[i] = parent[parent[i]]; i = parent[i]; } return i; };
const union = (a, b) => { const ra = find(a), rb = find(b); if (ra !== rb) parent[rb] = ra; };
const byTok = new Map();
items.forEach((e, i) => { for (const w of e.toks){ if (!byTok.has(w)) byTok.set(w, []); byTok.get(w).push(i); } });
for (const [, list] of byTok){
  if (list.length > 600) continue; /* token trop générique */
  const idxs = list.length > 300 ? list.slice(0, 300) : list;
  for (let a = 0; a < idxs.length; a++)
    for (let b = a + 1; b < idxs.length; b++){
      const i = idxs[a], j = idxs[b];
      if (find(i) === find(j)) continue;
      if (jacc(items[i].toks, items[j].toks) >= 0.55) union(i, j);
    }
}
const clusters = new Map();
items.forEach((e, i) => {
  const r = find(i);
  if (!clusters.has(r)) clusters.set(r, []);
  clusters.get(r).push(e);
});

/* nomenclature connue : taxonomie ELIA (fr/en/alias) + quelques classiques */
const KNOWN = [];
for (const t of tax.titles){
  for (const s of [t.title_fr, t.title_en, ...(t.aliases || [])])
    if (s) KNOWN.push({ id: t.id, n: normalize(s), toks: tokens(normalize(s)) });
}
const knownMatch = toks => {
  let best = null, bs = 0;
  for (const k of KNOWN){ const j = jacc(toks, k.toks); if (j > bs){ bs = j; best = k.id; } }
  return bs >= 0.6 ? best : null;
};

const groups = [...clusters.values()].map(members => {
  members.sort((a, b) => b.count - a.count);
  const label = members[0].n;
  const count = members.reduce((s, m) => s + m.count, 0);
  const dated = members.reduce((s, m) => s + m.dated, 0);
  const recent = members.reduce((s, m) => s + m.recent, 0);
  const srcs = {};
  for (const m of members) for (const [k, v] of Object.entries(m.srcs)) srcs[k] = (srcs[k] || 0) + v;
  const ex = new Map();
  for (const m of members) for (const [raw, c] of m.ex) ex.set(raw, (ex.get(raw) || 0) + c);
  const examples = [...ex.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4).map(x => x[0]);
  const known = knownMatch(tokens(label)) || members.map(m => knownMatch(m.toks)).find(Boolean) || null;
  const freshness = dated ? recent / dated : 0.5;
  const years = {};
  for (const m of members) for (const [y, c] of Object.entries(m.years)) years[y] = (years[y] || 0) + c;
  const early = (years[2022] || 0) + (years[2023] || 0), late = (years[2025] || 0) + (years[2026] || 0);
  const velocity = (early + late >= 6 && early > 0) ? Math.round(late / early * 10) / 10 : null;
  const score = Math.round(count * (0.45 + freshness) * (known ? 0.18 : 1) * (velocity !== null && velocity >= 2 ? 1.3 : 1) * 10) / 10;
  return { label, count, variants: members.length, recent_share: dated ? Math.round(freshness * 100) : null,
           srcs, examples, known, score, velocity, years };
}).filter(g => g.count >= 3).sort((a, b) => b.score - a.score);

const candidates = groups.filter(g => !g.known).slice(0, 18);
const knownTop = groups.filter(g => g.known).slice(0, 10);
console.log(`groupes IA : ${groups.length} — candidats hors nomenclature : ${candidates.length}`);
console.log('top candidats :', candidates.slice(0, 6).map(c => c.label + ' (' + c.count + ')').join(' · '));

/* ============ apparitions HN ============ */
const CACHE = join(root, '.cache', 'hn');
const idx = JSON.parse(readFileSync(join(CACHE, 'index.json'), 'utf8'));
const months = idx.months.filter(m => m < new Date().toISOString().slice(0, 7));
const ROLE = '(engineer|engineering|scientist|researcher|architect|designer|manager|developer|lead|officer|specialist|strategist)';
const NG = new RegExp('\\b([a-z][a-z&+.#-]{1,18}(?: [a-z][a-z&+.#-]{1,18}){0,2}) ' + ROLE + 's?\\b', 'g');
const BAN = new Set(['software','senior','staff','full stack','fullstack','front end','frontend','back end','backend','web','mobile','ios','android','data','devops','platform','product','project','qa','test','security','infrastructure','cloud','site reliability','machine learning','electrical','mechanical','civil','sales','marketing','growth','support','hardware','embedded','network','systems','system','principal','lead','founding','senior software','devops platform','designer']);
const series = new Map();
for (let mi = 0; mi < months.length; mi++){
  const { texts } = JSON.parse(readFileSync(join(CACHE, months[mi] + '.json'), 'utf8'));
  const seenInMonth = new Map();
  for (const tx of texts){
    NG.lastIndex = 0; let m;
    const seenInPost = new Set();
    while ((m = NG.exec(tx))){
      const g = (m[1] + ' ' + m[2]).replace(/\s+/g, ' ').trim();
      if (m[1].length < 2 || BAN.has(m[1]) || seenInPost.has(g)) continue;
      if (/(^| )(and|or|with|alongside|our|your|their|his|her|its|of|for|to|the|a|an|human|humans|as|we|you|is|are|from|by|at|on|like|via|plus|using|both|other)( |$)/.test(m[1])) continue;
      seenInPost.add(g);
      seenInMonth.set(g, (seenInMonth.get(g) || 0) + 1);
    }
  }
  for (const [g, c] of seenInMonth){
    if (!series.has(g)) series.set(g, new Array(months.length).fill(0));
    series.get(g)[mi] = c;
  }
}
const i2022 = months.indexOf('2022-01');
const knownNg = g => { const t = tokens(g.replace(/-/g, ' ')); return KNOWN.some(k => jacc(t, k.toks) >= 0.6); };
const appear = [];
for (const [g, arr] of series){
  const total = arr.reduce((s, v) => s + v, 0);
  if (total < 8) continue;
  let first = arr.findIndex(v => v > 0);
  if (first < i2022) continue;                       /* apparition récente uniquement */
  const last12 = arr.slice(-12).reduce((s, v) => s + v, 0);
  const prev12 = arr.slice(-24, -12).reduce((s, v) => s + v, 0);
  if (!AI_LEX.test(g) && !/agent|eval|inference|forward|prompt|model|ml |llm/.test(g)) continue;
  appear.push({ ngram: g, first_seen: months[first], total, last12, prev12,
    growth: prev12 >= 4 ? Math.round((last12 - prev12) / prev12 * 100) : null,
    known: knownNg(g) });
}
appear.sort((a, b) => b.total - a.total);
const appearTop = appear.slice(0, 34);
console.log(`apparitions HN ≥ 2022 : ${appear.length} n-grammes retenus — inédits : ${appear.filter(a => !a.known).length}`);
console.log('exemples inédits :', appear.filter(a => !a.known).slice(0, 8).map(a => a.ngram).join(' · '));

/* ============ sortie ============ */
const out = {
  mined_at: new Date().toISOString(),
  method: 'normalisation → filtre lexical IA (avec exclusion des homonymes, ex. IA-IPR) → clustering Jaccard ≥ 0,55 (union-find) → score = taille × (0,45 + fraîcheur ≤31 j) × vélocité 2025-26/2022-23 × 0,18 si déjà en nomenclature ; HN : n-grammes de rôles apparus ≥ 2022, ≥ 8 mentions.',
  fr: {
    corpus_total: corpusTotal, corpus_ai: aiRows.length,
    by_source: { FT: ft.offers.length, CSP: pub.csp.length, BPCE: pub.bpce.length, ADZ: (adz && adz.titles || []).length },
    groups_count: groups.length, candidates, known_top: knownTop,
  },
  hn: { months_span: [months[0], months[months.length - 1]], appear: appearTop },
};
writeFileSync(join(root, 'data', 'discovery.json'), JSON.stringify(out), 'utf8');
console.log('data/discovery.json écrit (' + Math.round(JSON.stringify(out).length / 1024) + ' KB).');
