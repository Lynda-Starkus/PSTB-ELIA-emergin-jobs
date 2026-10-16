# -*- coding: utf-8 -*-
"""Regenerate the three France Travail JSON inputs of the ELIA observatory from the data lake.

    website/data/ft_fr.json       {collected_at, api, method, results:{<title_id>:{count, count_31j, terms:{<term>:count}}}}
    website/data/ft_regions.json  {collected_at, api, titles_tracked, regions:[...18], quality:{total,cdi,debutants}, fde:{term,total,employers}}
    website/data/corpus_ft.json   {collected_at, calls, total, offers:[{id,t,d,r,c,dep}]}

Schema: website/SPEC_DATA.md.  Reference files: _prior/PSTB-ELIA-jobs/data/{ft_fr,ft_regions,corpus_ft}.json.
Tracked-title selection, REGIONS, quality and FDE employers are ported from _prior/PSTB-ELIA-jobs/tools/ingest_francetravail.mjs
and ingest_ft_regions.mjs; DEP2REG from ingest_csp_regions.mjs.

Source: data-lake/lake/ft_postings.parquet (1 075 585 offers; text = title + description, lower-cased).
"Offres en ligne" = the live stock only (ingest == 'api:2026-10-14').

Terms of a title:  AI families  = [title_en, title_fr] + ALL aliases, deduplicated, length > 3, at most 6 terms;
                   context families = [title_en] only.   (The reference lists, which stop at the first alias, are a prefix.)

Matching rule: an offer matches a term when EITHER
  (a) phrase rule on title + description: the term's words (normalised like the offer text: lower-case, accents stripped,
      tokens = re.findall('[a-z0-9]+'), stop-words de la le les des du d l en et of the and in a dropped) occur IN ORDER inside
      a window of (number of remaining words + 2) consecutive tokens of the offer text (stop-words of the text count as tokens);
  (b) title bag rule: all the term's words occur anywhere in the offer TITLE alone (intitule; titles are short, so a bag of
      words is precise there), as a MULTISET: each word must occur in the title at least as many times as in the term
      (collections.Counter containment), so "Responsable IA responsable" needs two "responsable" and no longer matches
      "Responsable IA".
  A one-word term matches on presence.  count = max over the title's terms; count_31j = 31-day count of the best term (first
  term of the maximum, as in the JS); count_annee = created within 365 days.
  Candidates are pre-selected with token sets (all words present), then the order / window test uses the token positions.

corpus_ft.json: every offer of the lake (both ingests); t = clean_inclusive(intitule), where clean_inclusive() is IMPORTED from
pipeline/site/build_csp.py (single source of truth: it strips French inclusive-writing suffixes such as "chargé(e)",
"ingénieur·e", "développeur.se", "enseignant-e", "Enseignant/e"), so the FT and CSP corpora are cleaned the same way.
The cleaning only touches the corpus titles: the matching above always uses the raw lake text and titles.

Run:
    G:/Linda/Bureau/PSTB/ELIA/metiers-ia-emergents/.venv/Scripts/python pipeline/site/build_ft.py [project_root]
        [--out DIR] [--skip-corpus]
  --skip-corpus : do not rewrite corpus_ft.json (e.g. when only the matching rule changed); the existing file is still validated.
"""
import argparse
import collections
import json
import multiprocessing as mp
import os
import re
import sys
import time
import unicodedata
from bisect import bisect_right
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------------------------------------------------
LIVE_INGEST = 'api:2026-10-14'            # live stock harvested on 14 Oct 2026 = "offres en ligne"
COLLECTED_AT = '2026-10-14T20:45:00Z'
RECENT_FROM = '2026-09-13T20:45:00'       # collected_at - 31 days (UTC, naive like lake.date_posted)
YEAR_FROM = '2025-10-14'                  # "created within 365 days"
CALLS = 0                                 # corpus_ft.json: nothing is fetched from the API any more

STOP_WORDS = frozenset(['de', 'la', 'le', 'les', 'des', 'du', 'd', 'l', 'en', 'et', 'of', 'the', 'and', 'in', 'a'])
GAP = 2                                   # window = number of remaining words + GAP consecutive tokens
MAX_TERMS = 6                             # AI families: [title_en, title_fr] + all aliases, at most 6 terms

API_FR = "France Travail \u2014 Offres d'emploi v2"
API_REG = "France Travail \u2014 Offres d\u2019emploi v2 (filtre region, typeContrat, experienceExige)"
METHOD_FR = ("comptage par expression : mots du terme (mots vides exclus) pr\u00e9sents dans l'ordre dans une fen\u00eatre de n+2 "
             "mots cons\u00e9cutifs du titre + de la description, OU tous les mots du terme pr\u00e9sents dans l'intitul\u00e9 seul, "
             "chacun au moins aussi souvent que dans le terme ; "
             "accents et casse ignor\u00e9s ; max. des termes (intitul\u00e9 EN, intitul\u00e9 FR et alias) ; "
             "stock en ligne du 2026-10-14 (data lake ELIA)")

# REGIONS of ingest_ft_regions.mjs (codes + names, in this order; typographic apostrophe in PACA)
REGIONS = [
    ('11', 'Île-de-France'), ('24', 'Centre-Val de Loire'), ('27', 'Bourgogne-Franche-Comté'),
    ('28', 'Normandie'), ('32', 'Hauts-de-France'), ('44', 'Grand Est'), ('52', 'Pays de la Loire'),
    ('53', 'Bretagne'), ('75', 'Nouvelle-Aquitaine'), ('76', 'Occitanie'), ('84', 'Auvergne-Rhône-Alpes'),
    ('93', 'Provence-Alpes-Côte d’Azur'), ('94', 'Corse'),
    ('01', 'Guadeloupe'), ('02', 'Martinique'), ('03', 'Guyane'), ('04', 'La Réunion'), ('06', 'Mayotte'),
]
METRO_EXCLUDED = {'01', '02', '03', '04', '06'}

# DEP2REG of ingest_csp_regions.mjs (department -> INSEE region code).  The lake stores Corse as the postal prefix '20'
# (never '2A'/'2B'), so '20' is added to '2a'/'2b' (same convention as pipeline/analysis_core.py).
REGION_DEPTS = {
    '11': ['75', '77', '78', '91', '92', '93', '94', '95'],
    '24': ['18', '28', '36', '37', '41', '45'],
    '27': ['21', '25', '39', '58', '70', '71', '89', '90'],
    '28': ['14', '27', '50', '61', '76'],
    '32': ['02', '59', '60', '62', '80'],
    '44': ['08', '10', '51', '52', '54', '55', '57', '67', '68', '88'],
    '52': ['44', '49', '53', '72', '85'],
    '53': ['22', '29', '35', '56'],
    '75': ['16', '17', '19', '23', '24', '33', '40', '47', '64', '79', '86', '87'],
    '76': ['09', '11', '12', '30', '31', '32', '34', '46', '48', '65', '66', '81', '82'],
    '84': ['01', '03', '07', '15', '26', '38', '42', '43', '63', '69', '73', '74'],
    '93': ['04', '05', '06', '13', '83', '84'],
    '94': ['2a', '2b', '20'],
    '01': ['971'], '02': ['972'], '03': ['973'], '04': ['974'], '06': ['976'],
}
DEP2REG = {d: r for r, ds in REGION_DEPTS.items() for d in ds}

TOKEN = re.compile(r'[a-z0-9]+')
COMBINING = re.compile('[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]')

CHUNK = 1500          # offers per task sent to the pool
N_WORKERS = 48        # Windows caps process pools below 64 handles


# --------------------------------------------------------------------------------------------------------------------
# Text normalisation and matching (module level: also imported by the spawned workers)
# --------------------------------------------------------------------------------------------------------------------
def strip_accents(s):
    """lower-case, NFD, drop combining marks."""
    return COMBINING.sub('', unicodedata.normalize('NFD', s.lower()))


def phrase_words(term):
    """Words of a search term: same normalisation and tokenisation as the offer text, stop-words dropped."""
    return tuple(w for w in TOKEN.findall(strip_accents(term)) if w not in STOP_WORDS)


def ordered_within(words, pos, win):
    """True when `words` occur in this order (strictly increasing positions) inside `win` consecutive tokens.
    pos: word -> sorted list of token positions in the offer text."""
    rest = words[1:]
    for p0 in pos[words[0]]:
        p = p0
        for w in rest:
            lst = pos[w]
            j = bisect_right(lst, p)
            if j == len(lst):
                return False            # no later occurrence of w: no later start can succeed either
            p = lst[j]                  # earliest next occurrence = smallest possible end for this start
            if p - p0 >= win:           # span p - p0 + 1 > win
                break
        else:
            return True
    return False


_W = {}


def _init_worker(specs):
    """specs: list (one per term) of tuples of phrase words."""
    _W['vset'] = frozenset(w for words in specs for w in words)
    # need = word multiplicities of the term, only when a word is repeated (multiset test of rule b), else None
    _W['specs'] = [(words, frozenset(words), len(words) + GAP, collections.Counter(words) if len(set(words)) != len(words) else None)
                   for words in specs]


def match_chunk(args):
    """args = (texts, titles).  Returns (bag, phr, ttl): bool matrices (len(texts), n_terms).
    bag = all words of the term are present somewhere in the offer text (diagnostic only);
    phr = the words occur in order inside a window of len(words) + GAP consecutive tokens of the offer text (rule a);
    ttl = every word of the term occurs in the offer title alone at least as many times as in the term (rule b, multiset).
    An offer matches a term when phr or ttl."""
    texts, titles = args
    vset, specs = _W['vset'], _W['specs']
    shape = (len(texts), len(specs))
    bag = np.zeros(shape, dtype=bool)
    phr = np.zeros(shape, dtype=bool)
    ttl = np.zeros(shape, dtype=bool)
    for r, s in enumerate(texts):
        toks = TOKEN.findall(strip_accents(s)) if s else []
        present = vset.intersection(toks)
        tt = titles[r]
        ttoks = TOKEN.findall(strip_accents(tt)) if tt else []
        tpresent = vset.intersection(ttoks)
        if not present and not tpresent:
            continue
        pos = None
        tcount = None
        for j, (words, wset, win, need) in enumerate(specs):
            if not words:
                continue
            if wset <= tpresent:
                if need is None:
                    ttl[r, j] = True
                else:
                    if tcount is None:
                        tcount = collections.Counter(ttoks)
                    if all(tcount[w] >= n for w, n in need.items()):
                        ttl[r, j] = True
            if wset <= present:
                bag[r, j] = True
                if len(words) == 1:
                    phr[r, j] = True
                    continue
                if pos is None:
                    pos = {}
                    for i, tok in enumerate(toks):
                        if tok in vset:
                            pos.setdefault(tok, []).append(i)
                if ordered_within(words, pos, win):
                    phr[r, j] = True
    return bag, phr, ttl


# --------------------------------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------------------------------
def log(msg, t0=[time.time()]):
    print('[%6.1fs] %s' % (time.time() - t0[0], msg), flush=True)


def fmt_int(n):
    return '{:,}'.format(int(n))


def terms_for(title, ctx):
    """AI families: [title_en, title_fr] + ALL aliases, deduplicated, length > 3, at most MAX_TERMS terms;
    context families: [title_en] only.  (ingest_francetravail.mjs stopped at the first alias / 3 terms.)"""
    is_ctx = ctx.get(title['family'], False)
    cand = [title.get('title_en'), title.get('title_fr')] + ([] if is_ctx else list(title.get('aliases') or []))
    terms = list(dict.fromkeys(s for s in cand if s and len(s) > 3))
    return terms[:1] if is_ctx else terms[:MAX_TERMS]


def parse_js_dep2reg(src):
    """DEP2REG region -> departments, as written in ingest_csp_regions.mjs (for the consistency check)."""
    block = src[src.index('const DEP2REG'):]
    block = block[block.index('Object.entries({'):]
    block = block[:block.index('}))')]
    return {k: re.findall(r"'([0-9a-z]+)'", v) for k, v in re.findall(r"'(\d\d)'\s*:\s*\[([^\]]*)\]", block)}


def atomic_write_text(path, text):
    tmp = Path(str(path) + '.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(tmp, path)


def load_clean_inclusive():
    """clean_inclusive() of the sibling script pipeline/site/build_csp.py, loaded by path.  Imported lazily (main process
    only, when the corpus is written) because build_csp.py imports pandas at module level, which the pool workers must not pay for."""
    import importlib.util
    path = Path(__file__).resolve().with_name('build_csp.py')
    spec = importlib.util.spec_from_file_location('build_csp', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.clean_inclusive


# --------------------------------------------------------------------------------------------------------------------
# Matching pass
# --------------------------------------------------------------------------------------------------------------------
def text_chunks(lake_file, ids_seen, titles_seen):
    """Stream the 'text' and 'intitule' columns of the lake, keep the live-stock rows (file order),
    yield (texts, titles) lists of CHUNK offers."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(lake_file)
    live = pa.scalar(LIVE_INGEST, type=pa.large_string())
    buf_i, buf_t, buf_n = [], [], []
    for b in pf.iter_batches(batch_size=8192, columns=['id', 'ingest', 'intitule', 'text']):
        m = pc.equal(b.column('ingest'), live)
        buf_i += b.column('id').filter(m).to_pylist()
        buf_n += [x or '' for x in b.column('intitule').filter(m).to_pylist()]
        buf_t += b.column('text').filter(m).to_pylist()
        while len(buf_t) >= CHUNK:
            ids_seen.extend(buf_i[:CHUNK])
            titles_seen.extend(buf_n[:CHUNK])
            yield buf_t[:CHUNK], buf_n[:CHUNK]
            del buf_i[:CHUNK], buf_t[:CHUNK], buf_n[:CHUNK]
    if buf_t:
        ids_seen.extend(buf_i)
        titles_seen.extend(buf_n)
        yield buf_t, buf_n


def pooled_matrices(specs, chunk_iter):
    bags, phrs, ttls, pending = [], [], [], collections.deque()
    with mp.get_context('spawn').Pool(N_WORKERS, initializer=_init_worker, initargs=(specs,)) as pool:
        def drain(limit):
            while len(pending) > limit:
                b, p, t = pending.popleft().get()
                bags.append(b)
                phrs.append(p)
                ttls.append(t)
        for chunk in chunk_iter:
            pending.append(pool.apply_async(match_chunk, (chunk,)))
            drain(2 * N_WORKERS)
        drain(0)
    return np.concatenate(bags, axis=0), np.concatenate(phrs, axis=0), np.concatenate(ttls, axis=0)


# --------------------------------------------------------------------------------------------------------------------
# Counting
# --------------------------------------------------------------------------------------------------------------------
def compute_results(titles, title_terms, masks, recent):
    """ingest_francetravail.mjs: per title {count = max over terms, count_31j = 31-day count of the best term, terms}."""
    results, best_term_of, alt31 = {}, {}, []
    for t in titles:
        per, best, best31 = {}, 0, 0
        for term in title_terms[t['id']]:
            m = masks[term]
            c = int(m.sum())
            per[term] = c
            if c > best:                               # strict '>' like the JS: first term of the maximum wins
                best, best31 = c, int((m & recent).sum())
        results[t['id']] = {'count': best, 'count_31j': best31, 'terms': per}
        # bestTerm(id) of ingest_ft_regions.mjs: terms sorted by count desc (stable) -> first; max() keeps the first maximum
        best_term_of[t['id']] = max(per, key=lambda k: per[k]) if per else None
        mx31 = max((int((masks[term] & recent).sum()) for term in title_terms[t['id']]), default=0)
        if mx31 != best31:
            alt31.append((t['id'], best31, mx31))
    return results, best_term_of, alt31


def select_tracked(titles, ctx, results, best_term_of):
    """ingest_ft_regions.mjs: top AI-family titles by count (count > 0), FDE forced in at the 10th position."""
    candidates = [t for t in titles if not ctx.get(t['family'], False) and results[t['id']]['count'] > 0 and best_term_of[t['id']]]
    candidates.sort(key=lambda t: -results[t['id']]['count'])           # stable sort: ties keep taxonomy order
    picked = [t for t in candidates if t['id'] != 'fde'][:10]
    fde_title = next((t for t in candidates if t['id'] == 'fde'), None)
    if fde_title:
        picked.insert(min(9, len(picked)), fde_title)
    return picked[:10]


def agreement(results, ref_results):
    """Agreement of per-term counts with the reference API counts, on the terms with API count >= 5:
    (n terms, median signed ln ratio, median |ln ratio|, number of terms within a factor 1.5)."""
    lr = []
    for tid, e in ref_results.items():
        for term, c in e['terms'].items():
            if c >= 5 and term in results[tid]['terms']:
                lr.append(np.log((results[tid]['terms'][term] + 1) / (c + 1)))
    lr = np.array(lr)
    return len(lr), float(np.median(lr)), float(np.median(np.abs(lr))), int((np.abs(lr) < np.log(1.5)).sum())


# --------------------------------------------------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------------------------------------------------
def build(root, out_dir, skip_corpus):
    import pandas as pd

    lake_file = root / 'data-lake' / 'lake' / 'ft_postings.parquet'
    tax_file = root / 'website' / 'data' / 'taxonomy.json'
    ref_dir = root / '_prior' / 'PSTB-ELIA-jobs' / 'data'
    out_dir.mkdir(parents=True, exist_ok=True)
    notes = []

    # ---- taxonomy, terms, phrase words -------------------------------------------------------------------------------
    tax = json.loads(tax_file.read_text(encoding='utf-8'))
    ctx = {f['id']: bool(f.get('is_context')) for f in tax['families']}
    titles = tax['titles']
    title_terms = {t['id']: terms_for(t, ctx) for t in titles}
    all_terms = list(dict.fromkeys(term for t in titles for term in title_terms[t['id']]))
    specs = [phrase_words(term) for term in all_terms]
    assert all(specs), 'a term has no word left after dropping the stop-words: %s' % [t for t, s in zip(all_terms, specs) if not s]
    log('taxonomy: %d titles, %d families, %d term slots, %d distinct terms, %d distinct phrase words'
        % (len(titles), len(tax['families']), sum(len(v) for v in title_terms.values()), len(all_terms), len({w for s in specs for w in s})))

    # ---- lake metadata (all rows) + live frame -------------------------------------------------------------------------
    cols = ['id', 'intitule', 'dateCreation', 'date_posted', 'romeCode', 'typeContrat', 'experienceExige',
            'entreprise.nom', 'dept', 'ingest']
    df = pd.read_parquet(lake_file, columns=cols)
    n_lake = len(df)
    live = df.loc[(df['ingest'] == LIVE_INGEST).to_numpy()].reset_index(drop=True)
    N = len(live)
    log('lake: %s offers, live stock (%s): %s' % (fmt_int(n_lake), LIVE_INGEST, fmt_int(N)))

    # ---- matching on the live stock ------------------------------------------------------------------------------------
    ids_seen, titles_seen = [], []
    bag, phr, ttl = pooled_matrices(specs, text_chunks(lake_file, ids_seen, titles_seen))
    assert ids_seen == live['id'].tolist(), 'live rows streamed from the lake are not in the order of the metadata frame'
    assert titles_seen == live['intitule'].fillna('').tolist()
    assert bag.shape == phr.shape == ttl.shape == (N, len(all_terms))
    assert not (phr & ~bag).any()
    assert not (ttl & ~bag).any(), 'a term found in a title is not found in the offer text: text does not contain the title'
    log('matching done: %d offers x %d terms' % phr.shape)
    fin = phr | ttl
    n_ttl_only = int((ttl & ~phr).sum())
    bagT, phrT, finT = (np.ascontiguousarray(x.T) for x in (bag, phr, fin))
    del bag, phr, ttl, fin
    masks = {term: finT[j] for j, term in enumerate(all_terms)}          # counting rule: phrase OR title bag
    masks_phr = {term: phrT[j] for j, term in enumerate(all_terms)}      # diagnostic: phrase rule alone
    masks_bag = {term: bagT[j] for j, term in enumerate(all_terms)}      # diagnostic: all words anywhere in the text

    dp = live['date_posted']
    recent = (dp >= pd.Timestamp(RECENT_FROM)).to_numpy()
    year = (dp >= pd.Timestamp(YEAR_FROM)).to_numpy()

    # ---- ft_fr.json ----------------------------------------------------------------------------------------------------
    results, best_term_of, alt31 = compute_results(titles, title_terms, masks, recent)
    results_phr = compute_results(titles, title_terms, masks_phr, recent)[0]
    results_bag = compute_results(titles, title_terms, masks_bag, recent)[0]
    ft_fr = {'collected_at': COLLECTED_AT, 'api': API_FR, 'method': METHOD_FR, 'results': results}
    atomic_write_text(out_dir / 'ft_fr.json', json.dumps(ft_fr, ensure_ascii=False, indent=1))
    log('ft_fr.json written')

    # ---- ft_regions.json -----------------------------------------------------------------------------------------------
    tracked = select_tracked(titles, ctx, results, best_term_of)

    code_idx = {c: i for i, (c, _) in enumerate(REGIONS)}
    dep_idx = {d: code_idx[r] for d, r in DEP2REG.items()}
    reg_i = live['dept'].str.lower().map(dep_idx).fillna(-1).astype(np.int16).to_numpy()
    has_reg = reg_i >= 0
    n_reg = len(REGIONS)

    per_region = [{'code': c, 'nom': n, 'total': 0, 'recent': 0, 'annee': 0, 'titles': {}} for c, n in REGIONS]
    unreg_tracked = 0
    for t in tracked:
        m = masks[best_term_of[t['id']]]
        c_all = np.bincount(reg_i[m & has_reg], minlength=n_reg)
        c_31 = np.bincount(reg_i[m & recent & has_reg], minlength=n_reg)
        c_yr = np.bincount(reg_i[m & year & has_reg], minlength=n_reg)
        unreg_tracked += int((m & ~has_reg).sum())
        assert int(c_all.sum()) + int((m & ~has_reg).sum()) == results[t['id']]['count']
        for i in range(n_reg):
            r = per_region[i]
            r['titles'][t['id']] = {'count': int(c_all[i]), 'count_31j': int(c_31[i]), 'count_annee': int(c_yr[i])}
            r['total'] += int(c_all[i])
            r['recent'] += int(c_31[i])
            r['annee'] += int(c_yr[i])

    # quality: national, summed over the tracked titles on their best term
    cdi_mask = (live['typeContrat'] == 'CDI').to_numpy()
    deb_mask = (live['experienceExige'] == 'D').to_numpy()
    q_total = q_cdi = q_deb = 0
    for t in tracked:
        m = masks[best_term_of[t['id']]]
        q_total += results[t['id']]['count']
        q_cdi += int((m & cdi_mask).sum())
        q_deb += int((m & deb_mask).sum())

    # FDE: best term, distinct employers of the matched live offers (most frequent first, then most recent), up to 10
    fde_term = best_term_of.get('fde') or 'forward deployed engineer'
    fde_m = masks[fde_term] if fde_term in masks else np.zeros(N, dtype=bool)
    sub = live.loc[fde_m, ['entreprise.nom', 'date_posted']].sort_values('date_posted', ascending=False, kind='stable')
    seen = collections.OrderedDict()
    for nm in sub['entreprise.nom']:
        if not isinstance(nm, str):
            continue
        nm = nm.strip()
        if len(nm) <= 1:
            continue
        k = nm.casefold()
        if k in seen:
            seen[k][1] += 1
        else:
            seen[k] = [nm, 1]
    employers = [v[0] for v in sorted(seen.values(), key=lambda v: -v[1])][:10]
    fde_total = int(fde_m.sum())

    ft_regions = {
        'collected_at': COLLECTED_AT,
        'api': API_REG,
        'titles_tracked': [{'id': t['id'], 'label': t.get('title_fr') or t.get('title_en'), 'term': best_term_of[t['id']]} for t in tracked],
        'regions': per_region,
        'quality': {'total': int(q_total), 'cdi': int(q_cdi), 'debutants': int(q_deb)},
        'fde': {'term': fde_term, 'total': fde_total, 'employers': employers},
    }
    atomic_write_text(out_dir / 'ft_regions.json', json.dumps(ft_regions, ensure_ascii=False, indent=1))
    log('ft_regions.json written')

    # ---- corpus_ft.json (all offers of both ingests, streamed by blocks to keep memory flat) -----------------------------
    corpus_path = out_dir / 'corpus_ft.json'
    corpus_changed, corpus_suffix, corpus_examples = None, None, []
    if not skip_corpus:
        clean_inclusive = load_clean_inclusive()
        ids = df['id'].fillna('').tolist()
        raw_titles = df['intitule'].fillna('').tolist()
        tt = [clean_inclusive(x) for x in raw_titles]
        spaces = re.compile(r'\s{2,}')
        changed = [(a, b) for a, b in zip(raw_titles, tt) if a != b]
        suffix = [(a, b) for a, b in changed if b != spaces.sub(' ', a).strip()]    # beyond the trim / double-space collapse
        corpus_changed, corpus_suffix = len(changed), len(suffix)
        corpus_examples = suffix[::max(1, len(suffix) // 8)][:8]
        del raw_titles, changed, suffix
        log('clean_inclusive applied to %s titles: %s changed (%s inclusive suffixes removed)' % (fmt_int(n_lake), fmt_int(corpus_changed), fmt_int(corpus_suffix)))
        dd = df['dateCreation'].fillna('').str.slice(0, 10).tolist()
        rr = df['romeCode'].fillna('').tolist()
        cc = df['typeContrat'].fillna('').tolist()
        dep = df['dept'].fillna('').tolist()
        tmp = Path(str(corpus_path) + '.tmp')
        B = 50000
        with open(tmp, 'wb') as f:
            f.write(('{"collected_at":%s,"calls":%d,"total":%d,"offers":[' % (json.dumps(COLLECTED_AT), CALLS, n_lake)).encode('utf-8'))
            for s in range(0, n_lake, B):
                e = min(s + B, n_lake)
                block = [{'id': a, 't': b, 'd': c, 'r': d, 'c': e_, 'dep': g}
                         for a, b, c, d, e_, g in zip(ids[s:e], tt[s:e], dd[s:e], rr[s:e], cc[s:e], dep[s:e])]
                txt = json.dumps(block, ensure_ascii=False, separators=(',', ':'))[1:-1]
                f.write((('' if s == 0 else ',') + txt).encode('utf-8', errors='replace'))
            f.write(b']}')
        os.replace(tmp, corpus_path)
        log('corpus_ft.json written')
    corpus_mb = corpus_path.stat().st_size / 1e6 if corpus_path.exists() else None

    # ---- notes for the summary ---------------------------------------------------------------------------------------------
    n_nodept = int(live['dept'].isna().sum())
    n_unmapped = int((~has_reg & live['dept'].notna().to_numpy()).sum())
    ai_ids = [t['id'] for t in titles if not ctx.get(t['family'], False)]
    gain = sum(results[i]['count'] - results_phr[i]['count'] for i in ai_ids)
    notes.append('terms: AI families = [title_en, title_fr] + all aliases (deduplicated, length > 3, max %d); context families = [title_en]; '
                 '%d term slots, %d distinct terms; the reference term lists (first alias only) are a prefix of these.'
                 % (MAX_TERMS, sum(len(v) for v in title_terms.values()), len(all_terms)))
    notes.append('matching: an offer matches a term if (a) its words minus stop-words (%s) occur in order inside a window of '
                 '(number of remaining words + %d) consecutive tokens of title + description, OR (b) all those words occur anywhere in the '
                 'title alone, each at least as many times as in the term (Counter containment; terms with a repeated word: %s); '
                 'one-word terms match on presence. Title-bag matches that the phrase rule misses: %s (term, offer) pairs; '
                 'sum over AI titles of count(final) - count(phrase only) = %s.'
                 % (', '.join(sorted(STOP_WORDS)), GAP, ', '.join('"%s"' % t for t, s in zip(all_terms, specs) if len(set(s)) != len(s)) or 'none',
                    fmt_int(n_ttl_only), fmt_int(gain)))
    notes.append('regions: dept -> INSEE region via DEP2REG of ingest_csp_regions.mjs; the lake encodes Corse as dept "20" '
                 '(added to 2a/2b); %s live offers (%.1f %%) have no dept and %s an unmapped one (98/99/975), so they are in no region; '
                 'tracked-title matches without region: %s of %s.'
                 % (fmt_int(n_nodept), 100 * n_nodept / N, fmt_int(n_unmapped), fmt_int(unreg_tracked), fmt_int(sum(results[t['id']]['count'] for t in tracked))))
    notes.append('hyphenated term words are split on non-alphanumerics, like the offer text (Full-Stack -> full, stack; Fine-tuning -> fine, tuning).')
    notes.append('count_31j = 31-day count of the best term (highest count, first on ties), as in ingest_francetravail.mjs; '
                 'max over terms of the 31-day counts would differ for %d title(s)%s.'
                 % (len(alt31), (': ' + ', '.join('%s %d->%d' % a for a in alt31)) if alt31 else ''))
    notes.append('ft_fr.json "method" rewritten to describe the combined rule; "api" kept; no other value or key changed. '
                 'website/SPEC_DATA.md (lines on the term list and the all-words rule) is not edited and is now out of date.')
    if bool(year.all()):
        notes.append('count_annee == count everywhere: every live offer was created on or after %s (earliest %s).' % (YEAR_FROM, str(dp.min())[:10]))
    else:
        notes.append('count_annee < count where offers are older than %s (%s live offers).' % (YEAR_FROM, fmt_int(int((~year).sum()))))
    if skip_corpus:
        notes.append('corpus_ft.json was NOT rewritten (--skip-corpus; it does not depend on the matching rule); the existing file is still schema-checked above.')
    else:
        notes.append('corpus_ft.json rewritten: t = clean_inclusive(intitule) with clean_inclusive imported from pipeline/site/build_csp.py '
                     '(%s of %s titles changed = %.2f %%: %s with an inclusive-writing suffix removed, %s only trimmed / double spaces collapsed, '
                     'which clean_inclusive does on every title); the matching above uses the raw titles and text, not the cleaned ones.'
                     % (fmt_int(corpus_changed), fmt_int(n_lake), 100 * corpus_changed / n_lake, fmt_int(corpus_suffix), fmt_int(corpus_changed - corpus_suffix)))

    return {
        'tax': tax, 'ctx': ctx, 'title_terms': title_terms, 'n_terms': len(all_terms), 'results': results,
        'results_phr': results_phr, 'results_bag': results_bag, 'best_term_of': best_term_of, 'tracked': tracked,
        'ft_regions': ft_regions, 'live_n': N, 'lake_n': n_lake, 'corpus_mb': corpus_mb, 'skip_corpus': skip_corpus,
        'corpus_bytes': corpus_path.stat().st_size if corpus_path.exists() else None,
        'corpus_changed': corpus_changed, 'corpus_suffix': corpus_suffix, 'corpus_examples': corpus_examples,
        'unreg_tracked': unreg_tracked, 'notes': notes, 'out_dir': out_dir, 'ref_dir': ref_dir,
        'employers_counts': {v[0]: v[1] for v in seen.values()}, 'dp_min': dp.min(), 'dp_max': dp.max(),
    }


# --------------------------------------------------------------------------------------------------------------------
# Validation against the reference files
# --------------------------------------------------------------------------------------------------------------------
def same_keys(a, b, what):
    assert list(a) == list(b), '%s: keys differ\n  new: %s\n  ref: %s' % (what, list(a), list(b))


def same_types(a, b, what):
    for k in a:
        assert type(a[k]) is type(b[k]), '%s.%s: type %s != %s' % (what, k, type(a[k]).__name__, type(b[k]).__name__)


def validate(res, root):
    out_dir, ref_dir = res['out_dir'], res['ref_dir']
    load = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    lines = []
    fam_of = {t['id']: t['family'] for t in res['tax']['titles']}

    # ft_fr.json
    new, ref = load(out_dir / 'ft_fr.json'), load(ref_dir / 'ft_fr.json')
    same_keys(new, ref, 'ft_fr')
    same_types(new, ref, 'ft_fr')
    assert new['api'] == ref['api']
    same_keys(new['results'], ref['results'], 'ft_fr.results (title ids)')
    assert list(new['results']) == [t['id'] for t in res['tax']['titles']]
    n_slots = 0
    for tid, e in new['results'].items():
        same_keys(e, ref['results'][tid], 'ft_fr.results.' + tid)
        nt, rt = list(e['terms']), list(ref['results'][tid]['terms'])
        assert nt[:len(rt)] == rt, 'ft_fr.results.%s.terms: the reference term list must be a prefix of the new one: %s vs %s' % (tid, rt, nt)
        assert (len(nt) == 1) if res['ctx'][fam_of[tid]] else (1 <= len(nt) <= MAX_TERMS), 'ft_fr.results.%s.terms: %d terms' % (tid, len(nt))
        n_slots += len(nt)
        assert type(e['count']) is int and type(e['count_31j']) is int
        assert all(type(k) is str and type(v) is int for k, v in e['terms'].items())
        assert e['count'] == max(e['terms'].values(), default=0) and 0 <= e['count_31j'] <= e['count']
    lines.append('ft_fr.json: SCHEMA OK (%d titles; terms = reference lists extended with all aliases, %d term entries)' % (len(new['results']), n_slots))
    ft_fr_new = new

    # ft_regions.json
    new, ref = load(out_dir / 'ft_regions.json'), load(ref_dir / 'ft_regions.json')
    same_keys(new, ref, 'ft_regions')
    same_types(new, ref, 'ft_regions')
    assert new['api'] == ref['api']
    assert len(new['titles_tracked']) == len(ref['titles_tracked']) == 10
    for a, b in zip(new['titles_tracked'], ref['titles_tracked']):
        same_keys(a, b, 'ft_regions.titles_tracked[]')
        same_types(a, b, 'ft_regions.titles_tracked[]')
    assert len(new['regions']) == len(ref['regions']) == 18
    for a, b in zip(new['regions'], ref['regions']):
        same_keys(a, b, 'ft_regions.regions[]')
        same_types(a, b, 'ft_regions.regions[]')
        assert (a['code'], a['nom']) == (b['code'], b['nom']), 'region code/name differs: %r vs %r' % ((a['code'], a['nom']), (b['code'], b['nom']))
        assert list(a['titles']) == [t['id'] for t in new['titles_tracked']]
        for tid, v in a['titles'].items():
            same_keys(v, next(iter(b['titles'].values())), 'ft_regions.regions[].titles.' + tid)
            assert all(type(x) is int for x in v.values()) and v['count_31j'] <= v['count'] and v['count_annee'] <= v['count']
        assert a['total'] == sum(v['count'] for v in a['titles'].values())
        assert a['recent'] == sum(v['count_31j'] for v in a['titles'].values())
        assert a['annee'] == sum(v['count_annee'] for v in a['titles'].values())
    same_keys(new['quality'], ref['quality'], 'ft_regions.quality')
    same_types(new['quality'], ref['quality'], 'ft_regions.quality')
    same_keys(new['fde'], ref['fde'], 'ft_regions.fde')
    same_types(new['fde'], ref['fde'], 'ft_regions.fde')
    assert new['quality']['total'] == sum(ft_fr_new['results'][t['id']]['count'] for t in new['titles_tracked'])
    assert all(t['term'] in ft_fr_new['results'][t['id']]['terms'] for t in new['titles_tracked'])
    assert len(new['fde']['employers']) <= 10 and all(isinstance(x, str) and x for x in new['fde']['employers'])
    lines.append('ft_regions.json: SCHEMA OK (18 regions identical to the reference codes/names, %d tracked titles)' % len(new['titles_tracked']))

    # corpus_ft.json (rewritten or, with --skip-corpus, the existing file)
    cpath = out_dir / 'corpus_ft.json'
    if not cpath.exists():
        lines.append('corpus_ft.json: absent, not validated')
    else:
        new, ref = load(cpath), load(ref_dir / 'corpus_ft.json')
        same_keys(new, ref, 'corpus_ft')
        same_types(new, ref, 'corpus_ft')
        assert new['total'] == len(new['offers']) == res['lake_n'] and new['calls'] == CALLS
        ref0 = ref['offers'][0]
        for o in (new['offers'][0], new['offers'][len(new['offers']) // 2], new['offers'][-1]):
            same_keys(o, ref0, 'corpus_ft.offers[]')
            same_types(o, ref0, 'corpus_ft.offers[]')
        ids = [o['id'] for o in new['offers']]
        assert len(set(ids)) == len(ids), 'duplicate ids in corpus_ft'
        keys = ['id', 't', 'd', 'r', 'c', 'dep']
        assert all(list(o) == keys for o in new['offers']), 'offers entries must have exactly id,t,d,r,c,dep'
        assert all(all(type(o[k]) is str for k in keys) for o in new['offers'])
        lines.append('corpus_ft.json: SCHEMA OK (%s offers, unique ids%s)' % (fmt_int(len(new['offers'])), ', existing file, not rewritten' if res['skip_corpus'] else ''))

    # DEP2REG / REGIONS vs the JS sources
    js = Path(root / '_prior' / 'PSTB-ELIA-jobs' / 'tools' / 'ingest_csp_regions.mjs').read_text(encoding='utf-8')
    mine = {r: [d for d in ds if d != '20'] for r, ds in REGION_DEPTS.items()}
    assert parse_js_dep2reg(js) == mine, 'DEP2REG differs from ingest_csp_regions.mjs'
    jsr = Path(root / '_prior' / 'PSTB-ELIA-jobs' / 'tools' / 'ingest_ft_regions.mjs').read_text(encoding='utf-8')
    js_regions = re.findall(r"\['(\d\d)',\s*'([^']+)'\]", jsr[jsr.index('const REGIONS'):jsr.index('const tax')])
    assert js_regions == REGIONS, 'REGIONS differs from ingest_ft_regions.mjs'
    lines.append('DEP2REG and REGIONS: identical to the .mjs sources (+ "20" for Corse)')
    return lines


# --------------------------------------------------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------------------------------------------------
def summarise(res, check_lines):
    results, ctx, tax = res['results'], res['ctx'], res['tax']
    fam_of = {t['id']: t['family'] for t in tax['titles']}
    reg = res['ft_regions']
    ref_results = json.loads(Path(res['ref_dir'] / 'ft_fr.json').read_text(encoding='utf-8'))['results']
    out = []
    out.append('===== SUMMARY =====')
    out.append('matching rule: term matches an offer if (a) its words minus stop-words occur in order within remaining words + %d consecutive tokens of '
               'title + description, OR (b) all its words occur anywhere in the title alone, each at least as many times as in the term (multiset)' % GAP)
    out.append('terms: [title_en, title_fr] + all aliases (dedup, len > 3, max %d) for AI families, [title_en] for context families; %d distinct terms' % (MAX_TERMS, res['n_terms']))
    out.append('live offers (ingest %s): %s of %s lake offers; collected_at %s; date_posted of the live stock %s -> %s'
               % (LIVE_INGEST, fmt_int(res['live_n']), fmt_int(res['lake_n']), COLLECTED_AT, str(res['dp_min'])[:10], str(res['dp_max'])[:19]))
    ai_ids = [t['id'] for t in tax['titles'] if not ctx.get(t['family'], False)]
    out.append('AI-family titles: %d with count>0 of %d; context titles: %d; sum of AI-title counts %s (API reference of 2026-10-04: %s)'
               % (sum(1 for i in ai_ids if results[i]['count'] > 0), len(ai_ids), len(tax['titles']) - len(ai_ids),
                  fmt_int(sum(results[i]['count'] for i in ai_ids)), fmt_int(sum(ref_results[i]['count'] for i in ai_ids))))
    out.append('')
    out.append('top 18 titles by count (count / count_31j) [ctx = context family]; terms with their own counts, * = best term:')
    top = sorted(tax['titles'], key=lambda t: -results[t['id']]['count'])[:18]
    for k, t in enumerate(top, 1):
        r = results[t['id']]
        best = res['best_term_of'][t['id']]
        out.append('  %2d. %-30s %7s / %-7s%s' % (k, t['id'], fmt_int(r['count']), fmt_int(r['count_31j']), '  [ctx]' if ctx.get(fam_of[t['id']]) else ''))
        out.append('        terms: ' + ' | '.join(('*' if term == best else '') + '%s %s' % (term, fmt_int(c)) for term, c in r['terms'].items()))
    out.append('')
    out.append('tracked titles (ft_regions.titles_tracked): id, best term, count / count_31j')
    for t in res['tracked']:
        r = results[t['id']]
        out.append('  %-30s %-38s %6s / %-6s' % (t['id'], res['best_term_of'][t['id']], fmt_int(r['count']), fmt_int(r['count_31j'])))
    q = reg['quality']
    rq = json.loads(Path(res['ref_dir'] / 'ft_regions.json').read_text(encoding='utf-8'))['quality']
    out.append('quality: total %s | cdi %s (%.1f %%) | debutants %s (%.1f %%)   [API reference of 2026-10-04: total %s | cdi %s (%.1f %%) | debutants %s (%.1f %%)]'
               % (fmt_int(q['total']), fmt_int(q['cdi']), 100 * q['cdi'] / max(1, q['total']), fmt_int(q['debutants']), 100 * q['debutants'] / max(1, q['total']),
                  fmt_int(rq['total']), fmt_int(rq['cdi']), 100 * rq['cdi'] / max(1, rq['total']), fmt_int(rq['debutants']), 100 * rq['debutants'] / max(1, rq['total'])))
    f = reg['fde']
    emp = ' | '.join('%s (%d)' % (n, res['employers_counts'].get(n, 0)) for n in f['employers']) or '(none)'
    out.append('FDE: term "%s", total %d, employers (%d, with number of FDE offers): %s' % (f['term'], f['total'], len(f['employers']), emp))
    out.append('')
    out.append('regions (total / recent <= 31 j / annee):')
    for r in reg['regions']:
        out.append('  %s %-28s %6s %6s %6s' % (r['code'], r['nom'], fmt_int(r['total']), fmt_int(r['recent']), fmt_int(r['annee'])))
    tot_all = sum(r['total'] for r in reg['regions'])
    rec_all = sum(r['recent'] for r in reg['regions'])
    ann_all = sum(r['annee'] for r in reg['regions'])
    idf = next(r for r in reg['regions'] if r['code'] == '11')
    metro = sum(r['total'] for r in reg['regions'] if r['code'] not in METRO_EXCLUDED)
    out.append('  all regions: %s / %s / %s' % (fmt_int(tot_all), fmt_int(rec_all), fmt_int(ann_all)))
    out.append('IDF share: %.1f %% of all regions (%s / %s), %.1f %% of metropolitan France (%s / %s); recent share %.1f %%; '
               'tracked-title matches without region: %s'
               % (100 * idf['total'] / max(1, tot_all), fmt_int(idf['total']), fmt_int(tot_all),
                  100 * idf['total'] / max(1, metro), fmt_int(idf['total']), fmt_int(metro), 100 * rec_all / max(1, tot_all), fmt_int(res['unreg_tracked'])))
    out.append('')
    if res['corpus_mb'] is None:
        out.append('corpus_ft.json: absent')
    else:
        out.append('corpus_ft.json: %s offers (both ingests), %s bytes = %.1f MB%s' % (fmt_int(res['lake_n']), fmt_int(res['corpus_bytes']), res['corpus_mb'],
                                                                                  ' (unchanged, not rewritten)' if res['skip_corpus'] else ' (rewritten)'))
        if not res['skip_corpus']:
            out.append('  titles "t" cleaned with clean_inclusive() imported from pipeline/site/build_csp.py: %s of %s changed (%.2f %%) = %s with an inclusive suffix removed '
                       '+ %s trimmed / double spaces collapsed only; examples of suffix removals (raw -> cleaned):'
                       % (fmt_int(res['corpus_changed']), fmt_int(res['lake_n']), 100 * res['corpus_changed'] / res['lake_n'],
                          fmt_int(res['corpus_suffix']), fmt_int(res['corpus_changed'] - res['corpus_suffix'])))
            for a, b in res['corpus_examples']:
                out.append('    %r -> %r' % (a, b))
    out.append('')
    out.extend(check_lines)

    # ---- sanity check against the reference API counts --------------------------------------------------------------------
    rp, rb = res['results_phr'], res['results_bag']
    out.append('')
    out.append('SANITY CHECK (title count = max over its terms): API ref = reference ft_fr.json of 2026-10-04 (first-alias terms only); '
               'final = this rule; phrase = rule (a) alone; bag = all words anywhere in title + description')
    out.append('  %-30s %8s %8s %8s %8s' % ('AI-family title', 'API ref', 'final', 'phrase', 'bag'))
    rows = sorted(ai_ids, key=lambda i: -max(results[i]['count'], ref_results[i]['count']))[:18]
    for i in rows:
        out.append('  %-30s %8s %8s %8s %8s' % (i, fmt_int(ref_results[i]['count']), fmt_int(results[i]['count']), fmt_int(rp[i]['count']), fmt_int(rb[i]['count'])))
    out.append('  %-30s %8s %8s %8s %8s' % ('sum over AI-family titles', fmt_int(sum(ref_results[i]['count'] for i in ai_ids)), fmt_int(sum(results[i]['count'] for i in ai_ids)),
                                           fmt_int(sum(rp[i]['count'] for i in ai_ids)), fmt_int(sum(rb[i]['count'] for i in ai_ids))))
    for name, rr in (('final', results), ('phrase', rp), ('bag', rb)):
        n, signed, med, within = agreement(rr, ref_results)
        out.append('  per-term agreement with the API reference (%d terms with API count >= 5), rule %-6s: median ln(new/API) %+.2f, median |ln| %.2f, within x1.5: %d/%d'
                   % (n, name, signed, med, within, n))

    out.append('')
    out.append('notes:')
    out.extend('  - ' + n for n in res['notes'])
    return '\n'.join(out)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('root', nargs='?', help='project root (default: two levels above this script)')
    ap.add_argument('--out', help='output directory (default: <root>/website/data)')
    ap.add_argument('--skip-corpus', action='store_true', help='do not (re)write corpus_ft.json (the existing file is still validated)')
    a = ap.parse_args()
    root = Path(a.root).resolve() if a.root else Path(__file__).resolve().parents[2]
    out_dir = Path(a.out).resolve() if a.out else root / 'website' / 'data'
    res = build(root, out_dir, a.skip_corpus)
    checks = validate(res, root)
    log('validation done')
    print()
    print(summarise(res, checks))
    for p in ('ft_fr.json', 'ft_regions.json', 'corpus_ft.json'):
        if (out_dir / p).exists():
            print('  %-18s %12s bytes  %s' % (p, fmt_int((out_dir / p).stat().st_size), out_dir / p))


if __name__ == '__main__':
    main()
