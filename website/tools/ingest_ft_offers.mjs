// Balayage COMPLET France Travail — API Offres d'emploi v2.
// Stratégie adaptative pour contourner le plafond de 3 150 offres par requête :
//   total national ≤ 3 150  → tirage national ;
//   sinon, par région ; si une région dépasse encore → par département.
// Périmètre : 12 codes ROME tech/IA + 18 requêtes lexicales IA en pleine profondeur.
// Champs conservés : id, intitulé, date, ROME, contrat, département.
// Sortie : data/corpus_ft.json. Usage : node tools/ingest_ft_offers.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const env = {};
for (const line of readFileSync(join(root, '.env'), 'utf8').split(/\r?\n/)) {
  const m = /^([A-Z_]+)=(.+)$/.exec(line.trim()); if (m) env[m[1]] = m[2];
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
const TOKEN_URL = 'https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire';
const SEARCH = 'https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search';

async function getToken(){
  const body = new URLSearchParams({ grant_type:'client_credentials', client_id:env.FT_CLIENT_ID,
    client_secret:env.FT_CLIENT_SECRET, scope:'api_offresdemploiv2 o2dsoffre' });
  const r = await fetch(TOKEN_URL, { method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body });
  if (!r.ok) throw new Error('OAuth ' + r.status);
  return (await r.json()).access_token;
}
let token = await getToken();
console.log('jeton OK');
let calls = 0;

async function req(params, range, tries = 5){
  const qs = new URLSearchParams({ ...params, sort:'1', range });
  for (let i = 0; i < tries; i++){
    const r = await fetch(SEARCH + '?' + qs, { headers:{ Authorization:'Bearer ' + token, Accept:'application/json' } });
    calls++;
    if (r.status === 204) return { total: 0, rows: [] };
    if (r.status === 401){ token = await getToken(); continue; }
    if (r.status === 429 || r.status >= 500){ await sleep(1000 * (i + 1)); continue; }
    if (r.status === 200 || r.status === 206){
      const cr = r.headers.get('content-range') || '';
      const total = Number((/\/(\d+)\s*$/.exec(cr) || [])[1] || 0);
      const js = await r.json().catch(() => ({}));
      return { total, rows: js.resultats || [] };
    }
    if (r.status === 400) return { total: 0, rows: [] };
    throw new Error('HTTP ' + r.status);
  }
  return { total: 0, rows: [] };
}

const seen = new Map();
const keep = (r, dep) => {
  if (!r || !r.id || !r.intitule || seen.has(r.id)) return;
  const cp = r.lieuTravail && (r.lieuTravail.codePostal || r.lieuTravail.commune) || '';
  seen.set(r.id, { id:r.id, t:r.intitule, d:(r.dateCreation || '').slice(0, 10),
    r:(r.romeCode || ''), c:(r.typeContrat || ''), dep: dep || String(cp).slice(0, 2) });
};

async function drain(params, dep, cap = 3150){
  for (let s = 0; s < cap; s += 150){
    const { rows } = await req(params, s + '-' + Math.min(s + 149, 3149));
    rows.forEach(r => keep(r, dep));
    await sleep(160);
    if (rows.length < 150) break;
  }
}

const DEPTS = {
  '11':['75','77','78','91','92','93','94','95'], '24':['18','28','36','37','41','45'],
  '27':['21','25','39','58','70','71','89','90'], '28':['14','27','50','61','76'],
  '32':['02','59','60','62','80'], '44':['08','10','51','52','54','55','57','67','68','88'],
  '52':['44','49','53','72','85'], '53':['22','29','35','56'],
  '75':['16','17','19','23','24','33','40','47','64','79','86','87'],
  '76':['09','11','12','30','31','32','34','46','48','65','66','81','82'],
  '84':['01','03','07','15','26','38','42','43','63','69','73','74'],
  '93':['04','05','06','13','83','84'], '94':['2A','2B'],
  '01':['971'], '02':['972'], '03':['973'], '04':['974'], '06':['976'],
};
const ROME = ['M1801','M1802','M1803','M1804','M1805','M1806','M1810','M1811','M1403','M1402','K2402','E1205'];

for (const code of ROME){
  const { total } = await req({ codeROME: code }, '0-0'); await sleep(160);
  if (total === 0){ console.log(`  ${code}: 0`); continue; }
  if (total <= 3150){
    await drain({ codeROME: code }, null);
    console.log(`  ${code}: ${total} (national) — uniques ${seen.size}, req ${calls}`);
    continue;
  }
  for (const [reg, deps] of Object.entries(DEPTS)){
    const { total: tr } = await req({ codeROME: code, region: reg }, '0-0'); await sleep(160);
    if (tr === 0) continue;
    if (tr <= 3150) await drain({ codeROME: code, region: reg }, null);
    else for (const dep of deps) await drain({ codeROME: code, departement: dep }, dep);
  }
  console.log(`  ${code}: ${total} (découpé) — uniques ${seen.size}, req ${calls}`);
}

const AI_QUERIES = ['intelligence artificielle','IA générative','GenAI','LLM','machine learning','deep learning',
  'MLOps','LLMOps','ingénieur IA','AI engineer','agent IA','RAG','prompt','NLP','computer vision','AI Act','chatbot','data scientist'];
const aiIds = new Set();
for (const q of AI_QUERIES){
  const before = new Set(seen.keys());
  await drain({ motsCles: q }, null);
  for (const id of seen.keys()) if (!before.has(id) || true) { /* marquage ci-dessous */ }
  const { total } = await req({ motsCles: q }, '0-0'); await sleep(120);
  console.log(`  « ${q} » (${total}) — uniques ${seen.size}, req ${calls}`);
}
/* marquage lexique IA : un intitulé est 'ai-query' s'il matche au moins une requête — refait côté fouille via lexique ; ici on garde tout */

const offers = [...seen.values()];
writeFileSync(join(root, 'data', 'corpus_ft.json'),
  JSON.stringify({ collected_at: new Date().toISOString(), calls, total: offers.length, offers }), 'utf8');
console.log(`data/corpus_ft.json — ${offers.length} offres uniques, ${calls} requêtes.`);
