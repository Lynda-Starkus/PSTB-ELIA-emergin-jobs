# -*- coding: utf-8 -*-
"""Regenerate the two CSP (Choisir le Service Public) JSON inputs of the observatory from the data lake.

    website/data/csp_monthly.json    {collected_at, source, scanned, matched, no_region, months, regions, total}
    website/data/corpus_public.json  {collected_at, csp:[[title, year], ...], bpce:[], notes}

Schema and semantics: website/SPEC_DATA.md.  Reference files: _prior/PSTB-ELIA-jobs/data/{csp_monthly,corpus_public}.json.
The lexical filter (AI_LEX / AI_FALSE on the stripped title), strip(), REGION_CODE and DEP2REG are ported 1:1 from
_prior/PSTB-ELIA-jobs/tools/ingest_csp_regions.mjs (the regex sources are compared with that file at validation time).

Source: data-lake/lake/csp_postings.parquet (one row per posting, titles + metadata, no description).

Run:
    G:/Linda/Bureau/PSTB/ELIA/metiers-ia-emergents/.venv/Scripts/python pipeline/site/build_csp.py [project_root]
"""
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# --------------------------------------------------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------------------------------------------------
FIRST_MONTH = '2022-01'
LAST_MONTH = '2026-09'          # 2026-10 (current month at build time) is incomplete and excluded
SOURCE = 'Choisir le Service Public (DGAFP) \u2014 offres secteur public, filtre lexical IA ELIA'
NOTES = 'CSP: archives Choisir le Service Public 2022-2026 (data.gouv.fr), via data lake ELIA'
LAKE_COLUMNS = ['title', 'date_first_pub', 'date_posted', 'dept', 'localisation', 'lieu']

# Lexical filter: JS regex sources copied verbatim from ingest_csp_regions.mjs. They are applied to the *stripped*
# title (only a-z and single spaces), so the JS \b (ASCII word boundary) is reproduced with re.ASCII.
AI_LEX_SRC = r"\b(ia|intelligence artificielle|a\.i\.|genai|gen ai|g[ée]n[ée]rative|llm|gpt|machine learning|deep learning|ml ?ops|llm ?ops|data scien|nlp|computer vision|prompt|rag|agent (ia|ai)|agents? autonomes?|chatbot|mod[èe]les? de (langage|fondation)|ai act|fine ?tun|annotation|vision par ordinateur)\b|\bai\b"
AI_FALSE_SRC = r"ia[- ]?ipr|\bipr\b|inspecteur|inspectrice|rectorat|dasen|acad[ée]mie|instruction en famille|\bien\b.{0,20}degr"
AI_LEX = re.compile(AI_LEX_SRC, re.ASCII)
AI_FALSE = re.compile(AI_FALSE_SRC, re.ASCII)

_COMBINING = re.compile('[\u0300-\u036f]')      # same range as the JS /[\u0300-\u036f]/g
_NOT_AZ = re.compile('[^a-z ]+')
_SPACES = re.compile(r'\s+')


def strip(s):
    """Exact port of the JS strip(): lower-case, NFD, drop combining marks, non [a-z ] runs -> ' ', collapse, trim."""
    s = unicodedata.normalize('NFD', str(s).lower())
    s = _COMBINING.sub('', s)
    s = _NOT_AZ.sub(' ', s)
    s = _SPACES.sub(' ', s)
    return s.strip()


_INCL_SUFFIX = r"(?:e|es|euse|euses|trice|trices|rice|rices|ne|nes|ère|ères|ere|eres|ve|ves|se|ses|le|les|ice|ices|ale|ales|elle|elles|ienne|iennes|eur|eurs)"
_INCL = [re.compile(r"(?<=\w)[·•∙/]\s?" + _INCL_SUFFIX + r"(?![\wàâäéèêëîïôöùûüç])", re.I),   # chercheur·euse, contractuel·le, Enseignant/e, Chercheur/euse
         re.compile(r"(?<=\w)\(" + _INCL_SUFFIX + r"\)", re.I),                                 # chargé(e), directeur(trice)
         re.compile(r"(?<=\w)\.(?:e|es|euse|trice|rice|ne|le|ve|se)(?![\wàâäéèêëîïôöùûüç])", re.I),  # ingénieur.e
         re.compile(r"(?<=[a-zéèàç])-(?:e|es|euse|trice|rice|ne|le|ve|se)(?![\wàâäéèêëîïôöùûüç])")]  # enseignant-e


def clean_inclusive(t):
    """Remove French inclusive-writing suffixes (chercheur·euse, chargé(e), ingénieur.e, enseignant-e) from a title."""
    for rx in _INCL:
        t = rx.sub('', t)
    return re.sub(r'\s{2,}', ' ', t).strip()


def is_ai(title):
    """Row counts as AI when len(strip(title)) >= 4 and AI_LEX matches and AI_FALSE does not."""
    t = strip(title) if isinstance(title, str) else ''
    return len(t) >= 4 and AI_LEX.search(t) is not None and AI_FALSE.search(t) is None


# Region names (stripped) -> INSEE region code, as in the JS REGION_CODE map.
REGION_CODE = {
    'ile de france': '11', 'centre val de loire': '24', 'bourgogne franche comte': '27', 'normandie': '28',
    'hauts de france': '32', 'grand est': '44', 'pays de la loire': '52', 'bretagne': '53',
    'nouvelle aquitaine': '75', 'occitanie': '76', 'auvergne rhone alpes': '84',
    'provence alpes cote d azur': '93', 'provence alpes cote dazur': '93', 'corse': '94',
    'guadeloupe': '01', 'martinique': '02', 'guyane': '03', 'la reunion': '04', 'reunion': '04', 'mayotte': '06',
}
# Department -> INSEE region code, as in the JS DEP2REG (lower-case keys: '2a', '2b'; overseas 971..976).
DEP2REG = {}
for _reg, _deps in {
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
    '94': ['2a', '2b'],
    '01': ['971'], '02': ['972'], '03': ['973'], '04': ['974'], '06': ['976'],
}.items():
    for _d in _deps:
        DEP2REG[_d] = _reg

REGION_NAME = {
    '11': 'Ile-de-France', '24': 'Centre-Val de Loire', '27': 'Bourgogne-Franche-Comte', '28': 'Normandie',
    '32': 'Hauts-de-France', '44': 'Grand Est', '52': 'Pays de la Loire', '53': 'Bretagne',
    '75': 'Nouvelle-Aquitaine', '76': 'Occitanie', '84': 'Auvergne-Rhone-Alpes',
    '93': "Provence-Alpes-Cote d'Azur", '94': 'Corse',
    '01': 'Guadeloupe', '02': 'Martinique', '03': 'Guyane', '04': 'La Reunion', '06': 'Mayotte',
}

# Department code between parentheses in the 'localisation' text, e.g. "Landes (40)", "Reunion (974)", "Corse du Sud (2a)".
# JS: /\((\d{2,3}|2a|2b)\)/i ; made tolerant to inner spaces because the lake has "Cher (18 )" and "Correze (19 )".
_DEPT_IN_PARENS = re.compile(r'\(\s*(\d{2,3}|2a|2b)\s*\)', re.I | re.ASCII)
_POSTAL_CODE = re.compile(r'\b(\d{5})\b', re.ASCII)
# a 5-digit number right after CS / BP / TSA is a mail-box number, not a postal code ("CS 60032   63001 Clermont-Ferrand")
_MAILBOX_BEFORE = re.compile(r'(?:\bcs|\bbp|\btsa|\bcedex)\s*$', re.I | re.ASCII)


def postal_code_in(text):
    """First 5-digit group of `text` that is not a CS/BP/TSA mail-box number (JS: first \\b\\d{5}\\b), else None."""
    for m in _POSTAL_CODE.finditer(text):
        if not _MAILBOX_BEFORE.search(text[:m.start()]):
            return m.group(1)
    return None


def region_from_dept(d):
    """DEP2REG lookup, case-insensitive; like the JS: full code first (2a/2b/971..976), then its first 2 characters."""
    if not isinstance(d, str):
        return None
    d = d.strip().lower()
    if not d:
        return None
    return DEP2REG.get(d) or DEP2REG.get(d[:2])


def resolve_region(dept, localisation, lieu):
    """Return (INSEE region code or None, rule that resolved it).

    1. `dept` column of the lake (DEP2REG);
    2. department code written in 'localisation' (the lake's dept column misses '(2a)', '(2b)', '(18 )', '(19 )' and the
       3-digit overseas codes), then DEP2REG;
    3. REGION_CODE on the stripped 'localisation' text (e.g. "Reunion (974)" -> 'reunion');
    4. postal code found in 'lieu' (lieu d'affectation), as the last resort of the JS script (20xxx = Corsica).
    """
    code = region_from_dept(dept)
    if code:
        return code, 'dept'
    if isinstance(localisation, str):
        m = _DEPT_IN_PARENS.search(localisation)
        if m:
            code = region_from_dept(m.group(1))
            if code:
                return code, 'localisation_code'
        code = REGION_CODE.get(strip(localisation))
        if code:
            return code, 'localisation_name'
    if isinstance(lieu, str):
        p = postal_code_in(lieu)
        if p:
            d = p[:3] if p.startswith('97') else p[:2]
            code = DEP2REG.get(d) or ('94' if d == '20' else None)
            if code:
                return code, 'lieu_postal_code'
    return None, 'none'


# --------------------------------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------------------------------
def log(*a):
    print(*a, file=sys.stderr, flush=True)


def iso_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def month_range(first, last):
    y, m = (int(x) for x in first.split('-'))
    ly, lm = (int(x) for x in last.split('-'))
    out = []
    while (y, m) <= (ly, lm):
        out.append(f'{y:04d}-{m:02d}')
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def region_sort_key(code):
    # same order as the JS object of the reference: metropolitan codes ascending, then the overseas ones ('01'...'06')
    return (code.startswith('0'), code)


def write_json_atomic(path, obj):
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, path)


def write_corpus_public(path, titles, years, collected_at, chunk=100_000):
    """Stream {"collected_at":..,"csp":[[title,year],..],"bpce":[],"notes":..} without building one giant string."""
    tmp = path.with_name(path.name + '.tmp')
    dumps = json.dumps
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write('{"collected_at":' + dumps(collected_at) + ',"csp":[')
        for i in range(0, len(titles), chunk):
            rows = [[t if isinstance(t, str) else '', y] for t, y in zip(titles[i:i + chunk], years[i:i + chunk])]
            s = dumps(rows, ensure_ascii=False, separators=(',', ':'))
            f.write(s[1:-1] if i == 0 else ',' + s[1:-1])
        f.write('],"bpce":[],"notes":' + dumps(NOTES, ensure_ascii=False) + '}')
    os.replace(tmp, path)


# --------------------------------------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------------------------------------
def check_regex_sources(js_path):
    """The Python regex sources must be character-for-character the ones of the JS script."""
    if not js_path.exists():
        log('  (regex source check skipped: %s not found)' % js_path)
        return False
    txt = js_path.read_text(encoding='utf-8')
    for name, src in (('AI_LEX', AI_LEX_SRC), ('AI_FALSE', AI_FALSE_SRC)):
        m = re.search(r'^const %s = /(.*)/;\s*$' % name, txt, re.M)
        assert m, 'cannot find %s in %s' % (name, js_path)
        assert m.group(1) == src, '%s differs from the JS source:\nJS: %s\nPY: %s' % (name, m.group(1), src)
    return True


def check_schema(name, new_path, ref_path, type_exempt=()):
    new = json.loads(new_path.read_text(encoding='utf-8'))
    ref = json.loads(ref_path.read_text(encoding='utf-8'))
    assert list(new.keys()) == list(ref.keys()), 'top-level keys differ for %s: %s vs %s' % (name, list(new), list(ref))
    for k in ref:
        if k not in type_exempt:
            assert type(new[k]) is type(ref[k]), '%s.%s: type %s vs reference %s' % (name, k, type(new[k]).__name__, type(ref[k]).__name__)
    return new, ref


def validate_csp_monthly(new, ref, scanned, matched, no_region_all, n_out_of_window):
    assert new['source'] == ref['source']
    months = new['months']
    assert months == month_range(FIRST_MONTH, LAST_MONTH) and months == sorted(months)
    assert len(new['total']) == len(months)
    assert all(isinstance(v, int) for v in new['total'])
    assert new['scanned'] == scanned and new['matched'] == matched and new['no_region'] == no_region_all
    for code, series in new['regions'].items():
        assert code in REGION_NAME, 'unknown region code %s' % code
        assert len(series) == len(months) and all(isinstance(v, int) for v in series), code
        assert sum(series) > 0, 'region %s has no AI row (should be omitted)' % code
    assert set(new['regions']) == {c for c, s in new['regions'].items() if sum(s) > 0}
    for i, t in enumerate(new['total']):                        # per month: total >= sum of the regions
        assert t >= sum(s[i] for s in new['regions'].values()), months[i]
    assert sum(new['total']) + n_out_of_window == matched
    assert type(ref['regions']) is dict and all(len(s) == len(ref['months']) for s in ref['regions'].values())


def validate_corpus_public(new, scanned):
    assert len(new['csp']) == scanned
    assert new['bpce'] == [] and isinstance(new['notes'], str) and new['notes'] == NOTES
    assert all(isinstance(r, list) and len(r) == 2 and isinstance(r[0], str) and isinstance(r[1], int) for r in new['csp'])


# --------------------------------------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------------------------------------
def main():
    t0 = time.time()
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
    src = root / 'data-lake' / 'lake' / 'csp_postings.parquet'
    out_dir = root / 'website' / 'data'
    ref_dir = root / '_prior' / 'PSTB-ELIA-jobs' / 'data'
    js_path = root / '_prior' / 'PSTB-ELIA-jobs' / 'tools' / 'ingest_csp_regions.mjs'
    out_dir.mkdir(parents=True, exist_ok=True)

    regex_checked = check_regex_sources(js_path)

    log('reading', src)
    df = pd.read_parquet(src, columns=LAKE_COLUMNS)
    scanned = len(df)
    titles = [clean_inclusive(t) if isinstance(t, str) else t for t in df['title'].tolist()]
    dept = df['dept'].tolist()
    localisation = df['localisation'].tolist()
    lieu = df['lieu'].tolist()
    d = df['date_first_pub'].fillna(df['date_posted'])           # month / year: date_first_pub, fallback date_posted
    month_all = d.dt.strftime('%Y-%m').tolist()                  # NaN when no date at all
    year_all = d.dt.year.fillna(0).astype('int64').tolist()      # 0 when no date at all
    del df, d
    log('  %d rows, %.1fs' % (scanned, time.time() - t0))

    log('lexical filter ...')
    ai_idx = [i for i, t in enumerate(titles) if is_ai(t)]
    log('  %d candidate AI rows, %.1fs' % (len(ai_idx), time.time() - t0))

    months = month_range(FIRST_MONTH, LAST_MONTH)
    midx = {m: i for i, m in enumerate(months)}
    total = [0] * len(months)
    regions = {}
    matched = 0
    no_region_all = 0
    n_out_of_window = 0
    n_no_date = 0
    steps = Counter()
    for i in ai_idx:
        month = month_all[i]
        if not isinstance(month, str):          # JS: a row without a valid month is skipped (never counted as matched)
            n_no_date += 1
            continue
        matched += 1
        code, step = resolve_region(dept[i], localisation[i], lieu[i])
        steps[step] += 1
        if code is None:
            no_region_all += 1
        k = midx.get(month)
        if k is None:                           # before 2022-01 or after 2026-09: counted in `matched` only
            n_out_of_window += 1
            continue
        total[k] += 1
        if code is not None:
            regions.setdefault(code, [0] * len(months))[k] += 1
    regions = {c: regions[c] for c in sorted(regions, key=region_sort_key)}

    # ---- csp_monthly.json
    collected_at = iso_now()
    csp_monthly = {
        'collected_at': collected_at,
        'source': SOURCE,
        'scanned': scanned,
        'matched': matched,
        'no_region': no_region_all,
        'months': months,
        'regions': regions,
        'total': total,
    }
    p_monthly = out_dir / 'csp_monthly.json'
    write_json_atomic(p_monthly, csp_monthly)
    log('  wrote', p_monthly, '%.1fs' % (time.time() - t0))

    # ---- corpus_public.json
    p_corpus = out_dir / 'corpus_public.json'
    write_corpus_public(p_corpus, titles, year_all, iso_now())
    log('  wrote', p_corpus, '%.1fs' % (time.time() - t0))

    # ---- summary
    print('=== build_csp.py : data-lake CSP -> website/data ===')
    print('scanned   :', scanned)
    print('matched   :', matched, '(AI rows, all months)')
    print('no_region :', no_region_all)
    print('region rule (AI rows):', ', '.join('%s=%d' % (k, steps[k]) for k in
          ('dept', 'localisation_code', 'localisation_name', 'lieu_postal_code', 'none')))
    per_year = Counter()
    for m, n in zip(months, total):
        per_year[m[:4]] += n
    print('AI rows per year (%s..%s):' % (months[0], months[-1]),
          '  '.join('%s=%d' % (y, per_year[y]) for y in sorted(per_year)), '| window total=%d' % sum(total),
          '| outside window=%d' % n_out_of_window)
    top = sorted(regions, key=lambda c: -sum(regions[c]))[:5]
    print('top 5 regions (AI rows):', ', '.join('%s %s=%d' % (c, REGION_NAME[c], sum(regions[c])) for c in top))
    print('regions with AI rows  :', len(regions), '(', ' '.join(regions), ')')
    print('months    : %s -> %s (%d months)' % (months[0], months[-1], len(months)))
    print('csp_monthly.json   : %.1f KB' % (p_monthly.stat().st_size / 1024))
    print('corpus_public.json : %.1f MB, %d rows' % (p_corpus.stat().st_size / 1048576, scanned))

    # ---- validation against the reference files
    if regex_checked:
        print('REGEX OK AI_LEX / AI_FALSE identical to tools/ingest_csp_regions.mjs')
    new, ref = check_schema('csp_monthly', p_monthly, ref_dir / 'csp_monthly.json')
    validate_csp_monthly(new, ref, scanned, matched, no_region_all, n_out_of_window)
    print('SCHEMA OK csp_monthly.json  (keys: %s)' % ','.join(new))
    new, ref = check_schema('corpus_public', p_corpus, ref_dir / 'corpus_public.json', type_exempt=('notes',))
    validate_corpus_public(new, scanned)
    print('SCHEMA OK corpus_public.json (keys: %s; notes is a string per SPEC_DATA.md, the reference holds a list of log lines)'
          % ','.join(new))
    log('done in %.1fs' % (time.time() - t0))


if __name__ == '__main__':
    main()
