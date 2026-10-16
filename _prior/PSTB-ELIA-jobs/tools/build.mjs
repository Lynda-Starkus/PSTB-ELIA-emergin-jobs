// Post-build for the ELIA observatory.
//  1. Embeds data/sources.json into data/data.js (window.ELIA_SOURCES) so the
//     methodology section renders without fetch() — file:// included.
//  2. Derives dist/artifact.html (variante hébergée, sans enveloppe de document)
//     from the canonical index.html.
// Usage: node tools/build.mjs   (run after tools/generate_data.mjs)
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

// 1 — embed sources + regions + geo (file:// support, pas de fetch nécessaire)
const dataPath = join(root, 'data', 'data.js');
if (existsSync(dataPath)) {
  let js = readFileSync(dataPath, 'utf8');
  js = js.replace(/\n?;?window\.ELIA_(SOURCES|REGIONS|GEO|DISCOVERY|ADZUNA|CSP_M|OUTCOMES)[\s\S]*$/, '');
  let tail = '';
  const embed = (file, name) => {
    const p = join(root, 'data', file);
    if (existsSync(p)) tail += ';window.' + name + ' = ' + JSON.stringify(JSON.parse(readFileSync(p, 'utf8'))) + ';\n';
  };
  embed('sources.json', 'ELIA_SOURCES');
  embed('ft_regions.json', 'ELIA_REGIONS');
  embed('fr-regions.geojson', 'ELIA_GEO');
  embed('discovery.json', 'ELIA_DISCOVERY');
  embed('adzuna.json', 'ELIA_ADZUNA');
  embed('csp_monthly.json', 'ELIA_CSP_M');
  embed('outcomes.json', 'ELIA_OUTCOMES');
  writeFileSync(dataPath, js.replace(/\s*$/, '\n') + tail, 'utf8');
  console.log('data/data.js: embeds ->', tail.match(/window\.\w+/g)?.join(', '));
}

// 2 — artifact variant
const html = readFileSync(join(root, 'index.html'), 'utf8');
const m = html.match(/<!-- ELIA:CONTENT-START -->([\s\S]*)<!-- ELIA:CONTENT-END -->/);
if (!m) { console.error('markers not found'); process.exit(1); }
mkdirSync(join(root, 'dist'), { recursive: true });
writeFileSync(join(root, 'dist', 'artifact.html'), m[1].trim() + '\n', 'utf8');
console.log('dist/artifact.html written (' + m[1].length + ' bytes)');
