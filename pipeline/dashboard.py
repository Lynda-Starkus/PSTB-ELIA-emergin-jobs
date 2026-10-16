# -*- coding: utf-8 -*-
"""Supervision dashboard generator. Reads dashboard/status.json, embeds the latest figures and key numbers,
writes dashboard/index.html (self-contained, publishable as a Claude artifact)."""
import sys, os, json, base64, glob, datetime, html
root = sys.argv[1]
dash = os.path.join(root, 'dashboard'); os.makedirs(dash, exist_ok=True)
status = json.load(open(os.path.join(dash, 'status.json'), encoding='utf-8'))
summary_path = os.path.join(root, 'data-lake', 'lake', 'summary.json')
summary = json.load(open(summary_path, encoding='utf-8')) if os.path.exists(summary_path) else {}
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

def b64img(p, max_bytes=900_000):
    if os.path.getsize(p) > max_bytes: return None
    return 'data:image/png;base64,' + base64.b64encode(open(p, 'rb').read()).decode()

figs = []
for p in sorted(glob.glob(os.path.join(root, 'research-paper', 'fig', '*.png')) + glob.glob(os.path.join(root, 'dashboard', 'fig', '*.png')), key=os.path.getmtime, reverse=True)[:24]:
    d = b64img(p)
    if d: figs.append((os.path.basename(p), d, datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime('%d/%m %H:%M')))

def bar(pct, state):
    cls = {'done': 'ok', 'running': 'run', 'blocked': 'bad', 'todo': 'todo'}.get(state, 'todo')
    return f'<div class="bar"><div class="fill {cls}" style="width:{pct}%"></div></div>'

phases = status.get('phases', [])
overall = round(sum(p.get('progress', 0) * p.get('weight', 1) for p in phases) / max(1, sum(p.get('weight', 1) for p in phases)))
rows = []
for p in phases:
    tasks = ''.join(f'<li class="t {t.get("state","todo")}"><span class="dot"></span><span class="tn">{html.escape(t["name"])}</span><span class="ts">{html.escape(t.get("note",""))}</span></li>' for t in p.get('tasks', []))
    rows.append(f'<section class="phase"><header><h3>{html.escape(p["name"])}</h3><span class="pct">{p.get("progress",0)}%</span></header>{bar(p.get("progress",0), p.get("state","todo"))}<ul class="tasks">{tasks}</ul></section>')

kpis = ''.join(f'<div class="kpi"><div class="v">{html.escape(str(v))}</div><div class="l">{html.escape(k)}</div></div>' for k, v in summary.get('kpis', {}).items())
notes = ''.join(f'<li><time>{html.escape(n.get("t",""))}</time> {html.escape(n.get("msg",""))}</li>' for n in status.get('log', [])[-25:][::-1])
figshtml = ''.join(f'<figure><img src="{d}" alt="{html.escape(n)}" loading="lazy"><figcaption>{html.escape(n)} <span>{t}</span></figcaption></figure>' for n, d, t in figs)
inputs = ''.join(f'<li class="{i.get("state","open")}">{html.escape(i["q"])}<em>{html.escape(i.get("a",""))}</em></li>' for i in status.get('inputs', []))

page = f'''<title>ELIA Mission Control</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;800&family=Spline+Sans+Mono:wght@400;600&display=swap">
<style>
/* layout: a control-room page; summary strip first, then phases with progress, then latest figures and the log */
:root{{--bg:#fcfcfe;--fg:#0f0f1a;--mut:#5b6174;--line:#e5e7eb;--card:#ffffff;--vio:#6520ff;--vio-soft:#f3edff;--rose:#ff1845;--ok:#009B72;--warn:#E08600;--bad:#E00023;--todo:#c9cdd8;--display:"Archivo",system-ui,sans-serif;--mono:"Spline Sans Mono",ui-monospace,monospace}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#131318;--fg:#f2f2f7;--mut:#a3a8ba;--line:#2a2d3a;--card:#1b1c24;--vio:#8d6aff;--vio-soft:#262042;--rose:#f43b5c;--ok:#2dd4a0;--warn:#f4b544;--bad:#ff6b7a;--todo:#3a3e4e;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#131318;--fg:#f2f2f7;--mut:#a3a8ba;--line:#2a2d3a;--card:#1b1c24;--vio:#8d6aff;--vio-soft:#262042;--rose:#f43b5c;--ok:#2dd4a0;--warn:#f4b544;--bad:#ff6b7a;--todo:#3a3e4e;color-scheme:dark}}
body{{background:var(--bg);color:var(--fg);font-family:var(--display);padding-inline:max(16px,env(safe-area-inset-left,0px)) max(16px,env(safe-area-inset-right,0px));padding-block:20px 48px;margin:0}}
.wrap{{max-width:1180px;margin:0 auto;display:grid;gap:22px}}
header.top{{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px 18px;border-bottom:1px solid var(--line);padding-bottom:12px}}
.brand{{font-family:var(--mono);letter-spacing:.14em;font-weight:600;color:var(--vio);background:var(--vio-soft);padding:3px 9px;border-radius:999px;font-size:12px}}
h1{{font-size:clamp(22px,3vw,30px);margin:0;font-weight:800;text-wrap:balance}} .upd{{color:var(--mut);font-family:var(--mono);font-size:12px;margin-left:auto}}
.overall{{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
.overall .big{{font-family:var(--mono);font-size:30px;font-weight:600;color:var(--vio)}}
.bar{{height:10px;background:var(--todo);border-radius:999px;overflow:hidden}} .fill{{height:100%;border-radius:999px;background:var(--vio)}} .fill.ok{{background:var(--ok)}} .fill.bad{{background:var(--bad)}} .fill.run{{background:linear-gradient(90deg,var(--vio),var(--rose))}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}} .kpi{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}} .kpi .v{{font-family:var(--mono);font-size:22px;font-weight:600;font-variant-numeric:tabular-nums}} .kpi .l{{color:var(--mut);font-size:12px;margin-top:2px}}
.phases{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
.phase{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;min-width:0}} .phase header{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}} .phase h3{{margin:0;font-size:15px}} .pct{{font-family:var(--mono);color:var(--mut)}}
.tasks{{list-style:none;padding:0;margin:10px 0 0;display:grid;gap:5px}} .t{{display:grid;grid-template-columns:12px 1fr;gap:8px;font-size:13px;align-items:start}} .t .ts{{grid-column:2;color:var(--mut);font-size:12px}} .dot{{width:9px;height:9px;border-radius:50%;background:var(--todo);margin-top:5px}} .t.done .dot{{background:var(--ok)}} .t.running .dot{{background:var(--vio);box-shadow:0 0 0 3px var(--vio-soft)}} .t.blocked .dot{{background:var(--bad)}}
h2{{font-size:17px;margin:4px 0 0}} .figs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}} figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px;min-width:0}} figure img{{width:100%;height:auto;border-radius:6px;background:#fff}} figcaption{{font-family:var(--mono);font-size:11px;color:var(--mut);margin-top:6px;word-break:break-all}} figcaption span{{float:right}}
.log{{list-style:none;padding:0;margin:0;display:grid;gap:4px;font-size:13px}} .log time{{font-family:var(--mono);color:var(--mut);margin-right:8px;font-size:12px}}
.inputs{{list-style:none;padding:0;margin:0;display:grid;gap:6px;font-size:13px}} .inputs li{{padding:8px 10px;border-left:3px solid var(--warn);background:var(--card);border-radius:0 8px 8px 0}} .inputs li.answered{{border-left-color:var(--ok)}} .inputs em{{display:block;color:var(--mut);font-style:normal;margin-top:2px}}
@media (prefers-reduced-motion:no-preference){{.t.running .dot{{animation:pulse 1.6s infinite}} @keyframes pulse{{50%{{opacity:.45}}}}}}
</style>
<div class="wrap">
<header class="top"><span class="brand">ELIA · PST&amp;B</span><h1>Mission Control · métiers IA émergents</h1><span class="upd">mis à jour {now}</span></header>
<div class="overall"><div><div style="display:flex;justify-content:space-between;font-size:13px;color:var(--mut);margin-bottom:6px"><span>Avancement global du projet</span><span>{html.escape(status.get("headline",""))}</span></div>{bar(overall,"running")}</div><div class="big">{overall}%</div></div>
<div class="kpis">{kpis}</div>
<div class="phases">{''.join(rows)}</div>
<h2>Entrées attendues de Linda</h2><ul class="inputs">{inputs}</ul>
<h2>Dernières figures</h2><div class="figs">{figshtml or "<p style='color:var(--mut)'>Aucune figure encore produite.</p>"}</div>
<h2>Journal</h2><ul class="log">{notes}</ul>
</div>'''
open(os.path.join(dash, 'index.html'), 'w', encoding='utf-8').write(page)
print('dashboard written', os.path.join(dash, 'index.html'), 'overall', overall, '% figs', len(figs))
