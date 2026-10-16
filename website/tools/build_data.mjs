// Assemblage du jeu de données RÉEL de l'observatoire.
//   .cache/hn/*.json  (ingest_hn)            → séries mensuelles par famille & intitulé
//   data/ft_fr.json   (ingest_francetravail) → offres en ligne France par intitulé
//   data/remoteok.json (optionnel)           → offres remote monde par intitulé
// Classification EXCLUSIVE par priorité : chaque annonce compte dans sa première
// famille correspondante (familles IA testées avant les familles génériques),
// pour que les parts soient empilables sans double compte.
// Sorties : data/series.json, data/data.js. Usage : node tools/build_data.mjs
import { readFileSync, writeFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const CACHE = join(root, '.cache', 'hn');
const tax = JSON.parse(readFileSync(join(root, 'data', 'taxonomy.json'), 'utf8'));

/* ---------- règles familles (ordre = priorité, premier match gagne) ---------- */
/* Précision avant rappel : on ne matche que des libellés de POSTE (nom de rôle
   adjacent au qualificatif IA), jamais un simple sujet dans la description —
   sinon « we build AI agents » classe une annonce full-stack chez agents. */
const FAM_RULES = [
  ['forward_deployed', /forward[\s-]?deploy|deployment strategist|ai sales engineer|solutions? (architect|engineer)[^.|,;]{0,25}(gen ?ai|\bai\b|llm)|customer engineer[^.|,;]{0,20}(\bai\b|llm)/],
  ['agents', /\bagent (engineer|developer)s?\b|agentic (engineer|developer)|ai agent (engineer|developer)/],
  ['prompt_context', /prompt engineer|context engineer/],
  ['llmops_evals', /llm ?ops engineer|ml ?ops engineer|evals? engineer|evaluation engineer/],
  ['ai_data_ops', /data annotation|annotation (lead|manager|specialist)|labell?ing (lead|manager|specialist|operations)|data curator|synthetic data engineer|ai trainer|knowledge engineer/],
  ['gouvernance_ia', /ai governance|ai compliance|ai ethics (officer|lead|manager)|responsible ai (lead|officer|manager)|ai policy (manager|lead|analyst)|ai risk (manager|officer|lead)|\bai act\b/],
  ['ai_security', /ai security engineer|llm security|ai red[- ]team|prompt injection/],
  ['direction_ia', /chief ai officer|\bcaio\b|head of (ai|artificial intelligence)|vp,? (of )?ai\b|director of ai|ai director/],
  ['ai_research', /research scientist|research engineer|applied scientist|machine learning scientist|alignment (researcher|engineer)/],
  ['ai_product', /ai product manager|product manager[^.|,;]{0,15}(\bai\b|\bml\b|llm)|conversation(al)? designer|ai ux designer|ai designer\b/],
  ['ml_engineering', /machine learning engineer|\bml engineer|\bmle\b|inference engineer|ai infrastructure engineer|ml platform engineer|gpu (infrastructure |cluster )?engineer/],
  ['ai_engineering', /\bai engineer|gen ?ai (engineer|developer)|generative ai (engineer|developer)|llm (engineer|developer)|ai developer|member of technical staff|rag engineer|fine[- ]?tuning engineer/],
  ['ai_transformation', /ai (transformation|adoption) (consultant|lead|manager)|ai consultant|ai strategist|ai enablement/],
  ['cybersecurite', /security engineer|cyber ?security|infosec|appsec|application security|penetration tester/],
  ['data_engineering_ctx', /data engineer|analytics engineer/],
  ['data_science_ctx', /data scientist/],
  ['devops_sre', /devops|site reliability|\bsre\b|platform engineer|infrastructure engineer|cloud engineer/],
  ['product_management', /product (manager|owner|lead)\b/],
  ['design_produit', /product designer|ux designer|ui designer|ux\/ui|visual designer|brand designer/],
  ['eng_management', /engineering manager|director of engineering|head of engineering|em\b[^.]{0,12}engineering/],
  ['qa_test', /\bqa engineer|quality assurance|test engineer|\bsdet\b|test automation/],
  ['it_support', /it support|help ?desk|system administrator|sysadmin|it technician/],
  ['fullstack_dev', /full[- ]?stack|front[- ]?end|back[- ]?end|backend|frontend|software (engineer|developer)|web developer|mobile (engineer|developer)|ios engineer|android engineer|\bswe\b/],
];
const RULE_FAMS = FAM_RULES.map(r => r[0]);
for (const f of tax.families) if (!RULE_FAMS.includes(f.id)) throw new Error('famille sans règle : ' + f.id);

/* ---------- règles intitulés (non exclusives — sparklines & croissance) ---------- */
const TITLE_RULES = {
  fde: /forward[\s-]?deployed engineer|\bfde\b/, fdse: /forward deployed software/,
  deployment_strategist: /deployment strategist/, solutions_architect_genai: /solutions? architect[^.]{0,25}(gen ?ai|ai|llm)/,
  ai_sales_engineer: /ai sales engineer|sales engineer[^.]{0,20}(ai|llm)/, customer_engineer_ia: /customer engineer/,
  ai_engineer: /\bai engineer/, mts: /member of technical staff/, ai_architect: /ai architect/,
  finetuning_engineer: /fine[- ]?tuning engineer/, rag_engineer: /\brag (engineer|developer)|retrieval engineer/,
  genai_engineer: /gen ?ai (engineer|developer)|generative ai (engineer|developer)/,
  agent_engineer: /agent (engineer|developer)|agentic engineer/, ai_automation_engineer: /ai automation|automation engineer[^.]{0,15}ai/,
  ai_product_manager: /ai product manager|product manager[^.]{0,12}ai/, ai_ux_designer: /ai (ux|designer)/,
  conversation_designer: /conversation(al)? designer/,
  ai_act_compliance_officer: /ai act|ai compliance/, resp_gouvernance_ia: /ai governance/,
  ai_ethics_officer: /ai ethics|responsible ai/, ai_risk_manager: /ai risk|model risk/,
  llmops_engineer: /llm ?ops/, mlops_engineer: /ml ?ops engineer|mlops/, evals_engineer: /evals? engineer|evaluation engineer/,
  ai_research_scientist: /research scientist/, research_engineer: /research engineer/, ml_scientist: /machine learning scientist|applied scientist/,
  prompt_engineer: /prompt engineer/, context_engineer: /context engineer/,
  data_annotation_lead: /annotation|labeling lead/, data_curator: /data curat/, synthetic_data_engineer: /synthetic data/,
  ai_trainer: /ai trainer/, knowledge_engineer: /knowledge engineer/,
  ai_transformation_consultant: /ai (consultant|transformation)/, genai_strategy_lead: /ai strateg/,
  ai_enablement_lead: /ai (enablement|adoption|training lead)/, ai_operations_manager: /ai operations/,
  caio: /chief ai officer|\bcaio\b/, head_of_ai: /head of ai/, vp_of_ai: /vp (of )?ai/,
  ml_engineer: /machine learning engineer|\bml engineer/, inference_engineer: /inference/,
  ai_infrastructure_engineer: /ai infrastructure|gpu (infra|cluster)/,
  ai_security_engineer: /ai security|llm security/, red_teamer_ia: /red[- ]team/,
  fullstack_developer: /full[- ]?stack/, data_engineer: /data engineer/, data_scientist: /data scient/,
  devops_engineer: /devops/, sre: /site reliability|\bsre\b/, cybersecurity_engineer: /cyber ?security|security engineer/,
  product_manager: /product manager/, product_designer: /product designer|ux designer/,
  engineering_manager: /engineering manager/, qa_engineer: /\bqa engineer|quality assurance/,
  it_support_technician: /it support|help ?desk/, sysadmin: /system administrator|sysadmin/,
};

/* ---------- lecture du cache HN ---------- */
const idx = JSON.parse(readFileSync(join(CACHE, 'index.json'), 'utf8'));
const now = new Date();
const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
const months = idx.months.filter(m => m < currentMonth); // mois courant incomplet exclu
const famCounts = Object.fromEntries(tax.families.map(f => [f.id, []]));
const titleCounts = Object.fromEntries(Object.keys(TITLE_RULES).map(t => [t, []]));
const totals = [];
let analysed = 0;

for (const month of months) {
  const { texts } = JSON.parse(readFileSync(join(CACHE, month + '.json'), 'utf8'));
  const fc = Object.fromEntries(RULE_FAMS.map(f => [f, 0]));
  const tc = Object.fromEntries(Object.keys(TITLE_RULES).map(t => [t, 0]));
  for (const text of texts) {
    for (const [fam, re] of FAM_RULES) { if (re.test(text)) { fc[fam]++; break; } }
    for (const [tid, re] of Object.entries(TITLE_RULES)) { if (re.test(text)) tc[tid]++; }
  }
  totals.push(texts.length); analysed += texts.length;
  for (const f of tax.families) famCounts[f.id].push(fc[f.id]);
  for (const t of Object.keys(TITLE_RULES)) titleCounts[t].push(tc[t]);
}
const N = months.length;

/* ---------- parts lissées (moyenne centrée 3 mois) ---------- */
const smooth3 = a => a.map((_, i) => {
  const w = [a[i - 1], a[i], a[i + 1]].filter(v => v !== undefined);
  return w.reduce((s, v) => s + v, 0) / w.length;
});
const famShare = {};
for (const f of tax.families) {
  const raw = famCounts[f.id].map((c, i) => totals[i] ? c / totals[i] * 100 : 0);
  famShare[f.id] = smooth3(raw).map(v => Math.round(v * 100) / 100);
}

/* ---------- intitulés : spark 36 mois, croissance 12 mois, mentions 24 mois ---------- */
const last = N - 1;
const winSum = (a, from, to) => a.slice(Math.max(0, from), to).reduce((s, v) => s + v, 0);
const ft = existsSync(join(root, 'data', 'ft_fr.json')) ? JSON.parse(readFileSync(join(root, 'data', 'ft_fr.json'), 'utf8')) : null;
const rok = existsSync(join(root, 'data', 'remoteok.json')) ? JSON.parse(readFileSync(join(root, 'data', 'remoteok.json'), 'utf8')) : null;

const titlesOut = tax.titles.map(t => {
  const hn = titleCounts[t.id];
  let spark = null, growth = null, hn24 = null;
  if (hn) {
    const sm = smooth3(hn);
    spark = sm.slice(-36).map(v => Math.round(v * 10) / 10);
    hn24 = winSum(hn, N - 24, N);
    const cur = winSum(hn, N - 12, N), prev = winSum(hn, N - 24, N - 12);
    if (prev >= 6) growth = Math.round((cur - prev) / prev * 1000) / 10;
    else if (prev > 0 && cur >= 10) growth = Math.round((cur - prev) / prev * 1000) / 10;
  }
  const f = ft && ft.results[t.id];
  return { ...t, spark, hn_24m: hn24, growth_12m_pct: growth,
    ft_count: f ? f.count : null, ft_count_31j: f ? f.count_31j : null,
    rok_count: rok ? (rok.per_title[t.id] ?? null) : null };
});

/* ---------- jalons (événements réels) ---------- */
const milestones = [
  { date: '2022-11', label_fr: 'Lancement de ChatGPT', short: 'ChatGPT' },
  { date: '2023-03', label_fr: 'Sortie de GPT-4', short: 'GPT-4' },
  { date: '2023-06', label_fr: 'Création de Mistral AI', short: 'Mistral AI' },
  { date: '2024-08', label_fr: "Entrée en vigueur de l'AI Act", short: 'AI Act' },
  { date: '2025-01', label_fr: 'Vague des agents autonomes', short: 'Agents' },
  { date: '2025-02', label_fr: "Sommet pour l'action sur l'IA, Paris", short: 'Sommet Paris' },
  { date: '2026-08', label_fr: 'AI Act : obligations haut risque', short: 'AI Act II' },
];

/* ---------- sorties ---------- */
const series = { updated: currentMonth, source: 'Hacker News « Who is hiring » (Algolia), classification ELIA exclusive, moyenne 3 mois',
  months, totals, families: famShare };
writeFileSync(join(root, 'data', 'series.json'), JSON.stringify(series), 'utf8');

const famsEcho = tax.families.map(f => ({ id: f.id, label_fr: f.label_fr, label_en: f.label_en,
  category: f.category, domain: f.domain, is_context: f.is_context, order: f.order, description_fr: f.description_fr }));

const data = {
  months, totals,
  series: { families: famShare },
  families: famsEcho,
  titles: titlesOut,
  milestones,
  meta: {
    updated: currentMonth,
    basis: 'Part des annonces « Who is hiring » (Hacker News), classification exclusive par famille, moyenne 3 mois',
    analysed_total: analysed,
    hn_crawled_at: idx.crawled_at,
    ft_collected_at: ft ? ft.collected_at : null,
    rok_collected_at: rok ? rok.collected_at : null,
    rok_total: rok ? rok.total_jobs : null,
  },
};
writeFileSync(join(root, 'data', 'data.js'), 'window.ELIA_DATA = ' + JSON.stringify(data) + ';\n', 'utf8');

/* ---------- contrôles & résumé ---------- */
const bad = Object.values(famShare).flat().filter(v => !isFinite(v) || v < 0).length;
if (bad) throw new Error('valeurs invalides : ' + bad);
const at = (fid, i) => famShare[fid][i];
console.log(`mois : ${N} (${months[0]} → ${months[N - 1]}), annonces analysées : ${analysed}`);
console.log('dernier mois —',
  'fde', at('forward_deployed', last) + '%', '| ai_eng', at('ai_engineering', last) + '%',
  '| agents', at('agents', last) + '%', '| fullstack', at('fullstack_dev', last) + '%');
const fdeT = titlesOut.find(t => t.id === 'fde');
console.log('FDE — spark 36m max', fdeT.spark ? Math.max(...fdeT.spark) : null, '| Δ12m', fdeT.growth_12m_pct, '% | FT France', fdeT.ft_count);
console.log('intitulés avec signal HN (≥5 mentions/24m) :', titlesOut.filter(t => (t.hn_24m || 0) >= 5).length + '/' + titlesOut.length);
if (ft) console.log('France Travail — collecte', ft.collected_at);
console.log('taille data.js :', Math.round(statSync(join(root, 'data', 'data.js')).size / 1024) + ' KB');
