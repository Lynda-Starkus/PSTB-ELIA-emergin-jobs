// Série mensuelle × région des offres IA du secteur public (archives CSP, DGAFP).
// Re-streame les CSV data.gouv en extrayant intitulé + date (mois) + région,
// filtre lexical IA (mêmes règles que la fouille, homonymes exclus),
// agrège par mois × région INSEE. Sortie : data/csp_monthly.json
// Usage : node tools/ingest_csp_regions.mjs
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Readable } from 'node:stream';
import { createInterface } from 'node:readline';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const UA = { 'User-Agent': 'ELIA-observatory/1.0 (PST&B; recherche)' };

const AI_LEX = /\b(ia|intelligence artificielle|a\.i\.|genai|gen ai|g[ée]n[ée]rative|llm|gpt|machine learning|deep learning|ml ?ops|llm ?ops|data scien|nlp|computer vision|prompt|rag|agent (ia|ai)|agents? autonomes?|chatbot|mod[èe]les? de (langage|fondation)|ai act|fine ?tun|annotation|vision par ordinateur)\b|\bai\b/;
const AI_FALSE = /ia[- ]?ipr|\bipr\b|inspecteur|inspectrice|rectorat|dasen|acad[ée]mie|instruction en famille|\bien\b.{0,20}degr/;
const strip = s => String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z ]+/g, ' ').replace(/\s+/g, ' ').trim();
const REGION_CODE = new Map(Object.entries({
  'ile de france':'11','centre val de loire':'24','bourgogne franche comte':'27','normandie':'28',
  'hauts de france':'32','grand est':'44','pays de la loire':'52','bretagne':'53',
  'nouvelle aquitaine':'75','occitanie':'76','auvergne rhone alpes':'84',
  'provence alpes cote d azur':'93','provence alpes cote dazur':'93','corse':'94',
  'guadeloupe':'01','martinique':'02','guyane':'03','la reunion':'04','reunion':'04','mayotte':'06',
}));
const DEP2REG = {};
for (const [reg, deps] of Object.entries({ '11':['75','77','78','91','92','93','94','95'],'24':['18','28','36','37','41','45'],'27':['21','25','39','58','70','71','89','90'],'28':['14','27','50','61','76'],'32':['02','59','60','62','80'],'44':['08','10','51','52','54','55','57','67','68','88'],'52':['44','49','53','72','85'],'53':['22','29','35','56'],'75':['16','17','19','23','24','33','40','47','64','79','86','87'],'76':['09','11','12','30','31','32','34','46','48','65','66','81','82'],'84':['01','03','07','15','26','38','42','43','63','69','73','74'],'93':['04','05','06','13','83','84'],'94':['2a','2b'],'01':['971'],'02':['972'],'03':['973'],'04':['974'],'06':['976'] }))
  for (const d of deps) DEP2REG[d] = reg;

const monthOf = raw => {
  if (!raw) return null;
  let m = /(\d{4})[-/](\d{2})/.exec(raw);
  if (m) return m[1] + '-' + m[2];
  m = /(\d{2})\/(\d{2})\/(\d{4})/.exec(raw);
  if (m) return m[3] + '-' + m[2];
  return null;
};

async function dataset(slug){
  const r = await fetch('https://www.data.gouv.fr/api/1/datasets/' + slug + '/', { headers: UA });
  if (!r.ok) throw new Error('data.gouv ' + r.status);
  return r.json();
}

const agg = new Map();      /* 'YYYY-MM|code' -> count */
const monthsSet = new Set();
let scanned = 0, matched = 0, noRegion = 0;

const ds = await dataset('les-offres-diffusees-sur-choisir-le-service-public');
const csvs = (ds.resources || []).filter(x => (x.format || '').toLowerCase() === 'csv')
  .sort((a, b) => (b.filesize || 0) - (a.filesize || 0));
for (const res of csvs){
  try {
    const r = await fetch(res.url, { headers: UA });
    if (!r.ok || !r.body) throw new Error('HTTP ' + r.status);
    const rl = createInterface({ input: Readable.fromWeb(r.body), crlfDelay: Infinity });
    let head = null, sep = ';', cT = -1, cD = -1, cR = -1, cDep = -1, cLieu = -1;
    for await (const line of rl){
      if (!head){
        head = line;
        sep = (line.match(/;/g) || []).length >= (line.match(/,/g) || []).length ? ';' : ',';
        const H = line.toLowerCase().split(sep);
        cT = H.findIndex(h => /intitul/.test(h)); if (cT < 0) cT = H.findIndex(h => /libell|titre/.test(h));
        cD = H.findIndex(h => /premi[eè]re publication/.test(h));
        if (cD < 0) cD = H.findIndex(h => /date/.test(h) && /(publi|diffus|crea|debut)/.test(h));
        if (cD < 0) cD = H.findIndex(h => /date/.test(h));
        cR = H.findIndex(h => /r[ée]gion/.test(h));
        cDep = H.findIndex(h => /localisation/.test(h));
        cLieu = H.findIndex(h => /lieu d.affectation/.test(h) && !/sans g[ée]o/.test(h));
        if (cT < 0 || cD < 0) { console.log('  colonnes absentes dans', res.title); break; }
        continue;
      }
      scanned++;
      const cells = line.split(sep);
      const t = strip(cells[cT] || '');
      if (t.length < 4 || !AI_LEX.test(t) || AI_FALSE.test(t)) continue;
      const month = monthOf(cells[cD]); if (!month) continue;
      let code = null;
      if (cR >= 0) code = REGION_CODE.get(strip(cells[cR] || '')) || null;
      if (!code && cDep >= 0){
        const dm = /\((\d{2,3}|2a|2b)\)/i.exec(cells[cDep] || '');
        if (dm) code = DEP2REG[dm[1].toLowerCase()] || DEP2REG[dm[1].slice(0, 2)] || null;
        if (!code) code = REGION_CODE.get(strip(cells[cDep] || '')) || null;
      }
      if (!code && cLieu >= 0){
        const pm = /\b(\d{5})\b/.exec(cells[cLieu] || '');
        if (pm){ const d = pm[1].startsWith('97') ? pm[1].slice(0, 3) : pm[1].slice(0, 2); code = DEP2REG[d] || null; }
      }
      matched++;
      if (!code){ noRegion++; code = 'XX'; }
      monthsSet.add(month);
      const k = month + '|' + code;
      agg.set(k, (agg.get(k) || 0) + 1);
    }
    console.log(`  ${res.title} — cumul scannées ${scanned}, IA ${matched}`);
  } catch (e){ console.log('  fichier KO —', e.message); }
}

const months = [...monthsSet].sort().filter(m => m >= '2022-01');
const codes = [...new Set([...agg.keys()].map(k => k.split('|')[1]))].filter(c => c !== 'XX');
const regions = {};
for (const c of codes) regions[c] = months.map(m => agg.get(m + '|' + c) || 0);
const total = months.map(m => codes.reduce((s, c) => s + (agg.get(m + '|' + c) || 0), 0) + (agg.get(m + '|XX') || 0));

writeFileSync(join(root, 'data', 'csp_monthly.json'), JSON.stringify({
  collected_at: new Date().toISOString(),
  source: 'Choisir le Service Public (DGAFP) — offres secteur public, filtre lexical IA ELIA',
  scanned, matched, no_region: noRegion, months, regions, total,
}), 'utf8');
console.log(`data/csp_monthly.json — ${months.length} mois (${months[0]} → ${months[months.length - 1]}), ${matched} offres IA régionalisées (${noRegion} sans région), ${scanned} scannées.`);
