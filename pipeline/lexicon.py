# -*- coding: utf-8 -*-
"""Shared lexicon for the ELIA emerging-AI-jobs study: scope rules, AI tiers, canonical AI/data titles, normalisation.
All regexes are bilingual (FR/EN), case-insensitive, with explicit homonym exclusions. Rules are frozen before results are read."""
import re, unicodedata


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


# ---------- AI terms (text level) ----------
AI_CORE_TERMS = [
    r"intelligence artificielle", r"artificial intelligence", r"machine learning", r"apprentissage automatique", r"apprentissage machine",
    r"deep learning", r"apprentissage profond", r"\bllms?\b", r"large language models?", r"mod[eè]les? de langage", r"language models?",
    r"ia g[ée]n[ée]rative", r"generative ai", r"\bgen ?ai\b", r"\bgenai\b", r"\bnlp\b", r"traitement (?:automatique )?du langage", r"natural language processing",
    r"computer vision", r"vision par ordinateur", r"r[ée]seaux? de neurones", r"neural networks?", r"\bmlops\b", r"\bllmops\b", r"\baiops\b",
    r"\brag\b", r"retrieval[- ]augmented", r"prompt engineering", r"prompt engineer", r"fine[- ]?tuning", r"agents? ia\b", r"agents? d'ia", r"ai agents?", r"agentic|agentique",
    r"chatgpt", r"\bgpt-?[345]", r"openai", r"copilot", r"hugging ?face", r"langchain", r"llamaindex", r"pytorch", r"tensorflow", r"\bkeras\b", r"scikit[- ]learn", r"\bsklearn\b",
    r"mistral ai", r"\bllama\b", r"stable diffusion", r"\bmidjourney\b", r"reinforcement learning", r"apprentissage par renforcement",
    r"xgboost|lightgbm|random forest|gradient boosting", r"\bmlflow\b|\bkubeflow\b|\bvertex ai\b|\bsagemaker\b|azure (?:open)?ai|aws bedrock",
    r"mod[eè]les? pr[ée]dictifs?", r"predictive models?", r"syst[eè]mes? de recommandation|recommender", r"speech recognition|reconnaissance vocale|reconnaissance d'images",
    r"embeddings?", r"vector (?:database|store|search)|base de donn[ée]es vectorielle", r"\bai act\b", r"\bchatbots?\b", r"agents? conversationnels?",
]
AI_ADJ_TERMS = [r"data scien(?:ce|tist)", r"big data", r"analyse pr[ée]dictive|predictive analytics", r"algorithm", r"\bspark\b", r"data mining", r"\bdatabricks\b|\bsnowflake\b"]
AI_EXCLUDE = [r"ia[- ]ipr", r"ia[- ]dsden", r"ipr[- ]ia", r"ia animale", r"ins[ée]mination", r"\bia\b ?[0-9]", r"a\.?i\.?s?\b (?:mani|lab)", r"\bia\b (?:bourbon|pays|bretagne)"]

RE_AI_CORE = re.compile("|".join(AI_CORE_TERMS), re.I)
# The acronyms IA / AI are matched case-sensitively (upper case only) to avoid the French verb form "j'ai" and similar noise;
# "IA Recrutement" (an agency name) and academic inspectors (IA-IPR, IA-DASDEN) are excluded. In English lower-cased corpora (HN) a lower-case "ai" is accepted.
RE_AI_ACRONYM = re.compile(r"(?<![A-Za-z'’])IA(?![A-Za-z])(?![- ]?(?:IPR|DSDEN|IAA|DASEN|CMI|Recrutement|RECRUTEMENT))|(?<![A-Za-z'’])AI(?![A-Za-z])|(?<![A-Za-z])A\.I\.?(?![A-Za-z])")
RE_AI_ACRONYM_LC = re.compile(r"(?<![a-z'’])ai(?![a-z])")
RE_AI_ADJ = re.compile("|".join(AI_ADJ_TERMS), re.I)
RE_AI_EXCL = re.compile("|".join(AI_EXCLUDE), re.I)
RE_AI_STRONG_TITLE = re.compile(r"intelligence artificielle|artificial intelligence|machine learning|deep learning|\bllm|ia g[ée]n[ée]rative|generative ai|\bgen ?ai\b|\bgenai\b|\bnlp\b|computer vision|\bmlops\b|\bllmops\b|prompt engineer|data scien|forward deployed|agents? ia|ai agents?|agentic|\brag\b|chatbot|conversationnel|apprentissage automatique|r[ée]seaux? de neurones|neural", re.I)

# ---------- Tech scope ----------
ROME_TECH_PREFIX = ("M18",)
ROME_TECH_EXTRA = {"M1405", "M1419", "M1423", "M1435", "M1403"}
# titles that France Travail sometimes files under IT ROME codes although the job is not an IT job (ROME auto-coding noise), or that contain a tech-looking word in a non-tech sense
NONTECH_TITLE = re.compile(r"business developer|d[ée]veloppeu(?:r|se)\s+(?:commercial|d'affaires|business|foncier|de territoire|immobilier|r[ée]seau|de r[ée]seau|franchise|de march[ée]|de client|grands comptes|de partenariats|de portefeuille|territorial|r[ée]gional|secteur|commerce|retail|des ventes|de zone|de la franchise|de l'offre|e-?commerce|produits?)|serveu(?:r|se)\b(?!\s+(?:web|linux|windows|d'application|informatique))|t[ée]l[ée]conseill|technico-?commercial|\bftth?\b|\bftto\b|fibre optique|hydraulic|tramway|approvisionn|acheteu(?:r|se)|cuisin|vendeu(?:r|se)|caissi|chauffeu(?:r|se)|m[ée]nage|infirmi|m[ée]decin|auxiliaire|agent (?:de|d')\s*(?:s[ée]curit[ée]|propret[ée]|service|production|maintenance|fabrication|tri|quai)|machiniste|magasinier|pr[ée]parateu(?:r|rice) de commandes|manutention|plaquiste|menuisier|soudeur|[ée]lectricien|plombier|ma[çc]on|peintre|carrossier|m[ée]canicien|conducteu(?:r|rice) (?:de|d')|responsable (?:de )?magasin|assistant(?:e)? (?:commercial|administrati|de direction|comptable|rh)|comptable|juriste|avocat|notaire|enseignant|professeur|animateu(?:r|rice)|[ée]ducateu(?:r|rice)|aide[- ]soignant|pharmacien|kin[ée]|ost[ée]o|coiffeu|esth[ée]ticien|boulanger|p[âa]tissier|boucher|agriculteur|paysagiste|jardinier|charg[ée](?:e)? (?:de|d') ?(?:client[eè]le|recrutement|communication|marketing|mission environnement|relation)|environnement(?!\s+(?:de d[ée]veloppement|cloud|technique|devops|it\b|informatique))|ux researcher|ux writer", re.I)
TECH_TITLE_TERMS = [
    r"d[ée]veloppeu(?:r|se)(?!\s+(?:commercial|d'affaires|business|foncier|de territoire|immobilier|r[ée]seau|de r[ée]seau|franchise|de march[ée]|de client|grands comptes|de partenariats|de portefeuille|territorial|r[ée]gional|secteur|commerce|retail|des ventes|de zone|de l'offre|e-?commerce|produits?))", r"(?<!business )(?<!sales )(?<!franchise )developer", r"\bdev\b", r"software", r"logiciel", r"devops", r"\bsre\b", r"data engineer", r"data analyst", r"data scientist", r"analyste? (?:de )?donn[ée]es",
    r"ing[ée]nieur(?:e)? (?:en )?(?:informatique|syst[eè]mes?|r[ée]seaux?|cloud|data|logiciel|[ée]tudes et d[ée]veloppement|d[ée]veloppement|machine learning|ia|intelligence artificielle|cybers[ée]curit[ée]|s[ée]curit[ée] informatique|devops|qa|test|plateforme|platform)",
    r"architecte? (?:si|logiciel|cloud|data|solutions?|technique|infrastructure|ia|big data|s[ée]curit[ée])", r"administrateu(?:r|rice) (?:syst[eè]mes?|r[ée]seaux?|base|bases? de donn[ée]es|infrastructure|linux|windows|cloud|si\b)",
    r"technicien(?:ne)? (?:informatique|support|syst[eè]mes?|r[ée]seaux?|help ?desk|it\b|exploitation)", r"cybers[ée]curit[ée]|cyber ?s[ée]curit[ée]|cybersecurity|pentest|\bsoc\b analyst|\bciso\b|\brssi\b", r"full[- ]?stack|back[- ]?end|front[- ]?end",
    r"\bit\b (?:manager|support|engineer|specialist|analyst|project)", r"chef(?:fe)? de projet (?:informatique|it|si|digital|technique|data|ia|mo[ae]|erp|sap)", r"product (?:owner|manager)", r"scrum master", r"\bux\b|\bui\b designer",
    r"\bqa\b|testeur|test engineer|automaticien(?:ne)? (?:de )?tests?", r"\bcloud\b", r"\bsap\b|\bsalesforce\b|\bservicenow\b|\bdynamics\b",
    r"machine learning|ml engineer|\bai\b engineer|ing[ée]nieur ia|intelligence artificielle|mlops|data ?ops|\bdba\b|base de donn[ée]es|\bsql\b|\bpython\b|\bjava\b|\.net\b|\bc\+\+|\bgolang\b|\bphp\b|\bangular\b|\breact\b|\bnode\b|kubernetes|\bdocker\b|\bazure\b|\baws\b|\bgcp\b|\blinux\b",
    r"consultant(?:e)? (?:si|erp|sap|technique|fonctionnel|data|ia|cloud|cybers|digital|informatique|it\b|bi\b|microsoft|salesforce)", r"\bbi\b|business intelligence|power ?bi|data ?viz", r"ing[ée]nieur(?:e)? (?:en )?embarqu|embedded",
    r"responsable (?:informatique|si|it|infrastructure|cybers|data|ia|digital)|\bdsi\b|\bcto\b|\bcdo\b|head of (?:data|ai|engineering|product)",
    r"ing[ée]nieur(?:e)? (?:recherche|r&d|research)|research scientist|research engineer|chercheu(?:r|se) (?:en )?(?:ia|intelligence artificielle|machine learning|informatique|data)",
    r"int[ée]grateur|webmaster|web ?designer|d[ée]veloppement web|\bweb\b (?:developer|engineer)", r"informati(?:que|cien)", r"\bnetwork\b engineer|r[ée]seaux? (?:et )?(?:syst[eè]mes?|t[ée]l[ée]coms?)",
]
RE_TECH_TITLE = re.compile("|".join(TECH_TITLE_TERMS), re.I)

# ---------- Canonical AI / data titles (title level). Order matters: first match wins. ----------
_AI = r"(?:\bia\b|\bai\b|intelligence artificielle|artificial intelligence|machine learning|deep learning|\bllm|genai|\bgen ai\b|g[ée]n[ée]rative|data science)"
CANON = [
    ("forward_deployed_engineer", r"forward[- ]deployed"),
    ("agent_engineer", r"(?:agents? ia|ai agents?|agentic|agentique|agents? d'ia|agents? intelligents?|agents? conversationnels?|multi-?agents?).{0,25}(?:engineer|ing[ée]nieur|d[ée]veloppeu|developer|architect)|(?:engineer|ing[ée]nieur|d[ée]veloppeu|developer|architect).{0,25}(?:agents? ia|ai agents?|agentic|agentique|agents? d'ia|agents? intelligents?|agents? conversationnels?|multi-?agents?)"),
    ("prompt_engineer", r"prompt (?:engineer|ing[ée]nieur|designer|specialist|expert)|ing[ée]nieur(?:e)? prompt|prompt engineering"),
    ("genai_engineer", r"(?:ia g[ée]n[ée]rative|generative ai|\bgen ?ai\b|genai|\bllm|large language).{0,25}(?:engineer|ing[ée]nieur|d[ée]veloppeu|developer|expert|specialist|sp[ée]cialiste)|(?:engineer|ing[ée]nieur|d[ée]veloppeu|developer|expert|specialist|sp[ée]cialiste).{0,25}(?:ia g[ée]n[ée]rative|generative ai|\bgen ?ai\b|genai|\bllm)"),
    ("mlops_engineer", r"\bml ?ops\b|\bllm ?ops\b|\baiops\b|ml platform|machine learning platform|ai platform engineer|ai infrastructure|infrastructure ia"),
    ("nlp_engineer", r"\bnlp\b|traitement (?:automatique )?(?:du|des) langu?|natural language|computational linguist|linguiste? informati"),
    ("computer_vision_engineer", r"computer vision|vision par ordinateur|vision artificielle|image processing|traitement d'images?"),
    ("ml_engineer", r"(?:machine learning|\bml\b|apprentissage automatique|deep learning).{0,20}(?:engineer|ing[ée]nieur|d[ée]veloppeu|developer)|(?:engineer|ing[ée]nieur|d[ée]veloppeu|developer).{0,20}(?:machine learning|\bml\b|apprentissage automatique|deep learning)|\bmle\b"),
    ("ai_researcher", r"(?:research(?:er)? scientist|chercheu(?:r|se)|research engineer|ing[ée]nieur(?:e)? (?:de )?recherche|scientifique|doctorant|phd|post[- ]?doc|th[eè]se).{0,40}" + _AI + r"|" + _AI + r".{0,30}(?:research(?:er)? scientist|chercheu(?:r|se)|research engineer|ing[ée]nieur(?:e)? (?:de )?recherche|doctorant|phd|post[- ]?doc|th[eè]se)"),
    ("ai_architect", r"architect.{0,25}" + _AI + r"|" + _AI + r".{0,25}architect"),
    ("ai_product_manager", r"(?:product (?:manager|owner)|chef(?:fe)? de produit|\bpo\b|\bpm\b).{0,25}" + _AI + r"|" + _AI + r".{0,25}(?:product (?:manager|owner)|chef(?:fe)? de produit)"),
    ("head_of_ai", r"(?:head of|directeu(?:r|rice)|director|responsable|\blead\b|manager|chief|\bvp\b|\bcto\b).{0,20}" + _AI + r"|" + _AI + r".{0,20}(?:\blead\b|manager|director|directeu(?:r|rice)|responsable|head)|chief ai officer|\bcaio\b"),
    ("ai_governance", _AI + r".{0,30}(?:[ée]thique|ethic|gouvernance|governance|compliance|conformit[ée]|\brisk|risque|audit|trust|responsible|policy|r[ée]glement|regulation|juriste|legal)|(?:[ée]thique|ethic|gouvernance|governance|compliance|conformit[ée]|audit|juriste|legal|\brisk).{0,30}" + _AI + r"|\bai act\b"),
    ("ai_consultant", r"(?:consultant(?:e)?|conseil|advisor|expert(?:e)?|sp[ée]cialiste|specialist|analyste?|analyst).{0,25}" + _AI + r"|" + _AI + r".{0,25}(?:consultant|advisor|expert|sp[ée]cialiste|specialist|analyst)"),
    ("ai_trainer", r"(?:formateu(?:r|rice)|trainer|enseignant|professeur|teacher|instructor|coach).{0,25}" + _AI + r"|" + _AI + r".{0,25}(?:formateu|trainer|teacher|instructor|coach)|data (?:annotat|label)|annotateu(?:r|rice)|ai (?:tutor|rater)"),
    ("ai_sales", r"(?:sales|commercial|business developer|account|pre-?sales|avant[- ]vente|solutions? engineer|customer engineer|deployment strategist).{0,25}" + _AI + r"|" + _AI + r".{0,25}(?:sales|commercial|business developer|pre-?sales|avant[- ]vente|solutions? engineer|customer engineer)"),
    ("ai_engineer", r"(?:ing[ée]nieur(?:e)?|engineer|d[ée]veloppeu(?:r|se)|developer|programmeu(?:r|se)|concepteu(?:r|rice)|int[ée]grateu(?:r|rice)|tech ?lead|lead dev|software).{0,30}(?:\bia\b|\bai\b|intelligence artificielle|artificial intelligence|deep learning|apprentissage|\bllm|chatbot)|(?:\bia\b|\bai\b|intelligence artificielle|artificial intelligence|deep learning|\bllm|chatbot).{0,30}(?:ing[ée]nieur|engineer|d[ée]veloppeu|developer|programmeu|concepteu|int[ée]grateu|tech ?lead|software)|\bmts\b|member of technical staff"),
    ("data_scientist", r"data scien|datascien|scientifique (?:de |des )?donn[ée]es|scientist.{0,15}data"),
    ("data_engineer", r"data engineer|ing[ée]nieur(?:e)? (?:en )?(?:data|donn[ée]es|big data)|big data|data ?ops|ing[ée]nieur(?:e)? etl|d[ée]veloppeu(?:r|se) data|data platform|ing[ée]nieur(?:e)? (?:data )?pipeline"),
    ("data_analyst", r"data analyst|analyste? (?:de |des )?donn[ée]es|data analytics|business intelligence|\bbi\b analyst|analyste? bi\b|consultant(?:e)? bi\b|power ?bi|d[ée]veloppeu(?:r|se) bi\b"),
    ("data_architect", r"data architect|architecte? (?:de |des )?donn[ée]es|architecte? data"),
    ("data_leader", r"chief data|\bcdo\b|head of data|data (?:manager|lead|owner|steward|governance|protection|quality|product manager)|responsable (?:de la |des )?donn[ée]es|directeu(?:r|rice) (?:de la |des )?donn[ée]es|data (?:science|engineering) manager|gouvernance (?:de la |des )?donn[ée]es"),
    ("ai_other", r"\bia\b|\bai\b|intelligence artificielle|artificial intelligence|machine learning|deep learning|\bllm|genai|g[ée]n[ée]rative|chatbot"),
]
RE_CANON = [(k, re.compile(p, re.I)) for k, p in CANON]
CANON_FAMILY = {
    "forward_deployed_engineer": "AI engineering (new titles)", "agent_engineer": "AI engineering (new titles)", "prompt_engineer": "AI engineering (new titles)", "genai_engineer": "AI engineering (new titles)",
    "ai_engineer": "AI engineering", "ml_engineer": "ML engineering", "mlops_engineer": "ML engineering", "nlp_engineer": "ML engineering", "computer_vision_engineer": "ML engineering",
    "ai_researcher": "AI research", "ai_architect": "AI architecture & leadership", "head_of_ai": "AI architecture & leadership",
    "ai_product_manager": "AI business roles", "ai_consultant": "AI business roles", "ai_sales": "AI business roles", "ai_governance": "AI governance & ethics", "ai_trainer": "AI training & data labelling",
    "data_scientist": "Data science", "data_engineer": "Data engineering", "data_architect": "Data engineering", "data_analyst": "Data analytics", "data_leader": "Data leadership", "ai_other": "Other AI-labelled",
}
CANON_LABEL = {
    "forward_deployed_engineer": "Forward Deployed Engineer", "agent_engineer": "AI Agent Engineer", "prompt_engineer": "Prompt Engineer", "genai_engineer": "Generative AI / LLM Engineer",
    "ai_engineer": "AI Engineer / Développeur IA", "ml_engineer": "Machine Learning Engineer", "mlops_engineer": "MLOps / AI Platform Engineer", "nlp_engineer": "NLP Engineer", "computer_vision_engineer": "Computer Vision Engineer",
    "ai_researcher": "AI Research Scientist", "ai_architect": "AI Architect", "head_of_ai": "Head of AI / Responsable IA", "ai_product_manager": "AI Product Manager", "ai_governance": "AI Governance, Ethics & Compliance",
    "ai_consultant": "AI Consultant / Expert", "ai_trainer": "AI Trainer / Data Annotator", "ai_sales": "AI Sales / Solutions Engineer", "data_scientist": "Data Scientist", "data_engineer": "Data Engineer",
    "data_analyst": "Data Analyst / BI", "data_architect": "Data Architect", "data_leader": "Data Leadership & Governance", "ai_other": "Other AI-labelled title",
}

# ---------- Title normalisation ----------
RE_GENDER = re.compile(r"\(?\b[hf]\s?/\s?[hf]\b\)?|\((?:e|se|euse|rice|trice|ne|ve|ère|le|te|sse)\)|·e|\bh/f\b|\bf/h\b|\bm/f\b|\bm/w/d\b|\(?\bh/f/x\b\)?|\(?\bf/m/x\b\)?|\(?\bw/m/d\b\)?|\(?\bh/f/d\b\)?", re.I)
RE_DOUBLE = re.compile(r"\b(\w{3,})\s*/\s*(\w{3,}(?:e|euse|rice|trice|ne|ve|ère|le|te|sse))\b")
RE_SENIORITY = re.compile(r"\b(senior|sénior|junior|confirm[ée]e?|d[ée]butant(?:e)?|exp[ée]riment[ée]e?|principal|staff|stagiaire|alternant(?:e)?|apprenti(?:e)?|intern(?:ship)?|stage|alternance|apprentissage|cdi|cdd|freelance|ind[ée]pendant|int[ée]rim|temps (?:plein|partiel)|full[- ]time|part[- ]time|remote|t[ée]l[ée]travail|hybride|hybrid|on[- ]site|\d{4,5}|\d+ ?(?:ans|mois|k€|€))\b", re.I)
RE_PAREN = re.compile(r"\([^)]*\)|\[[^\]]*\]")
RE_SPACES = re.compile(r"[\s_]+")
RE_PUNCT_EDGE = re.compile(r"^[\s\-–—:;,./|•*]+|[\s\-–—:;,./|•*]+$")


def seniority_of(title):
    t = (title or "").lower()
    if re.search(r"\b(senior|sénior|confirm|exp[ée]riment|principal|staff|lead\b|expert)", t): return "senior"
    if re.search(r"\b(junior|d[ée]butant|stagiaire|alternan|apprenti|intern|stage\b|graduate|entry)", t): return "junior"
    if re.search(r"\b(head|directeu|director|chief|vp\b|cto\b|cdo\b|manager|responsable)", t): return "lead"
    return "unspecified"


def normalise_title(title):
    if not title: return ""
    t = title.lower()
    t = RE_PAREN.sub(" ", t)
    t = RE_GENDER.sub(" ", t)
    t = RE_DOUBLE.sub(r"\1", t)
    t = RE_SENIORITY.sub(" ", t)
    t = RE_SPACES.sub(" ", t).strip()
    if len(t) > 25: t = re.sub(r"\s+[-–—|:]\s+.*$", "", t)
    t = RE_PUNCT_EDGE.sub("", t)
    t = RE_SPACES.sub(" ", t).strip()
    return strip_accents(t)


def canon_title(title):
    t = title or ""
    for k, r in RE_CANON:
        if r.search(t): return k
    return None


def ai_tier(text, title="", lowercase_corpus=False):
    """0 none; 1 adjacent (data science / analytics); 2 AI mentioned in text; 3 AI in title (AI-core).
    lowercase_corpus=True for corpora stored in lower case (Hacker News), where a lower-case 'ai' token is accepted."""
    if not text: return 0, []
    body = RE_AI_EXCL.sub(" ", text)
    core = set(m.group(0).lower() for m in RE_AI_CORE.finditer(body))
    acr = RE_AI_ACRONYM_LC if lowercase_corpus else RE_AI_ACRONYM
    if acr.search(body): core.add("ia/ai")
    core = sorted(core)
    t = RE_AI_EXCL.sub(" ", title) if title else ""
    if t and (RE_AI_STRONG_TITLE.search(t) or acr.search(t)): return 3, core
    if core: return 2, core
    if RE_AI_ADJ.search(body): return 1, []
    return 0, []


def is_tech(rome, title):
    """Tech scope = (IT/data ROME code OR tech title lexicon) AND NOT an obviously non-tech title (ROME auto-coding noise)."""
    rome = (rome or ""); title = title or ""
    if NONTECH_TITLE.search(title) and not re.search(r"informati|logiciel|software|data|devops|cloud|cyber|syst[eè]mes? (?:et )?r[ée]seaux|\bsi\b|\bit\b|digital|web|python|java", title, re.I): return False
    if rome[:3] in ROME_TECH_PREFIX or rome in ROME_TECH_EXTRA: return True
    return bool(RE_TECH_TITLE.search(title))


def ai_substantive(terms, tier):
    """Stricter AI flag for sensitivity analysis: AI in the title, or >= 2 distinct AI terms, or one technical (non-acronym, non-tool-brand) term."""
    if tier == 3: return True
    weak = {"ia/ai", "copilot", "chatbot", "chatbots", "ocr", "embeddings", "agents conversationnels", "reconnaissance vocale", "recommender", "syst[eè]mes? de recommandation"}
    strong = [t for t in terms if t not in weak]
    return len(terms) >= 2 or len(strong) >= 1
