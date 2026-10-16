// Remplace la reconstruction du logo par les assets OFFICIELS :
//   héros (fond nuit)  → SVG blanc officiel du site pstb.fr, inliné
//   pied de page clair → PNG couleur fourni (data URI)
// Sauvegarde les assets dans assets/. Usage : node tools/patch_logo.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const SVG_URL = 'https://www.pstb.fr/sites/default/files/ggeedu_vars/Logo-PSTB-RVB-Blanc-V2_7.svg';
const PNG_SRC = join(root, 'assets', 'logo-pstb-couleur.png');

const r = await fetch(SVG_URL, { headers: { 'User-Agent': 'Mozilla/5.0' } });
if (!r.ok) throw new Error('SVG ' + r.status);
let svg = await r.text();
console.log('SVG officiel:', svg.length, 'octets, aperçu:', svg.slice(0, 220).replace(/\s+/g, ' '));
if (/<(script|image|foreignObject)/i.test(svg)) throw new Error('SVG inattendu (contenu actif)');
svg = svg.replace(/<\?xml[^>]*\?>/, '').replace(/<!DOCTYPE[^>]*>/, '').trim()
  .replace(/<svg /, '<svg class="pstb-logo" role="img" aria-label="Paris School of Technology & Business" ')
  .replace(/\s(width|height)="[^"]*"/g, '');
writeFileSync(join(root, 'assets', 'logo-pstb-blanc.svg'), svg, 'utf8');

const png = readFileSync(PNG_SRC);
writeFileSync(join(root, 'assets', 'logo-pstb-couleur.png'), png);
const dataUri = 'data:image/png;base64,' + png.toString('base64');
console.log('PNG couleur:', png.length, 'octets, data URI:', Math.round(dataUri.length / 1024), 'KB');

let html = readFileSync(join(root, 'index.html'), 'utf8');
const heroRe = /<div class="pstb">[\s\S]*?<\/div>/;
const footRe = /<span class="pstb">[\s\S]*?pstb-name[\s\S]*?<\/span>\s*<\/span>/;
if (!heroRe.test(html) || !footRe.test(html)) throw new Error('blocs pstb introuvables');
html = html.replace(heroRe, '<div class="pstb">' + svg + '</div>');
html = html.replace(footRe, '<img class="pstb-img" alt="Paris School of Technology & Business" src="' + dataUri + '">');
html = html.replace('.pstb-mark{width:38px;height:38px;flex:none}',
  '.pstb-logo{width:min(230px,56vw);height:auto;display:block}\n.pstb-img{height:46px;width:auto;display:block}');
writeFileSync(join(root, 'index.html'), html, 'utf8');
console.log('index.html patché avec les assets officiels.');
