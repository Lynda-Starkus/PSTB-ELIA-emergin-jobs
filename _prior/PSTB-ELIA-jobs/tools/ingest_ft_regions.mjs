// Collecte régionale France Travail — API Offres d'emploi v2.
// Pour les ~10 intitulés IA les plus présents (FDE forcé), comptage par région
// (18 codes INSEE, métropole + outre-mer), total et publiées ≤ 31 j, plus :
//   - répartition CDI des offres IA (typeContrat=CDI)
//   - part ouverte aux débutants (experienceExige=D)
//   - employeurs réels des offres Forward Deployed Engineer (25 premières offres)
// Sortie : data/ft_regions.json. Usage : node tools/ingest_ft_regions.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const env = {};
for (const line of readFileSync(join(root, '.env'), 'utf8').split(/\r?\n/)) {
  const m = /^([A-Z_]+)=(.+)$/.exec(line.trim());
  if (m) env[m[1]] = m[2];
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
const TOKEN_URL = 'https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire';
const SEARCH = 'https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search';

async function getToken() {
  const body = new URLSearchParams({ grant_type: 'client_credentials', client_id: env.FT_CLIENT_ID,
    client_secret: env.FT_CLIENT_SECRET, scope: 'api_offresdemploiv2 o2dsoffre' });
  const r = await fetch(TOKEN_URL, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body });
  if (!r.ok) throw new Error('OAuth ' + r.status);
  return (await r.json()).access_token;
}
let token = await getToken();
console.log('jeton OK');

async function call(params, raw = false, tries = 4) {
  const qs = new URLSearchParams({ ...params, range: raw ? '0-24' : '0-0' });
  for (let i = 0; i < tries; i++) {
    const r = await fetch(SEARCH + '?' + qs, { headers: { Authorization: 'Bearer ' + token, Accept: 'application/json' } });
    if (r.status === 204) return raw ? { total: 0, resultats: [] } : 0;
    if (r.status === 401 && i === 0) { token = await getToken(); continue; }
    if (r.status === 429 || r.status >= 500) { await sleep(900 * (i + 1)); continue; }
    if (r.status === 200 || r.status === 206) {
      const cr = r.headers.get('content-range') || '';
      const total = Number((/\/(\d+)\s*$/.exec(cr) || [])[1] || 0);
      if (!raw) return total;
      const js = await r.json().catch(() => ({}));
      return { total, resultats: js.resultats || [] };
    }
    if (r.status === 400) return raw ? { total: 0, resultats: [] } : 0;
    throw new Error('HTTP ' + r.status);
  }
  return raw ? { total: 0, resultats: [] } : 0;
}

const REGIONS = [
  ['11', 'Île-de-France'], ['24', 'Centre-Val de Loire'], ['27', 'Bourgogne-Franche-Comté'],
  ['28', 'Normandie'], ['32', 'Hauts-de-France'], ['44', 'Grand Est'], ['52', 'Pays de la Loire'],
  ['53', 'Bretagne'], ['75', 'Nouvelle-Aquitaine'], ['76', 'Occitanie'], ['84', 'Auvergne-Rhône-Alpes'],
  ['93', 'Provence-Alpes-Côte d’Azur'], ['94', 'Corse'],
  ['01', 'Guadeloupe'], ['02', 'Martinique'], ['03', 'Guyane'], ['04', 'La Réunion'], ['06', 'Mayotte'],
];

const tax = JSON.parse(readFileSync(join(root, 'data', 'taxonomy.json'), 'utf8'));
const ft = JSON.parse(readFileSync(join(root, 'data', 'ft_fr.json'), 'utf8'));
const ctx = new Map(tax.families.map(f => [f.id, !!f.is_context]));
const bestTerm = id => {
  const e = ft.results[id]; if (!e || !e.terms) return null;
  const ts = Object.entries(e.terms).sort((a, b) => b[1] - a[1]);
  return ts.length ? ts[0][0] : null;
};
const candidates = tax.titles
  .filter(t => !ctx.get(t.family) && (ft.results[t.id]?.count || 0) > 0 && bestTerm(t.id))
  .sort((a, b) => (ft.results[b.id].count) - (ft.results[a.id].count));
const picked = [];
const fde = candidates.find(t => t.id === 'fde');
for (const t of candidates) { if (picked.length >= 10) break; if (t.id !== 'fde') picked.push(t); }
if (fde) picked.splice(Math.min(9, picked.length), 0, fde);
const TITLES = picked.slice(0, 10);
console.log('intitulés retenus :', TITLES.map(t => t.id).join(', '));

let calls = 0;
const regions = [];
for (const [code, nom] of REGIONS) {
  const titles = {};
  let total = 0, recent = 0, annee = 0;
  const iso = d => d.toISOString().replace(/\.\d{3}Z$/, 'Z');
  const yAgo = new Date(Date.now() - 365 * 864e5);
  for (const t of TITLES) {
    const term = bestTerm(t.id);
    const c = await call({ motsCles: term, region: code }); calls++; await sleep(190);
    let c31 = 0, cy = 0;
    if (c > 0) {
      c31 = await call({ motsCles: term, region: code, publieeDepuis: '31' }); calls++; await sleep(190);
      cy = await call({ motsCles: term, region: code, minCreationDate: iso(yAgo), maxCreationDate: iso(new Date()) }); calls++; await sleep(190);
    }
    titles[t.id] = { count: c, count_31j: c31, count_annee: cy };
    total += c; recent += c31; annee += cy;
  }
  regions.push({ code, nom, total, recent, annee, titles });
  console.log(`  ${nom} — ${total} offres IA (${recent} ≤ 31 j) [${calls} req.]`);
}

/* qualité de l'emploi — agrégats nationaux sur les mêmes intitulés */
let cdi = 0, deb = 0, tot = 0;
for (const t of TITLES) {
  const term = bestTerm(t.id);
  tot += ft.results[t.id].count || 0;
  cdi += await call({ motsCles: term, typeContrat: 'CDI' }); calls++; await sleep(190);
  deb += await call({ motsCles: term, experienceExige: 'D' }); calls++; await sleep(190);
}

/* employeurs FDE réels */
const fdeTerm = bestTerm('fde') || 'forward deployed engineer';
const fdeRaw = await call({ motsCles: fdeTerm }, true); calls++;
const employers = [...new Set(fdeRaw.resultats.map(r => (r.entreprise && r.entreprise.nom || '').trim()).filter(n => n && n.length > 1))].slice(0, 10);

const out = {
  collected_at: new Date().toISOString(),
  api: 'France Travail — Offres d’emploi v2 (filtre region, typeContrat, experienceExige)',
  titles_tracked: TITLES.map(t => ({ id: t.id, label: t.title_fr || t.title_en, term: bestTerm(t.id) })),
  regions,
  quality: { total: tot, cdi, debutants: deb },
  fde: { term: fdeTerm, total: fdeRaw.total, employers },
};
writeFileSync(join(root, 'data', 'ft_regions.json'), JSON.stringify(out, null, 1), 'utf8');
const metro = regions.filter(r => !['01','02','03','04','06'].includes(r.code));
const idf = regions.find(r => r.code === '11');
console.log(`data/ft_regions.json écrit — ${calls} requêtes.`);
console.log(`IDF ${idf.total} / métropole ${metro.reduce((s, r) => s + r.total, 0)} · CDI ${cdi}/${tot} · débutants ${deb}/${tot}`);
console.log('employeurs FDE :', employers.join(' · ') || '(anonymisés)');
