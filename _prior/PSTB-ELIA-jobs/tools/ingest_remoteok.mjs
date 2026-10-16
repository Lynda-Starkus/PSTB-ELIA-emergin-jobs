// Ingestion RemoteOK (api publique, un seul GET) — comptage des offres remote
// mondiales par intitulé. Source d'appoint ; échec toléré sans bloquer le build.
// Usage : node tools/ingest_remoteok.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
try {
  const r = await fetch('https://remoteok.com/api', { headers: { 'User-Agent': 'ELIA-observatory/1.0 (PST&B)' } });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const js = await r.json();
  const jobs = js.filter(x => x && x.position).map(x => (x.position + ' ' + (x.tags || []).join(' ')).toLowerCase());
  const tax = JSON.parse(readFileSync(join(root, 'data', 'taxonomy.json'), 'utf8'));
  const per = {};
  for (const t of tax.titles) {
    const needles = [t.title_en, ...(t.aliases || [])].filter(s => s && s.length > 3).map(s => s.toLowerCase());
    per[t.id] = jobs.filter(j => needles.some(n => j.includes(n))).length;
  }
  writeFileSync(join(root, 'data', 'remoteok.json'),
    JSON.stringify({ collected_at: new Date().toISOString(), total_jobs: jobs.length, per_title: per }), 'utf8');
  console.log(`data/remoteok.json écrit — ${jobs.length} offres remote scannées.`);
} catch (e) {
  console.log('RemoteOK indisponible (' + e.message + ') — source ignorée.');
}
