# -*- coding: utf-8 -*-
"""Web Data Commons, schema.org JobPosting class-specific subset (October 2024 Common Crawl) -> French postings.
Input : data-lake/raw/wdc_jobposting/part_*.gz  (N-Quads: <subject> <predicate> object <graph=page url> .)
Output: data-lake/raw/wdc_jobposting/fr_postings.ndjson + data-lake/lake/wdc_fr_2024.parquet
Keep a posting when its jobLocation country is France, or the page host ends with .fr, or its text carries a French language tag.
Licence of the source: Web Data Commons extraction of Common Crawl, free for research; cite Brinkmann et al. (2023)."""
import sys, os, re, gzip, json, glob, html
from urllib.parse import urlsplit
from multiprocessing import Pool
import pandas as pd
root = sys.argv[1]; raw = os.path.join(root, 'data-lake', 'raw', 'wdc_jobposting'); lake = os.path.join(root, 'data-lake', 'lake')
Q = re.compile(r'^(<[^>]*>|_:\S+) <([^>]*)> (.*) (<[^>]*>)\s*\.\s*$')
LIT = re.compile(r'^"(.*)"(?:@([A-Za-z-]+)|\^\^<[^>]*>)?$', re.S)
P = lambda u: u.rsplit('/', 1)[-1].rsplit('#', 1)[-1]      # predicate local name (schema.org/… or schema.org#…)
FR_COUNTRY = {'fr', 'france', 'fra', 'french', 'république française'}
WANT = {'title', 'description', 'datePosted', 'validThrough', 'employmentType', 'hiringOrganization', 'jobLocation', 'baseSalary', 'identifier', 'industry', 'occupationalCategory', 'skills', 'qualifications', 'experienceRequirements', 'educationRequirements', 'jobLocationType', 'url', 'directApply', 'addressLocality', 'addressRegion', 'postalCode', 'addressCountry', 'name', 'value', 'minValue', 'maxValue', 'currency', 'unitText', 'address', 'legalName', 'sameAs', 'streetAddress'}

def unescape(s):
    return s.encode('utf-8', 'surrogatepass').decode('unicode_escape', 'ignore').encode('latin-1', 'ignore').decode('utf-8', 'ignore') if '\\' in s else s

def parse_obj(o):
    if o.startswith('<'): return ('iri', o[1:-1], None)
    if o.startswith('_:'): return ('bnode', o, None)
    m = LIT.match(o)
    if not m: return ('lit', o, None)
    return ('lit', unescape(m.group(1)), m.group(2))

def val(node, key, nodes, depth=0):
    """Resolve a property: literal, or nested node's name/value (hiringOrganization.name, jobLocation.address.addressLocality ...)."""
    v = node.get(key)
    if v is None: return None
    kind, x, lang = v
    if kind == 'lit': return x
    if kind in ('bnode', 'iri') and x in nodes and depth < 3:
        n = nodes[x]
        for k in ('name', 'value', 'addressLocality', 'legalName'):
            r = val(n, k, nodes, depth + 1)
            if r: return r
    return x if kind == 'iri' else None

def flush(graph, nodes, out):
    """Emit one record per JobPosting entity in the page graph if it is French."""
    graph = graph.strip('<>'); host = urlsplit(graph).hostname or ''
    for sid, node in nodes.items():
        if node.get('__type') != 'JobPosting': continue
        loc = node.get('jobLocation'); addr = None; country = city = postal = region = None
        if loc and loc[1] in nodes:
            ln = nodes[loc[1]]; a = ln.get('address'); addr = nodes.get(a[1]) if a and a[1] in nodes else ln
            country = val(addr, 'addressCountry', nodes); city = val(addr, 'addressLocality', nodes); postal = val(addr, 'postalCode', nodes); region = val(addr, 'addressRegion', nodes)
        langs = {node[k][2] for k in ('title', 'description') if k in node and node[k][2]}
        is_fr = (country or '').strip().lower() in FR_COUNTRY or host.endswith('.fr') or any(l.lower().startswith('fr') for l in langs)
        if not is_fr and not os.environ.get('WDC_ALL'): continue
        sal = node.get('baseSalary'); sal_min = sal_max = sal_cur = None
        if sal and sal[1] in nodes:
            sn = nodes[sal[1]]; vv = sn.get('value'); vn = nodes.get(vv[1]) if vv and vv[1] in nodes else sn
            sal_min = val(vn, 'minValue', nodes) or val(vn, 'value', nodes); sal_max = val(vn, 'maxValue', nodes); sal_cur = val(sn, 'currency', nodes)
        rec = {'url': graph, 'host': host, 'title': val(node, 'title', nodes), 'description': html.unescape(re.sub(r'<[^>]+>', ' ', val(node, 'description', nodes) or ''))[:6000],
               'datePosted': val(node, 'datePosted', nodes), 'validThrough': val(node, 'validThrough', nodes), 'employmentType': val(node, 'employmentType', nodes),
               'employer': val(node, 'hiringOrganization', nodes), 'city': (city or '').strip() or None, 'postalCode': (postal or '').strip() or None, 'region': (region or '').strip() or None, 'country': (country or '').strip() or None,
               'salary_min': sal_min, 'salary_max': sal_max, 'salary_currency': sal_cur, 'industry': val(node, 'industry', nodes), 'occupationalCategory': val(node, 'occupationalCategory', nodes),
               'identifier': val(node, 'identifier', nodes), 'lang': ','.join(sorted(langs)) or None}
        if rec['title'] or rec['description']: out.write(json.dumps(rec, ensure_ascii=False) + '\n')

def work(path):
    outp = path + '.fr.ndjson'; n_lines = n_pages = 0
    with gzip.open(path, 'rt', encoding='utf-8', errors='ignore') as f, open(outp, 'w', encoding='utf-8') as out:
        graph = None; nodes = {}
        for line in f:
            n_lines += 1
            m = Q.match(line.rstrip('\n'))
            if not m: continue
            s, p, o, g = m.groups()
            if g != graph:
                if graph is not None: flush(graph, nodes, out); n_pages += 1
                graph, nodes = g, {}
            node = nodes.setdefault(s, {})
            if p.endswith('#type'):
                t = o[1:-1].rsplit('/', 1)[-1]
                if t == 'JobPosting' or '__type' not in node: node['__type'] = t
                continue
            key = P(p)
            if key in WANT and key not in node: node[key] = parse_obj(o)
        if graph is not None: flush(graph, nodes, out); n_pages += 1
    return path, n_lines, n_pages, sum(1 for _ in open(outp, encoding='utf-8'))

if __name__ == '__main__':
    files = sorted(glob.glob(os.path.join(raw, 'part_*.gz')))
    with Pool(min(14, len(files))) as pool: res = pool.map(work, files)
    tot = 0
    with open(os.path.join(raw, 'fr_postings.ndjson'), 'w', encoding='utf-8') as out:
        for path, nl, npg, nfr in res:
            print(os.path.basename(path), 'lines', nl, 'pages', npg, 'french postings', nfr); tot += nfr
            for line in open(path + '.fr.ndjson', encoding='utf-8'): out.write(line)
    df = pd.read_json(os.path.join(raw, 'fr_postings.ndjson'), lines=True)
    df = df.drop_duplicates(subset=['url', 'title']); df.to_parquet(os.path.join(lake, 'wdc_fr_2024.parquet'), index=False)
    print('TOTAL french postings', tot, '-> unique', len(df)); print(df.host.value_counts().head(25).to_string())
    json.dump({'source': 'Web Data Commons schema.org JobPosting subset, October 2024 Common Crawl', 'files': len(files), 'french_postings': int(len(df)), 'hosts': int(df.host.nunique()), 'date_min': str(df.datePosted.min()), 'date_max': str(df.datePosted.max())}, open(os.path.join(raw, 'manifest.json'), 'w'), indent=1)
