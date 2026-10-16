// Masse publique : archive « Choisir le Service Public » (DGAFP) en PLEINE
// profondeur — tous les CSV du jeu (dont l'archive ~160 Mo), parsés en flux,
// intitulé + année conservés — et flux Groupe BPCE (JSON).
// Sortie : data/corpus_public.json { csp: [[intitulé, année], …], bpce: [intitulés] }
// Usage : node tools/ingest_mass_fr.mjs
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Readable } from 'node:stream';
import { createInterface } from 'node:readline';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const UA = { 'User-Agent': 'ELIA-observatory/1.0 (PST&B; recherche)' };
const out = { collected_at: new Date().toISOString(), csp: [], bpce: [], notes: [] };
const CAP = 900000;

async function dataset(slug){
  const r = await fetch('https://www.data.gouv.fr/api/1/datasets/' + slug + '/', { headers: UA });
  if (!r.ok) throw new Error('data.gouv ' + r.status);
  return r.json();
}

/* ---- CSP : tous les CSV, en flux ---- */
try {
  const ds = await dataset('les-offres-diffusees-sur-choisir-le-service-public');
  const csvs = (ds.resources || []).filter(x => (x.format || '').toLowerCase() === 'csv')
    .sort((a, b) => (b.filesize || 0) - (a.filesize || 0));
  if (!csvs.length) throw new Error('aucun CSV');
  for (const res of csvs){
    if (out.csp.length >= CAP) break;
    const mb = Math.round((res.filesize || 0) / 1e6);
    try {
      const r = await fetch(res.url, { headers: UA });
      if (!r.ok || !r.body) throw new Error('HTTP ' + r.status);
      const rl = createInterface({ input: Readable.fromWeb(r.body), crlfDelay: Infinity });
      let head = null, sep = ';', colT = -1, colD = -1, n = 0;
      for await (const line of rl){
        if (!head){
          head = line;
          sep = (line.match(/;/g) || []).length >= (line.match(/,/g) || []).length ? ';' : ',';
          const H = line.toLowerCase().split(sep);
          colT = H.findIndex(h => /intitul/.test(h));
          if (colT < 0) colT = H.findIndex(h => /libell|titre|offre/.test(h));
          colD = H.findIndex(h => /date/.test(h) && /(publi|diffus|crea|debut)/.test(h));
          if (colD < 0) colD = H.findIndex(h => /date/.test(h));
          if (colT < 0) break;
          continue;
        }
        const cells = line.split(sep);
        const t = (cells[colT] || '').replace(/^"|"$/g, '').trim();
        if (t.length < 4) continue;
        const dm = colD >= 0 ? /(\d{4})/.exec(cells[colD] || '') : null;
        out.csp.push([t, dm ? Number(dm[1]) : 0]);
        if (++n % 200000 === 0) console.log('   …', out.csp.length, 'lignes');
        if (out.csp.length >= CAP) break;
      }
      out.notes.push(`CSP ${res.title} (${mb} Mo) → cumul ${out.csp.length}`);
      console.log(`CSP ${res.title} (${mb} Mo) → cumul ${out.csp.length} intitulés`);
    } catch (e){ out.notes.push(`CSP ${res.title}: ${e.message}`); console.log('  CSP fichier KO —', e.message); }
  }
} catch (e){ out.notes.push('CSP indisponible: ' + e.message); console.log('CSP KO —', e.message); }

/* ---- BPCE ---- */
try {
  const ds = await dataset('groupe-bpce-offres-emploi-publiques');
  const res = (ds.resources || []).filter(x => /json/i.test(x.format || ''))
    .sort((a, b) => new Date(b.last_modified || 0) - new Date(a.last_modified || 0))[0];
  if (!res) throw new Error('aucun JSON');
  const r = await fetch(res.url, { headers: UA });
  if (!r.ok) throw new Error('JSON ' + r.status);
  const js = await r.json();
  const arr = Array.isArray(js) ? js : (Object.values(js).find(v => Array.isArray(v)) || []);
  const key = arr.length ? Object.keys(arr[0]).find(k => /intitul|title|libell|poste/i.test(k)) : null;
  if (!key) throw new Error('clé intitulé introuvable');
  out.bpce = arr.map(o => String(o[key] || '').trim()).filter(t => t.length > 3).slice(0, 50000);
  console.log('BPCE :', out.bpce.length, 'intitulés');
} catch (e){ out.notes.push('BPCE indisponible: ' + e.message); console.log('BPCE KO —', e.message); }

writeFileSync(join(root, 'data', 'corpus_public.json'), JSON.stringify(out), 'utf8');
console.log('data/corpus_public.json écrit —', out.csp.length, 'CSP +', out.bpce.length, 'BPCE.');
