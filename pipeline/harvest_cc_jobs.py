# -*- coding: utf-8 -*-
"""Harvest French job postings (schema.org JobPosting in JSON-LD) from the Common Crawl web archive.

Only Common Crawl's public infrastructure is contacted: the CDX index server (index.commoncrawl.org) and the WARC
files (data.commoncrawl.org, HTTPS range requests). The job boards themselves are never contacted.

Subcommands
  index  For every (crawl, host pattern), query the CDX API (status-200 captures) page by page and save the captures
         to data-lake/raw/cc_jobs/index/<crawl>/<host>.jsonl. Each page is committed in <host>.state.json, so an
         interrupted run resumes where it stopped. At most 2 concurrent CDX requests, up to 8 retries with exponential
         backoff from 10 s (the server answers 502/504 under load).
  fetch  For every saved capture not processed yet, range-request its WARC record, extract the JobPosting objects of
         the <script type="application/ld+json"> blocks, normalise them, keep the French ones, dedupe across crawls
         (earliest capture kept) and append them to data-lake/raw/cc_jobs/postings/<crawl>.ndjson. Processed captures
         are listed in <crawl>.done (resumable). Writes data-lake/raw/cc_jobs/manifest.json.
  build  Concatenate the NDJSON files into data-lake/lake/cc_jobs_fr.parquet (deduplicated) and print counts per host
         and per year of datePosted.

Examples (from the project root)
  python pipeline/harvest_cc_jobs.py index --crawls CC-MAIN-2026-30 --hosts www.hellowork.com fr.talent.com
  python pipeline/harvest_cc_jobs.py fetch --limit 300
  python pipeline/harvest_cc_jobs.py build
  nohup python -u pipeline/harvest_cc_jobs.py index > data-lake/raw/cc_jobs/_index.log 2>&1 &

Notes
  * Pages are requested one index block at a time (pageSize=1, ~3000 lines): the default 5-block pages of large hosts
    exceed the ~10 s gateway timeout of index.commoncrawl.org and fail with 502/504 on every retry.
  * The CDX server only understands a trailing '*' (prefix query). A pattern with an inner '*'
    (welcometothejungle, free-work) is queried by its prefix up to the first '*' and the URLs are filtered locally.
  * Dedupe key: the capture URL (normalised: no scheme, no 'www.', no tracking parameters), or (host, identifier)
    guarded by title + employer + city so that a site-wide constant identifier cannot collapse distinct postings.
  * Common Crawl terms of use: https://commoncrawl.org/terms-of-use
"""
import argparse
import codecs
import html
import json
import math
import os
import random
import re
import sys
import threading
import time
import zlib
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
CC_DIR = ROOT / 'data-lake' / 'raw' / 'cc_jobs'
INDEX_DIR = CC_DIR / 'index'
POST_DIR = CC_DIR / 'postings'
MANIFEST = CC_DIR / 'manifest.json'
LAKE_FILE = ROOT / 'data-lake' / 'lake' / 'cc_jobs_fr.parquet'

USER_AGENT = ('ELIA-PSTB-research-harvester/1.0 (ELIA lab, PST&B: academic study of emerging AI occupations in France; '
              'reads the Common Crawl index and WARC files only; contact: linda.belkessa@univ-eiffel.fr)')
COLLINFO_URL = 'https://index.commoncrawl.org/collinfo.json'
CDX_URL = 'https://index.commoncrawl.org/{crawl}-index'
DATA_URL = 'https://data.commoncrawl.org/'
FIRST_CRAWL, LAST_CRAWL = 'CC-MAIN-2023-06', 'CC-MAIN-2026-39'
CDX_FIELDS = 'url,timestamp,filename,offset,length,mime'
CDX_PAGE_SIZE = 1                       # index blocks (~3000 lines) per page; the default 5 hits the 10 s gateway timeout
CDX_CONCURRENCY = 2                     # never more than 2 CDX requests in flight overall
CDX_RETRIES, CDX_BACKOFF, CDX_BACKOFF_MAX = 8, 10.0, 600.0
CDX_PAUSE = 1.0                         # polite pause after every CDX request, while still holding its slot
WARC_RETRIES, WARC_BACKOFF, WARC_BACKOFF_MAX = 8, 5.0, 300.0
RETRY_HTTP = {403, 408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}
# the CDX server also wraps its own backend failures in a 400, e.g. "Error: ('Connection aborted.', ConnectionResetError..."
TRANSIENT_BODY_RX = re.compile(r'connection|reset|aborted|timed? ?out|temporar|unavailable|errno|broken pipe|'
                               r'max retries|too many', re.I)
DESC_MAX = 6000

PATTERNS = [
    'www.hellowork.com/fr-fr/emplois/*',
    'www.welcometothejungle.com/fr/companies/*/jobs/*',
    'www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/*',
    'www.cadremploi.fr/emploi/detail_offre*',
    'fr.talent.com/view*',
    'www.jobteaser.com/fr/job-offers/*',
    'www.monster.fr/emploi/offre/*',
    'www.free-work.com/fr/tech-it/*/job-mission/*',
    'www.lesjeudis.com/offre/*',
    'www.meteojob.com/candidat/offres/*',
    'www.jobijoba.com/fr/annonce/*',
    'www.optioncarriere.com/jobad/*',
    'emplois.leboncoin.fr/*',
    'candidat.francetravail.fr/offres/recherche/detail/*',
    'candidat.pole-emploi.fr/offres/recherche/detail/*',   # same offers before the January 2024 rebranding
    'choisirleservicepublic.gouv.fr/offre-emploi/*',
    'fr.indeed.com/viewjob*',
    'www.glassdoor.fr/job-listing/*',
    'www.linkedin.com/jobs/view/*',
]
FOREIGN_BOARDS = {'www.linkedin.com'}   # worldwide boards: keep only postings located in France
FR_COUNTRY = {'fr', 'fra', 'france', 'la france', 'french republic', 'république française', 'republique francaise'}
COLUMNS = ['url', 'crawl', 'capture_time', 'host', 'title', 'description', 'datePosted', 'validThrough',
           'employmentType', 'employer', 'city', 'postalCode', 'region', 'country', 'salary_min', 'salary_max',
           'salary_currency', 'salary_unit', 'identifier', 'industry', 'occupationalCategory', 'jp_index',
           'warc_filename', 'warc_offset', 'warc_length']


# ----------------------------------------------------------------------------------------------- small utilities
def log(*parts):
    print(time.strftime('%Y-%m-%d %H:%M:%S'), *parts, flush=True)


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def read_json(path, default=None):
    for _ in range(30):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return default
        except (PermissionError, ValueError):      # being replaced by another process right now
            time.sleep(0.1)
    return default


def write_json(path, obj):
    """Atomic write (temp file + rename), retried because Windows refuses to replace a file that is open elsewhere."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.{os.getpid()}.{threading.get_ident()}.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    for _ in range(50):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.1)
    os.replace(tmp, path)


def acquire_lock(path):
    """Exclusive lock held for the life of the process (released by the OS if it dies)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, 'a+')
    try:
        if os.name == 'nt':
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(f'another harvest_cc_jobs run already holds {path}; wait for it or stop it first')
    return fh


def repair_tail(path):
    """Drop a torn last line (process killed in the middle of a write)."""
    if not path.exists() or path.stat().st_size == 0:
        return
    with open(path, 'rb+') as f:
        f.seek(-1, 2)
        if f.read(1) == b'\n':
            return
        pos = f.seek(0, 2)
        while pos > 0:
            start = max(0, pos - 65536)
            f.seek(start)
            i = f.read(pos - start).rfind(b'\n')
            if i >= 0:
                f.truncate(start + i + 1)
                return
            pos = start
        f.truncate(0)


_tls = threading.local()


def http():
    s = getattr(_tls, 'session', None)
    if s is None:
        s = requests.Session()
        s.headers['User-Agent'] = USER_AGENT
        _tls.session = s
    return s


def host_of(pattern):
    return pattern.split('/', 1)[0]


def select_patterns(tokens):
    if not tokens:
        return list(PATTERNS)
    for t in tokens:
        if not any(t in p for p in PATTERNS):
            log(f'warning: --hosts {t} matches no pattern')
    return [p for p in PATTERNS if any(t in p for t in tokens)]


def list_crawls(first, last):
    cache = CC_DIR / 'collinfo.json'
    data = None
    for attempt in range(5):
        try:
            r = http().get(COLLINFO_URL, timeout=60)
            r.raise_for_status()
            data = r.json()
            write_json(cache, data)
            break
        except (requests.RequestException, ValueError) as e:
            wait = 10 * 2 ** attempt
            log(f'collinfo.json: {type(e).__name__}, retry in {wait}s')
            time.sleep(wait)
    if data is None:
        data = read_json(cache)
        if data is None:
            sys.exit('cannot read the Common Crawl collection list')
    return sorted(c['id'] for c in data
                  if re.fullmatch(r'CC-MAIN-\d{4}-\d{2}', c.get('id', '')) and first <= c['id'] <= last)


# ------------------------------------------------------------------------------------------------------- index
class CDXError(Exception):
    pass


_cdx_slots = threading.BoundedSemaphore(CDX_CONCURRENCY)


def cdx_get(crawl, params, what, parse):
    """One CDX API call with retries; returns parse(body), parse('') when the server reports no capture."""
    url = CDX_URL.format(crawl=crawl)
    last = None
    for attempt in range(CDX_RETRIES + 1):
        if attempt:
            wait = min(CDX_BACKOFF * 2 ** (attempt - 1), CDX_BACKOFF_MAX) * random.uniform(0.9, 1.1)
            log(f'  {what}: {last} -> retry {attempt}/{CDX_RETRIES} in {wait:.0f}s')
            time.sleep(wait)
        with _cdx_slots:
            try:
                r = http().get(url, params=params, timeout=(30, 300))
                code, body = r.status_code, r.text
            except requests.RequestException as e:
                code, body = None, type(e).__name__
            time.sleep(CDX_PAUSE)
        if code == 404 and 'No Captures found' in body:
            return parse('')
        if code == 200:
            try:
                return parse(body)
            except ValueError as e:                    # truncated or HTML body behind a 200
                last = f'malformed response ({str(e)[:60]})'
                continue
        last = f'HTTP {code}' if code else body
        if code is not None and code not in RETRY_HTTP and not (code == 400 and TRANSIENT_BODY_RX.search(body[:500])):
            raise CDXError(f'{what}: HTTP {code}: {body[:200]!r}')
    raise CDXError(f'{what}: gave up after {CDX_RETRIES} retries (last: {last})')


def parse_cdx(body):
    return [json.loads(line) for line in body.splitlines() if line.strip()]


def parse_numpages(body):
    if not body.strip():
        return {'pages': 0, 'blocks': 0}
    v = json.loads(body)
    return v if isinstance(v, dict) else {'pages': int(v), 'blocks': None}


def cdx_query(pattern):
    """The CDX server only honours a trailing '*' (prefix query): cut the pattern at its first '*'."""
    return pattern.split('*', 1)[0] + '*' if '*' in pattern else pattern


def pattern_regex(pattern):
    """Local URL filter: inner '*' = any path part, trailing '*' = anything. Scheme, 'www.' and port are optional
    because the CDX server canonicalises them away."""
    host, _, path = pattern.partition('/')
    host = host[4:] if host.startswith('www.') else host
    trailing = path.endswith('*')
    core = path[:-1] if trailing else path
    rx = '[^?#]*'.join(re.escape(p) for p in core.split('*'))
    rx += '.*' if trailing else '(?:[?#].*)?$'
    return re.compile(r'^(?:https?://)?(?:www\.)?' + re.escape(host) + r'(?::\d+)?/' + rx, re.I)


def index_pair(crawl, pattern, pos):
    """Index one (crawl, pattern); resumable page by page. Returns the state dict."""
    host = host_of(pattern)
    d = INDEX_DIR / crawl
    d.mkdir(parents=True, exist_ok=True)
    jf, sf = d / f'{host}.jsonl', d / f'{host}.state.json'
    st = read_json(sf, None)
    if not st or st.get('pattern') != pattern or (not st.get('complete')
                                                   and st.get('page_size', 5) != CDX_PAGE_SIZE):
        st = {'crawl': crawl, 'host': host, 'pattern': pattern, 'query': cdx_query(pattern), 'num_pages': None,
              'page_size': CDX_PAGE_SIZE, 'blocks': None, 'pages': {}, 'bytes': 0, 'captures': 0, 'complete': False}
    if st['complete']:
        log(f'[{pos}] {crawl} {host:<34} captures {st["captures"]:>7} (already indexed)')
        return st
    if jf.exists() and jf.stat().st_size != st['bytes']:   # bytes appended after the last committed page
        with open(jf, 'r+b') as f:
            f.truncate(st['bytes'])
    elif not jf.exists():
        st.update(pages={}, bytes=0, captures=0)
    t0 = time.time()
    base = {'url': st['query'], 'output': 'json', 'pageSize': st['page_size']}
    if st['num_pages'] is None:
        info = cdx_get(crawl, {**base, 'showNumPages': 'true'}, f'{crawl} {host} numpages', parse_numpages)
        st['num_pages'], st['blocks'] = int(info.get('pages') or 0), info.get('blocks')
        write_json(sf, st)
    rx, failed = pattern_regex(pattern), []
    for page in range(st['num_pages']):
        if str(page) in st['pages']:
            continue
        what = f'{crawl} {host} page {page + 1}/{st["num_pages"]}'
        try:
            rows = cdx_get(crawl, {**base, 'filter': 'status:200', 'fl': CDX_FIELDS, 'page': page}, what, parse_cdx)
        except CDXError as e:
            log(f'  FAILED {e}')
            failed.append(page)
            continue
        keep = [r for r in rows if rx.match(r.get('url', ''))]
        blob = ''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n' for r in keep).encode('utf-8')
        with open(jf, 'ab') as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        st['bytes'] += len(blob)
        st['pages'][str(page)] = {'captures': len(keep), 'raw': len(rows)}
        st['captures'] = sum(p['captures'] for p in st['pages'].values())
        write_json(sf, st)
    raw = sum(p['raw'] for p in st['pages'].values())
    st['complete'] = len(st['pages']) == st['num_pages']
    st['updated'] = now_iso()
    write_json(sf, st)
    log(f'[{pos}] {crawl} {host:<34} captures {st["captures"]:>7}'
        + (f' (of {raw} raw lines)' if raw != st['captures'] else '')
        + f'  pages {len(st["pages"])}/{st["num_pages"]}  {time.time() - t0:.0f}s'
        + (f'  FAILED pages {failed} (re-run index to retry)' if failed else ''))
    return st


def cmd_index(args):
    lock = acquire_lock(INDEX_DIR / '.lock')
    crawls = sorted(args.crawls) if args.crawls else list_crawls(args.first, args.last)
    crawls.sort(reverse=args.order == 'newest')
    pats = select_patterns(args.hosts)
    pairs = [(c, p) for c in crawls for p in pats]
    if not pairs:
        sys.exit('nothing to index')
    log(f'index: pid {os.getpid()}, {len(crawls)} crawls ({crawls[0]} .. {crawls[-1]}), {len(pats)} patterns, '
        f'{len(pairs)} (crawl, host) pairs, {CDX_CONCURRENCY} concurrent CDX requests max')
    t0, results = time.time(), {}
    with ThreadPoolExecutor(CDX_CONCURRENCY) as ex:
        futs = {ex.submit(index_pair, c, p, f'{i + 1}/{len(pairs)}'): (c, p) for i, (c, p) in enumerate(pairs)}
        for k, fut in enumerate(as_completed(futs), 1):
            c, p = futs[fut]
            try:
                results[(c, p)] = fut.result()
            except Exception as e:                      # CDXError on numpages, disk error, ...
                log(f'  FAILED {c} {host_of(p)}: {type(e).__name__}: {e}')
            if k % 10 == 0:
                write_manifest()
    by_host, by_crawl = Counter(), Counter()
    for (c, p), st in results.items():
        by_host[host_of(p)] += st['captures']
        by_crawl[c] += st['captures']
    incomplete = [f'{c} {host_of(p)}' for (c, p) in pairs if not results.get((c, p), {}).get('complete')]
    log(f'index finished in {(time.time() - t0) / 60:.1f} min; captures per host:')
    for h, n in by_host.most_common():
        print(f'  {h:<36} {n:>9}')
    print('  captures per crawl: ' + ', '.join(f'{c} {by_crawl[c]}' for c in sorted(by_crawl)))
    if incomplete:
        log(f'{len(incomplete)} pairs incomplete, re-run the same command to resume: {incomplete[:20]}')
    write_manifest()
    lock.close()


# ---------------------------------------------------------------------------------- WARC record -> JobPosting
LD_RX = re.compile(rb'<script\b[^>]*?\btype\s*=\s*["\']?\s*application/ld\+json[^>]*>(.*?)</script\s*>', re.I | re.S)
MICRODATA_RX = re.compile(rb'itemtype\s*=\s*["\']?\s*https?://(?:www\.)?schema\.org/JobPosting', re.I)
META_CHARSET_RX = re.compile(rb'<meta[^>]+charset\s*=\s*["\']?\s*([A-Za-z0-9_.:-]+)', re.I)
HTTP_STATUS_RX = re.compile(rb'^HTTP/\S+\s+(\d{3})')
CDATA_RX = re.compile(r'^\s*(?://\s*)?<!\[CDATA\[|(?://\s*)?\]\]>\s*$')
COMMENT_RX = re.compile(r'^\s*<!--|-->\s*$')
TRAILING_COMMA_RX = re.compile(r',\s*([}\]])')
CTRL_RX = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
TAG_RX = re.compile(r'<[^>]*>')
BLOCK_TAG_RX = re.compile(r'<\s*/?\s*(?:br|p|div|li|ul|ol|h[1-6]|tr|table|section|article|blockquote)\b[^>]*>', re.I)
SPACES_RX = re.compile(r'[ \t\r\f\v  -​  　]+')
NEWLINES_RX = re.compile(r'\s*\n\s*')
TRACKING_RX = re.compile(r'^(?:utm_\w+|xtor|gclid|fbclid|msclkid|mc_[ce]id|_ga|ref|refid|referer|referrer|trackingid|trk|'
                         r'tk|from|src|source|origin|campaign|cmp|at_\w+|mtm_\w+|pk_\w+|position|pagenum|pos|rank|'
                         r'trigger_from)$', re.I)


class PermanentHTTPError(Exception):
    pass


def download_record(filename, offset, length):
    """HTTPS range request of one gzip member of a Common Crawl WARC file, with retries."""
    url = DATA_URL + filename
    hdrs = {'Range': f'bytes={offset}-{offset + length - 1}', 'Accept-Encoding': 'identity'}
    last = None
    for attempt in range(WARC_RETRIES + 1):
        if attempt:
            time.sleep(min(WARC_BACKOFF * 2 ** (attempt - 1), WARC_BACKOFF_MAX) * random.uniform(0.8, 1.2))
        try:
            with http().get(url, headers=hdrs, timeout=(20, 120), stream=True) as r:
                if r.status_code == 206:
                    data = r.content
                    if len(data) == length:
                        return data
                    last = f'short read {len(data)}/{length}'
                elif r.status_code in RETRY_HTTP:
                    last = f'HTTP {r.status_code}'
                else:                                   # 404/416: never retry; 200 = range ignored, body not read
                    raise PermanentHTTPError(r.status_code)
        except requests.RequestException as e:
            last = type(e).__name__
    raise IOError(f'gave up after {WARC_RETRIES} retries ({last})')


def parse_headers(lines):
    h = {}
    for ln in lines:
        k, sep, v = ln.partition(b':')
        if sep:
            k, v = k.strip().lower().decode('latin-1'), v.strip().decode('latin-1')
            h[k] = f'{h[k]}, {v}' if k in h else v
    return h


def dechunk(b):
    out, i = bytearray(), 0
    while True:
        j = b.find(b'\r\n', i)
        if j < 0:
            break
        try:
            n = int(b[i:j].split(b';')[0].strip() or b'0', 16)
        except ValueError:
            return b                                    # not really chunked
        if n == 0:
            break
        out += b[j + 2:j + 2 + n]
        i = j + 2 + n + 2
    return bytes(out)


def parse_warc(raw):
    """gzip member -> (WARC headers, HTTP status, HTTP headers, payload)."""
    dz = zlib.decompressobj(16 + zlib.MAX_WBITS)
    rec = dz.decompress(raw) + dz.flush()
    if not rec.startswith(b'WARC/'):
        raise ValueError('not a WARC record')
    end = rec.find(b'\r\n\r\n')
    if end < 0:
        raise ValueError('unterminated WARC header')
    wh = parse_headers(rec[:end].split(b'\r\n')[1:])
    block = rec[end + 4:]
    try:
        block = block[:int(wh.get('content-length', len(block)))]
    except ValueError:
        pass
    if wh.get('warc-type') != 'response':
        return wh, None, {}, b''
    end, sep = block.find(b'\r\n\r\n'), 4
    if end < 0:
        end, sep = block.find(b'\n\n'), 2
    if end < 0:
        raise ValueError('unterminated HTTP header')
    lines = block[:end].split(b'\n')
    m = HTTP_STATUS_RX.match(lines[0].strip())
    hh = parse_headers(ln.rstrip(b'\r') for ln in lines[1:])
    payload = block[end + sep:]
    # Common Crawl stores payloads decoded and renames the headers X-Crawler-Transfer-Encoding/-Content-Encoding;
    # undo an encoding only if the original header survived and the bytes really are encoded.
    if 'chunked' in hh.get('transfer-encoding', '').lower():
        payload = dechunk(payload)
    enc = {t.strip() for t in hh.get('content-encoding', '').lower().split(',')}
    try:
        if enc & {'gzip', 'x-gzip'} and payload[:2] == b'\x1f\x8b':
            dz = zlib.decompressobj(16 + zlib.MAX_WBITS)
            payload = dz.decompress(payload) + dz.flush()
        elif 'deflate' in enc:
            payload = zlib.decompress(payload)
        elif 'br' in enc:
            import brotli
            payload = brotli.decompress(payload)
    except Exception:
        pass
    return wh, int(m.group(1)) if m else None, hh, payload


def charset_of(hh, payload):
    m = re.search(r'charset\s*=\s*["\']?([A-Za-z0-9_.:-]+)', hh.get('content-type', ''), re.I)
    cs = m.group(1) if m else None
    if not cs:
        m = META_CHARSET_RX.search(payload[:8192])
        cs = m.group(1).decode('ascii', 'ignore') if m else 'utf-8'
    try:
        codecs.lookup(cs)
        return cs
    except LookupError:
        return 'utf-8'


def loads_jsonld(txt):
    s = COMMENT_RX.sub('', CDATA_RX.sub('', txt)).strip().rstrip(';').strip()
    if not s:
        raise ValueError('empty block')
    fixes = (lambda t: t, lambda t: t.replace("\\'", "'"), lambda t: TRAILING_COMMA_RX.sub(r'\1', t),
             html.unescape, lambda t: CTRL_RX.sub(' ', t),
             lambda t: TRAILING_COMMA_RX.sub(r'\1', CTRL_RX.sub(' ', t.replace("\\'", "'"))))
    for fix in fixes:
        try:
            return json.loads(fix(s), strict=False)
        except ValueError:
            pass
    dec, out, i = json.JSONDecoder(strict=False), [], 0     # several JSON values back to back
    while i < len(s):
        while i < len(s) and s[i] in ' \t\r\n,;':
            i += 1
        if i < len(s):
            obj, i = dec.raw_decode(s, i)
            out.append(obj)
    return out


def type_is(t, name='JobPosting'):
    if isinstance(t, str):
        return re.split(r'[/#:]', t)[-1].strip() == name
    if isinstance(t, list):
        return any(type_is(x, name) for x in t)
    return False


def walk(obj, jobs, ids, depth=0):
    """Collect JobPosting dicts (top-level object, array, @graph, nested) and the @id-identified nodes."""
    if depth > 30:
        return
    if isinstance(obj, dict):
        ref = obj.get('@id')
        if isinstance(ref, str) and any(k not in ('@id', '@type', '@context') for k in obj):
            ids.setdefault(ref, obj)
        if type_is(obj.get('@type')):
            jobs.append(obj)
        for v in obj.values():
            if isinstance(v, (dict, list)):
                walk(v, jobs, ids, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, jobs, ids, depth + 1)


def deref(v, ids, depth=0):
    """Replace {"@id": ...} references (common in @graph documents) by the node they point to."""
    if depth > 6:
        return v
    if isinstance(v, dict):
        ref = v.get('@id')
        if isinstance(ref, str) and ref in ids and set(v) <= {'@id', '@type'}:
            v = ids[ref]
        return {k: deref(x, ids, depth + 1) for k, x in v.items()}
    if isinstance(v, list):
        return [deref(x, ids, depth + 1) for x in v]
    return v


def as_text(v, sep=', ', depth=0):
    if v is None or depth > 5:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, (int, float)):
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
    if isinstance(v, dict):
        for k in ('name', '@value', 'value', 'codeValue', 'text', 'description', 'addressLocality'):
            if v.get(k) not in (None, '', [], {}):
                return as_text(v[k], sep, depth + 1)
        return None
    if isinstance(v, list):
        parts = [p for p in (as_text(x, sep, depth + 1) for x in v) if p]
        return sep.join(dict.fromkeys(parts)) if parts else None
    return str(v)


def clean_text(s):
    if s is None:
        return None
    s = html.unescape(str(s))
    if '<' in s:
        s = TAG_RX.sub(' ', s)
    return ' '.join(s.split()) or None


def clean_html(s):
    if not s:
        return None
    s = html.unescape(s)                    # descriptions are often HTML-escaped HTML
    if '<' in s:
        s = html.unescape(TAG_RX.sub(' ', BLOCK_TAG_RX.sub('\n', s)))
    s = NEWLINES_RX.sub('\n', SPACES_RX.sub(' ', s)).strip()
    return s[:DESC_MAX] or None


def num(x):
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x) if math.isfinite(x) else None
    if isinstance(x, str):
        s = re.sub(r'[\s  ]', '', x).replace(',', '.')
        return float(s) if re.fullmatch(r'[-+]?\d+(?:\.\d+)?', s) else None
    return None


def first_dict(v):
    if isinstance(v, list):
        return next((x for x in v if isinstance(x, dict)), None)
    return v if isinstance(v, dict) else None


def salary(bs, cur0):
    lo = hi = cur = unit = None
    bs = first_dict(bs) if isinstance(bs, list) else bs
    if isinstance(bs, dict):
        cur, unit = as_text(bs.get('currency')), as_text(bs.get('unitText'))
        v = bs.get('value')
        v = (v[0] if v else None) if isinstance(v, list) else v
        if isinstance(v, dict):
            lo, hi, single = num(v.get('minValue')), num(v.get('maxValue')), num(v.get('value'))
            unit = as_text(v.get('unitText')) or unit
            if lo is None and hi is None:
                lo = hi = single
        else:
            lo = hi = num(v)
        lo = lo if lo is not None else num(bs.get('minValue'))
        hi = hi if hi is not None else num(bs.get('maxValue'))
    elif bs is not None:
        lo = hi = num(bs)
    return lo, hi, clean_text(cur or as_text(cur0)), clean_text(unit)


def locations(jl):
    """All addresses of jobLocation as dicts (city/postalCode/region/country)."""
    out = []
    for loc in (jl if isinstance(jl, list) else [jl]):
        if isinstance(loc, str):
            out.append({'city': clean_text(loc)})
            continue
        if not isinstance(loc, dict):
            continue
        addr = loc.get('address', loc)
        addr = first_dict(addr) if isinstance(addr, list) else addr
        if isinstance(addr, str):
            out.append({'city': clean_text(addr)})
        elif isinstance(addr, dict):
            out.append({'city': clean_text(as_text(addr.get('addressLocality')) or as_text(loc.get('name'))),
                        'postalCode': clean_text(as_text(addr.get('postalCode'))),
                        'region': clean_text(as_text(addr.get('addressRegion'))),
                        'country': clean_text(as_text(addr.get('addressCountry')))})
    return out


def is_france(country):
    return bool(country) and country.strip().lower() in FR_COUNTRY


def ts_iso(ts):
    ts = str(ts)
    return f'{ts[0:4]}-{ts[4:6]}-{ts[6:8]}T{ts[8:10]}:{ts[10:12]}:{ts[12:14]}Z' if len(ts) >= 14 else ts


def normalise(jp, cap, crawl, i):
    """One JobPosting dict -> (flat record or None, set of countries of all its locations)."""
    title = clean_text(as_text(jp.get('title')) or as_text(jp.get('name')))
    desc = clean_html(as_text(jp.get('description'), sep='\n'))
    locs = locations(jp.get('jobLocation'))
    countries = {l.get('country') for l in locs if l.get('country')}
    req = as_text(jp.get('applicantLocationRequirements'))
    if req:
        countries.add(clean_text(req))
    if not title and not desc:
        return None, countries
    loc = next((l for l in locs if l.get('city') or l.get('country')), locs[0] if locs else {})
    lo, hi, cur, unit = salary(jp.get('baseSalary'), jp.get('salaryCurrency'))
    ident = jp.get('identifier')
    ident = (ident[0] if ident else None) if isinstance(ident, list) else ident
    if isinstance(ident, dict):
        ident = ident.get('value') if ident.get('value') not in (None, '') else ident.get('name')
    org = jp.get('hiringOrganization')
    rec = {
        'url': cap['url'], 'crawl': crawl, 'capture_time': ts_iso(cap['timestamp']), 'host': cap['host'],
        'title': title, 'description': desc,
        'datePosted': clean_text(as_text(jp.get('datePosted'))),
        'validThrough': clean_text(as_text(jp.get('validThrough'))),
        'employmentType': clean_text(as_text(jp.get('employmentType'), sep=',')),
        'employer': clean_text(as_text(first_dict(org) if isinstance(org, list) else org)),
        'city': loc.get('city'), 'postalCode': loc.get('postalCode'), 'region': loc.get('region'),
        'country': loc.get('country'),
        'salary_min': lo, 'salary_max': hi, 'salary_currency': cur, 'salary_unit': unit,
        'identifier': clean_text(as_text(ident)),
        'industry': clean_text(as_text(jp.get('industry'))),
        'occupationalCategory': clean_text(as_text(jp.get('occupationalCategory'))),
        'jp_index': i, 'warc_filename': cap['filename'], 'warc_offset': int(cap['offset']),
        'warc_length': int(cap['length']),
    }
    return rec, countries


def process_capture(cap, crawl):
    """Worker: download + parse one capture. Never raises; the status says what happened."""
    res = {'status': None, 'postings': [], 'n_found': 0, 'n_kept': 0, 'truncated': 0, 'n_ld': 0, 'n_ld_err': 0,
           'ms': 0}
    if cap.get('mime') == 'warc/revisit':
        res['status'] = 'revisit'
        return res
    t0 = time.time()
    try:
        raw = download_record(cap['filename'], int(cap['offset']), int(cap['length']))
    except PermanentHTTPError as e:
        res['status'] = f'fetch_http_{e.args[0]}'
        return res
    except Exception as e:
        res['status'], res['error'] = 'download_error', f'{type(e).__name__}: {e}'[:300]
        return res
    res['ms'], res['nbytes'] = int((time.time() - t0) * 1000), len(raw)
    try:
        wh, code, hh, payload = parse_warc(raw)
    except Exception as e:
        res['status'], res['error'] = 'warc_error', f'{type(e).__name__}: {e}'[:300]
        return res
    res['truncated'] = int('warc-truncated' in wh)
    if wh.get('warc-type') != 'response':
        res['status'] = 'not_response'
        return res
    if code != 200:
        res['status'] = f'http_{code}'
        return res
    blocks = LD_RX.findall(payload)
    res['n_ld'] = len(blocks)
    jobs, ids, lost = [], {}, 0
    for b in blocks:
        try:
            txt = b.decode('utf-8')
        except UnicodeDecodeError:
            txt = b.decode(charset_of(hh, payload), 'replace')
        try:
            walk(loads_jsonld(txt), jobs, ids)
        except Exception:                              # ValueError, RecursionError
            res['n_ld_err'] += 1
            lost += b'JobPosting' in b
    res['n_found'] = len(jobs)
    if not jobs:
        if lost:
            res['status'] = 'jsonld_error'             # a JobPosting block exists but could not be parsed
        elif MICRODATA_RX.search(payload):
            res['status'] = 'microdata_only'
        else:
            res['status'] = 'no_jobposting' if blocks else 'no_jsonld'
        return res
    for i, jp in enumerate(jobs):
        try:
            rec, countries = normalise(deref(jp, ids), cap, crawl, i)
        except Exception as e:
            res['error'] = f'normalise: {type(e).__name__}: {e}'[:300]
            continue
        if rec is None:
            continue
        if cap['host'] in FOREIGN_BOARDS and not any(is_france(c) for c in countries):
            continue
        res['postings'].append(rec)
    res['n_kept'] = len(res['postings'])
    res['status'] = 'ok' if res['postings'] else 'filtered'
    return res


# ------------------------------------------------------------------------------------------------------- fetch
def norm_url(u):
    try:
        sp = urlsplit(u.strip())
    except ValueError:
        return u.strip().lower()
    host = (sp.hostname or '').lower()
    host = host[4:] if host.startswith('www.') else host
    q = sorted((k, v) for k, v in parse_qsl(sp.query, keep_blank_values=True) if not TRACKING_RX.match(k))
    return host + (sp.path.rstrip('/') or '/') + ('?' + urlencode(q) if q else '')


def url_key(url, jp_index=0):
    return norm_url(url) + (f'#{jp_index}' if jp_index else '')


def _n(s):
    return ' '.join(str(s).lower().split()) if s is not None and s == s else ''


def id_key(host, identifier, title, employer, city):
    """(host, identifier) guarded by title/employer/city: identical for true re-captures of a posting, and a
    site-wide constant identifier can then not merge distinct postings."""
    ident = _n(identifier)
    return '\x1f'.join((host or '', ident, _n(title), _n(employer), _n(city))) if ident else None


def load_index_captures(crawl, pats):
    caps, seen = [], set()
    for p in pats:
        host = host_of(p)
        st = read_json(INDEX_DIR / crawl / f'{host}.state.json', None)
        if not st or not st.get('bytes') or st.get('pattern') != p:
            continue
        try:
            with open(INDEX_DIR / crawl / f'{host}.jsonl', 'rb') as f:
                blob = f.read(st['bytes'])              # committed pages only (index may still be running)
        except FileNotFoundError:
            continue
        for line in blob.decode('utf-8', 'replace').splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            k = (r['filename'], str(r['offset']))
            if k not in seen:
                seen.add(k)
                r['host'] = host
                caps.append(r)
    return caps


def load_done(crawl):
    done, path = set(), POST_DIR / f'{crawl}.done'
    if path.exists():
        with open(path, encoding='utf-8') as f:
            for line in f:
                p = line.split('\t', 2)
                if len(p) == 3:
                    done.add((p[0], p[1]))
    return done


def load_seen():
    """Dedupe keys of the postings already written: key -> earliest crawl holding it."""
    seen_url, seen_id = {}, {}
    for f in sorted(POST_DIR.glob('CC-MAIN-*.ndjson')):
        crawl = f.stem
        with open(f, encoding='utf-8') as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                uk = url_key(r['url'], r.get('jp_index') or 0)
                if seen_url.get(uk, '~') > crawl:
                    seen_url[uk] = crawl
                ik = id_key(r.get('host'), r.get('identifier'), r.get('title'), r.get('employer'), r.get('city'))
                if ik and seen_id.get(ik, '~') > crawl:
                    seen_id[ik] = crawl
    return seen_url, seen_id


def round_robin(caps, n):
    """Pick n captures spread evenly over hosts (for test runs with --limit)."""
    by_host = defaultdict(deque)
    for c in caps:
        by_host[c['host']].append(c)
    out = []
    while len(out) < n and by_host:
        for h in list(by_host):
            if len(out) >= n:
                break
            out.append(by_host[h].popleft())
            if not by_host[h]:
                del by_host[h]
    return sorted(out, key=lambda c: (c['timestamp'], c['url']))


def done_line(cap, status, res, n_written):
    return '\t'.join(map(str, (cap['filename'], cap['offset'], cap['host'], status, res.get('n_found', 0),
                               res.get('n_kept', 0), n_written, res.get('truncated', 0), res.get('n_ld', 0),
                               res.get('n_ld_err', 0), res.get('ms', 0)))) + '\n'


DOWNLOADED = lambda s: s not in ('skip_seen_url', 'revisit')


def summarise_done(crawl):
    per_host = defaultdict(Counter)
    path = POST_DIR / f'{crawl}.done'
    if path.exists():
        with open(path, encoding='utf-8') as f:
            for line in f:
                p = line.rstrip('\n').split('\t')
                if len(p) < 11:
                    continue
                host, status = p[2], p[3]
                n_found, n_kept, n_written, trunc, n_ld, n_ld_err, ms = map(int, p[4:11])
                c = per_host[host]
                c['processed'] += 1
                c['downloaded'] += DOWNLOADED(status)
                c['with_jobposting'] += n_found > 0
                c['postings_found'] += n_found
                c['postings_kept'] += n_kept
                c['postings_written'] += n_written
                c['truncated'] += trunc
                c['jsonld_blocks'] += n_ld
                c['jsonld_block_errors'] += n_ld_err
                c['download_ms'] += ms
                c[f'status_{status}'] += 1
    return {h: dict(sorted(c.items())) for h, c in sorted(per_host.items())}


def run_crawl(crawl, todo, seen_url, seen_id, workers, run):
    out_path, done_path = POST_DIR / f'{crawl}.ndjson', POST_DIR / f'{crawl}.done'
    for p in (out_path, done_path):
        repair_tail(p)
    t0 = last_log = time.time()
    n = 0
    with open(out_path, 'a', encoding='utf-8', newline='\n') as out, \
            open(done_path, 'a', encoding='utf-8', newline='\n') as donef, \
            open(POST_DIR / f'{crawl}.errors.log', 'a', encoding='utf-8', newline='\n') as errf, \
            ThreadPoolExecutor(workers) as ex:
        window, it = deque(), iter(todo)

        def feed():
            for cap in it:
                if seen_url.get(url_key(cap['url']), '~') <= crawl:     # already harvested from an earlier capture
                    donef.write(done_line(cap, 'skip_seen_url', {}, 0))
                    for c in (run['all'], run['host:' + cap['host']]):
                        c['processed'] += 1
                        c['status_skip_seen_url'] += 1
                    continue
                window.append((cap, ex.submit(process_capture, cap, crawl)))
                return True
            return False

        for _ in range(workers * 4):
            if not feed():
                break
        while window:
            cap, fut = window.popleft()                  # results consumed in timestamp order -> earliest kept
            res = fut.result()
            status, n_written = res['status'], 0
            for c in (run['all'], run['host:' + cap['host']]):
                c['processed'] += 1
            if status == 'download_error':               # not marked done: retried by the next run
                errf.write(f'{now_iso()}\t{cap["filename"]}\t{cap["offset"]}\t{res.get("error")}\n')
                errf.flush()
            else:
                for rec in res['postings']:
                    uk = url_key(rec['url'], rec['jp_index'])
                    ik = id_key(rec['host'], rec['identifier'], rec['title'], rec['employer'], rec['city'])
                    if seen_url.get(uk, '~') <= crawl or (ik and seen_id.get(ik, '~') <= crawl):
                        continue
                    out.write(json.dumps(rec, ensure_ascii=False) + '\n')
                    n_written += 1
                    seen_url[uk] = crawl
                    if ik:
                        seen_id[ik] = crawl
                if n_written:
                    out.flush()                          # postings reach the OS before the done line
                if status == 'ok' and not n_written:
                    status = 'dup'
                donef.write(done_line(cap, status, res, n_written))
            if res.get('error') and status != 'download_error':
                errf.write(f'{now_iso()}\t{cap["filename"]}\t{cap["offset"]}\t{status}\t{res["error"]}\n')
            for c in (run['all'], run['host:' + cap['host']]):
                c[f'status_{status}'] += 1
                c['downloaded'] += DOWNLOADED(status) and status != 'download_error'
                c['with_jobposting'] += res['n_found'] > 0
                c['postings_found'] += res['n_found']
                c['postings_kept'] += res['n_kept']
                c['postings_written'] += n_written
                c['truncated'] += res['truncated']
                c['jsonld_blocks'] += res['n_ld']
                c['jsonld_block_errors'] += res['n_ld_err']
                c['bytes'] += res.get('nbytes', 0)
            n += 1
            if n % 200 == 0 or time.time() - last_log > 60:
                donef.flush()
                el, a = time.time() - t0, run['all']
                log(f'  {crawl}: {n}/{len(todo)} captures, {a["with_jobposting"]} with JobPosting, '
                    f'{a["postings_written"]} postings written, {100 * el / max(n, 1):.1f}s per 100 records')
                last_log = time.time()
            feed()
    return time.time() - t0


def cmd_fetch(args):
    POST_DIR.mkdir(parents=True, exist_ok=True)
    lock = acquire_lock(POST_DIR / '.lock')
    pats = select_patterns(args.hosts)
    crawls = sorted(d.name for d in INDEX_DIR.glob('CC-MAIN-*') if d.is_dir())
    if args.crawls:
        crawls = [c for c in crawls if c in set(args.crawls)]
    log(f'fetch: pid {os.getpid()}, {len(crawls)} indexed crawls, {len(pats)} patterns, {args.workers} parallel '
        f'downloads' + (f', limit {args.limit} captures' if args.limit else ''))
    seen_url, seen_id = load_seen()
    log(f'  {len(seen_url)} postings already harvested')
    budget = args.limit
    run = defaultdict(Counter)
    t_start, t_work = time.time(), 0.0
    for crawl in crawls:                                  # chronological: the earliest capture of a posting wins
        if budget is not None and budget <= 0:
            break
        caps = load_index_captures(crawl, pats)
        done = load_done(crawl)
        todo = sorted((c for c in caps if (c['filename'], str(c['offset'])) not in done),
                      key=lambda c: (c['timestamp'], c['url']))
        n_pending = len(todo)
        if budget is not None:
            todo = round_robin(todo, budget)
            budget -= len(todo)
        log(f'{crawl}: {len(caps)} captures indexed, {len(caps) - n_pending} already processed, '
            f'{len(todo)} to process now')
        if todo:
            t_work += run_crawl(crawl, todo, seen_url, seen_id, args.workers, run)
            write_json(POST_DIR / f'{crawl}.summary.json', summarise_done(crawl))
            write_manifest()
    write_manifest()
    a = run['all']
    dl = a['downloaded']
    pct = lambda k, base=None: f'{a[k]} ({100 * a[k] / max(base if base is not None else dl, 1):.1f}%)'
    log(f'fetch finished in {time.time() - t_start:.0f}s')
    print(f'  captures processed       {a["processed"]}  (skipped, URL already harvested: {a["status_skip_seen_url"]}; '
          f'download failures, retried next run: {a["status_download_error"]})')
    print(f'  WARC records downloaded  {dl}')
    print(f'  with a JobPosting        {pct("with_jobposting")}')
    print(f'  postings found/kept/written  {a["postings_found"]} / {a["postings_kept"]} / {a["postings_written"]}'
          f'  (dup records {a["status_dup"]}, filtered non-FR {a["status_filtered"]})')
    fails = a['status_jsonld_error'] + a['status_warc_error']
    print(f'  parse failures           {fails} ({100 * fails / max(dl, 1):.1f}% of records: JSON-LD JobPosting '
          f'unparseable {a["status_jsonld_error"]}, WARC/gzip {a["status_warc_error"]}); JSON-LD blocks '
          f'{a["jsonld_blocks"]}, unparseable {a["jsonld_block_errors"]}')
    print(f'  no JobPosting            no JSON-LD {a["status_no_jsonld"]}, JSON-LD without JobPosting '
          f'{a["status_no_jobposting"]}, microdata only {a["status_microdata_only"]}, truncated payloads {a["truncated"]}')
    if dl:
        print(f'  time per 100 records     {100 * t_work / dl:.1f}s wall clock ({args.workers} parallel downloads, '
              f'{a["bytes"] / 1e6:.1f} MB downloaded)')
    print('  statuses: ' + ', '.join(f'{k[7:]} {v}' for k, v in sorted(a.items()) if k.startswith('status_') and v))
    for key in sorted(k for k in run if k.startswith('host:')):
        h = run[key]
        print(f'  {key[5:]:<34} processed {h["processed"]:>6}  with JobPosting {h["with_jobposting"]:>6}  '
              f'written {h["postings_written"]:>6}')
    lock.close()


# ------------------------------------------------------------------------------------------------------- build
def cmd_build(args):
    import pandas as pd
    recs, bad = [], 0
    for f in sorted(POST_DIR.glob('CC-MAIN-*.ndjson')):
        with open(f, encoding='utf-8') as fh:
            for line in fh:
                try:
                    recs.append(json.loads(line))
                except ValueError:
                    bad += 1
    if not recs:
        sys.exit('no postings yet: run fetch first')
    recs.sort(key=lambda r: (r.get('capture_time') or '', r.get('crawl') or '', r.get('jp_index') or 0))
    seen_u, seen_i, keep = set(), set(), []
    for r in recs:                                      # earliest capture first
        uk = url_key(r['url'], r.get('jp_index') or 0)
        ik = id_key(r.get('host'), r.get('identifier'), r.get('title'), r.get('employer'), r.get('city'))
        if uk in seen_u or (ik and ik in seen_i):
            continue
        seen_u.add(uk)
        if ik:
            seen_i.add(ik)
        keep.append(r)
    df = pd.DataFrame.from_records(keep, columns=COLUMNS).drop_duplicates()
    LAKE_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(LAKE_FILE, index=False)
    year = df['datePosted'].astype('string').str.extract(r'((?:19|20)\d{2})', expand=False).fillna('n/a')
    log(f'build: {len(recs)} NDJSON records ({bad} unreadable lines) -> {len(df)} unique postings -> {LAKE_FILE}')
    print('postings per host:')
    print(df['host'].value_counts().to_string())
    print('postings per year of datePosted:')
    print(year.value_counts().sort_index().to_string())
    print('host x year of datePosted:')
    print(pd.crosstab(df['host'], year).to_string())
    write_manifest(build={'generated': now_iso(), 'file': str(LAKE_FILE.relative_to(ROOT)).replace('\\', '/'),
                          'rows': int(len(df)), 'ndjson_records': len(recs),
                          'per_host': {k: int(v) for k, v in df['host'].value_counts().items()},
                          'per_year_datePosted': {k: int(v) for k, v in year.value_counts().sort_index().items()}})


# ---------------------------------------------------------------------------------------------------- manifest
def write_manifest(build=None):
    idx = defaultdict(dict)
    for sf in sorted(INDEX_DIR.glob('CC-MAIN-*/*.state.json')):
        st = read_json(sf, None)
        if st:
            pages = st.get('pages', {})
            idx[sf.parent.name][st.get('host') or sf.name[:-11]] = {
                'pattern': st.get('pattern'), 'pages': st.get('num_pages'), 'pages_done': len(pages),
                'captures': sum(p.get('captures', 0) for p in pages.values()), 'complete': bool(st.get('complete'))}
    fetch = {f.name[:-13]: read_json(f, {}) for f in sorted(POST_DIR.glob('CC-MAIN-*.summary.json'))}
    hosts = defaultdict(Counter)
    for d in idx.values():
        for h, v in d.items():
            hosts[h]['index_captures'] += v['captures']
            hosts[h]['crawls_indexed'] += v['complete']
    for d in fetch.values():
        for h, v in d.items():
            for k in ('processed', 'downloaded', 'with_jobposting', 'postings_written'):
                hosts[h][k] += v.get(k, 0)
    old = read_json(MANIFEST, {}) or {}
    write_json(MANIFEST, {
        'generated': now_iso(),
        'source': 'Common Crawl: index.commoncrawl.org CDX API + data.commoncrawl.org WARC range requests '
                  '(job boards never contacted)',
        'script': 'pipeline/harvest_cc_jobs.py', 'patterns': PATTERNS,
        'totals_per_host': {h: dict(c) for h, c in sorted(hosts.items())},
        'index': dict(sorted(idx.items())), 'fetch': fetch,
        'build': build if build is not None else old.get('build'),
    })


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('index', help='query the CDX index and save the captures (resumable)')
    a.add_argument('--crawls', nargs='+', help='crawl ids (default: every CC-MAIN crawl from --first to --last)')
    a.add_argument('--first', default=FIRST_CRAWL)
    a.add_argument('--last', default=LAST_CRAWL)
    a.add_argument('--hosts', nargs='+', help='keep the patterns containing one of these strings')
    a.add_argument('--order', choices=('newest', 'oldest'), default='newest', help='crawl processing order')
    f = sub.add_parser('fetch', help='download the WARC records and extract the JobPostings (resumable)')
    f.add_argument('--crawls', nargs='+')
    f.add_argument('--hosts', nargs='+')
    f.add_argument('--limit', type=int, help='process at most N new captures in this run (spread over hosts)')
    f.add_argument('--workers', type=int, default=8, help='parallel downloads (default 8)')
    sub.add_parser('build', help='NDJSON -> data-lake/lake/cc_jobs_fr.parquet')
    args = ap.parse_args()
    {'index': cmd_index, 'fetch': cmd_fetch, 'build': cmd_build}[args.cmd](args)


if __name__ == '__main__':
    main()
