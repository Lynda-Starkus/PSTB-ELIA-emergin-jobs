# -*- coding: utf-8 -*-
"""Figure 1 - study design, drawn from the data (no boxes with text).
a  sources and their monthly volumes on one time axis (2011-2026)
b  nested scopes of the French corpus, log scale, with the rule that defines each scope
c  how the Emergence Index reads a real monthly series (forward deployed engineer)
d  lifecycle stages and transition rules, with the current number of titles in each stage
"""
import sys, os, json, numpy as np, pandas as pd, matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Circle, Rectangle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figstyle as F
F.setup(); root = sys.argv[1]; res = os.path.join(root, 'data-lake', 'lake', 'results'); lake = os.path.join(root, 'data-lake', 'lake'); out = os.path.join(root, 'research-paper', 'fig')
MD = lambda m: pd.Timestamp(m + '-01')

# ---------------- data ----------------
hm = pd.read_csv(os.path.join(res, 'hn_monthly.csv'), index_col=0); hm = hm[hm.index <= '2026-09']
cm = pd.read_csv(os.path.join(res, 'csp_monthly.csv'), index_col=0); cm = cm[(cm.index >= '2022-01') & (cm.index <= '2026-09')]
fm = pd.read_csv(os.path.join(res, 'ft_monthly.csv'), index_col=0)
S = json.load(open(os.path.join(lake, 'summary.json'), encoding='utf-8'))['kpis']
N_FT = int(S['Offres France Travail (texte intégral, 2026)'].replace(' ', '')); N_TECH = int(S['dont tech (ROME M18 + lexique)'].replace(' ', ''))
N_AI = int(S['dont mention IA'].replace(' ', '')); N_CORE = int(S['dont IA dans l’intitulé'].replace(' ', ''))
N_CSP = int(S['Offres secteur public CSP 2022–2026'].replace(' ', '')); N_HN = int(hm.n.sum()); N_ADZ = 11895
em = pd.read_csv(os.path.join(res, 'emergence_index.csv'))
hn = pd.read_parquet(os.path.join(lake, 'hn_classified.parquet'), columns=['month', 'canon', 'text'])
fde = hn[hn.canon == 'forward_deployed_engineer'].copy(); fde['company'] = fde.text.str.split(r'\s\|\s', regex=True).str[0].str.strip().str.lower()
months = [m for m in sorted(hn.month.unique()) if m <= '2026-09']
mc = fde.groupby('month').size().reindex(months, fill_value=0)
last12, prev12 = months[-12:], months[-24:-12]
n12, nprev = int(mc[last12].sum()), int(mc[prev12].sum())
G = np.log((n12 + 1) / (nprev + 1)) * n12 / (n12 + 10)
P = float((mc[last12] > 0).mean())
emp12 = fde[fde.month.isin(last12)].company.nunique()
row = em[em.canon == 'forward_deployed_engineer'].iloc[0]

# ---------------- canvas (mm) ----------------
FW, FH = 183, 122
fig = plt.figure(figsize=(FW * F.MM, FH * F.MM))
ax_a = F.axes_mm(fig, 40, 76, 78, 38, FW, FH)
ax_b = F.axes_mm(fig, 134, 78, 45, 36, FW, FH)
ax_c = F.axes_mm(fig, 40, 14, 60, 44, FW, FH)
ax_d = F.axes_mm(fig, 133, 10, 48, 50, FW, FH)

# ---------------- a: sources on one time axis ----------------
ax = ax_a
rows = [('Hacker News', 'international, full text', hm.n, F.SLATE, f'{F.thousands(N_HN)} posts'),
        ('Choisir le Service Public', 'French public sector, titles', cm.n, F.GREY2, f'{F.thousands(N_CSP)} postings'),
        ('France Travail', 'France, full text', fm.n, F.VIOLET, f'{F.thousands(N_FT)} offers'),
        ('Adzuna', 'France, IT category', None, F.GREY2, f'{F.thousands(N_ADZ)} live ads')]
x0, x1 = MD('2011-01'), MD('2027-01'); band = 0.8
for i, (name, sub, ser, col, note) in enumerate(rows):
    y = len(rows) - 1 - i
    ax.plot([x0, x1], [y, y], color=F.HAIR, lw=0.5, zorder=1)
    if ser is not None:
        xs = [MD(m) for m in ser.index]; v = ser.values / ser.values.max() * band
        ax.fill_between(xs, y, y + v, color=col, alpha=0.9 if col == F.VIOLET else 0.7, lw=0, zorder=2)
    else:
        ax.vlines(MD('2026-10'), y, y + band * 0.5, color=col, lw=1.4, zorder=2)
    ax.text(MD('2010-09'), y + 0.52, name, fontsize=6.5, color=F.INK, ha='right', va='center', clip_on=False)
    ax.text(MD('2010-09'), y + 0.27, sub, fontsize=5.5, color=F.MUTED, ha='right', va='center', clip_on=False)
    ax.text(MD('2010-09'), y + 0.04, note, fontsize=5.5, color=F.MUTED, ha='right', va='center', clip_on=False)
ax.axvline(MD('2022-11'), color=F.MUTED, lw=0.5, ls=(0, (1.5, 2)), zorder=0); ax.text(MD('2022-12'), len(rows) - 0.08, 'ChatGPT', fontsize=6, color=F.MUTED, va='top')
ax.set_xlim(x0, x1); ax.set_ylim(-0.05, len(rows) - 0.05); ax.set_yticks([]); F.clean(ax, left=False)
ax.set_xticks([MD(f'{y}-01') for y in range(2011, 2027, 3)]); ax.set_xticklabels([str(y) for y in range(2011, 2027, 3)])
ax.text(x0, -0.55, 'Monthly volume, scaled within each source', fontsize=5.5, color=F.MUTED, ha='left', va='top', clip_on=False)

# ---------------- b: nested scopes (log scale) ----------------
ax = ax_b
scopes = [('All postings', N_FT, F.GREY, None, ''), ('Technology jobs', N_TECH, F.SLATE, N_FT, 'IT or data ROME code, or a technology title'),
          ('AI-related', N_AI, F.VIOLET, N_TECH, 'an AI term anywhere in the text'), ('AI-titled', N_CORE, F.ROSE, N_AI, 'an AI term in the job title')]
step = 1.45
for i, (name, n, col, base, rule) in enumerate(scopes):
    y = (len(scopes) - 1 - i) * step
    ax.barh(y, np.log10(n), height=0.34, color=col, zorder=2)
    ax.text(np.log10(n) + 0.08, y, F.thousands(n), fontsize=6.5, va='center', ha='left', color=F.INK, fontweight='bold')
    head = name if base is None else f'{name}  ·  {100 * n / base:.1f} % of ' + {1: 'all postings', 2: 'technology jobs', 3: 'AI-related'}[i]
    ax.text(0, y + 0.31, head, fontsize=6.3, va='bottom', ha='left', color=F.INK)
    if rule: ax.text(0, y - 0.29, rule, fontsize=5.5, va='top', ha='left', color=F.MUTED)
ax.set_xlim(0, 7.2); ax.set_ylim(-0.75, (len(scopes) - 1) * step + 0.75); ax.set_yticks([]); F.clean(ax, left=False)
ax.set_xticks([3, 4, 5, 6]); ax.set_xticklabels(['10³', '10⁴', '10⁵', '10⁶']); ax.set_xlabel('France Travail offers, 2026 (log scale)', labelpad=2)

# ---------------- c: the index on a real series ----------------
ax = ax_c
start = '2018-01'; ms = [m for m in months if m >= start]; xs = [MD(m) for m in ms]; vals = mc[ms].values
colors = [F.VIOLET if m in last12 else F.SLATE if m in prev12 else F.GREY2 for m in ms]
ax.bar(xs, vals, width=20, color=colors, lw=0, zorder=3)
top = vals.max() * 1.75
ax.axvspan(MD(prev12[0]), MD(last12[0]), color=F.SLATE, alpha=0.07, lw=0, zorder=0)
ax.axvspan(MD(last12[0]), MD(last12[-1]) + pd.offsets.MonthEnd(0), color=F.VIOLET, alpha=0.08, lw=0, zorder=0)
ax.text(MD(prev12[0]) - pd.Timedelta(days=20), top * 0.98, f'previous 12 months\n{nprev} posts', fontsize=5.8, color=F.SLATE, va='top', ha='right', linespacing=1.15)
ax.text(MD('2027-01'), top * 0.72, f'last 12 months\n{n12} posts\n{emp12} employers', fontsize=5.8, color=F.VIOLET, va='top', ha='right', linespacing=1.15)
ax.axvline(MD('2022-11'), color=F.MUTED, lw=0.5, ls=(0, (1.5, 2)), zorder=1); ax.text(MD('2022-10'), top * 0.50, 'ChatGPT', fontsize=6, color=F.MUTED, va='top', ha='right')
yb = -top * 0.19
for m in last12:
    ax.add_patch(Rectangle((MD(m) - pd.Timedelta(days=11), yb), pd.Timedelta(days=22), top * 0.07, color=F.VIOLET if mc[m] > 0 else F.HAIR, lw=0, clip_on=False))
ax.text(MD(last12[0]) - pd.Timedelta(days=35), yb + top * 0.035, 'posted', fontsize=5.5, color=F.MUTED, ha='right', va='center')
ax.set_xlim(MD(start), MD('2027-01')); ax.set_ylim(0, top); F.clean(ax); ax.set_yticks([0, 3, 6]); ax.set_ylabel('Posts per month', labelpad=2)
ax.set_xticks([MD(f'{y}-01') for y in (2018, 2021, 2024)]); ax.set_xticklabels(['2018', '2021', '2024'])
ax.text(MD(start), top * 1.03, 'Forward deployed engineer, international hiring', fontsize=6.5, color=F.INK, va='bottom')
# component read-out, in a separate text axes to the right of c
rx = F.axes_mm(fig, 104, 14, 24, 44, FW, FH); rx.axis('off'); rx.set_xlim(0, 1); rx.set_ylim(0, 1)
comp = [('Novelty  N', f'{row.N:.2f}', 'share of posts after Nov. 2022'), ('Growth  G', f'{G:+.2f}', 'log ratio of the two windows,\nshrunk towards 0 for small counts'),
        ('Breadth  B', f'{row.B:.2f}', f'{emp12} employers abroad, {int(row.fr_employers)} in France'), ('Persistence  P', f'{P:.2f}', f'{int(round(P * 12))} of 12 months with a post'),
        ('Index  E', f'{row.E:.2f}', 'mean of the four percentile ranks')]
for j, (k, v, d) in enumerate(comp):
    yy = 0.99 - 0.205 * j; bold = 'Index' in k
    rx.text(0, yy, k, fontsize=6.5, color=F.INK, va='top', ha='left', fontweight='bold' if bold else 'normal')
    rx.text(1, yy, v, fontsize=6.5, color=F.VIOLET if bold else F.INK, va='top', ha='right', fontweight='bold' if bold else 'normal')
    rx.text(0, yy - 0.075, d, fontsize=5.3, color=F.MUTED, va='top', ha='left', linespacing=1.15)

# ---------------- d: lifecycle stages ----------------
ax = ax_d; ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')
counts = em[em.canon != 'ai_other'].stage.value_counts()
stages = [('appearing', 1.1), ('diffusing', 3.7), ('established', 6.3), ('fading', 8.9)]
rules = ['five posts\nafter 2024,\nstill posted', 'G > 0.3,\n≥ 10\nemployers', 'posted 11 of\n12 months,\n|G| ≤ 0.3', 'G < −0.5\nfrom ≥ 10\nposts']
yl = 6.2
for i, (s, x) in enumerate(stages):
    n = int(counts.get(s, 0)); r = 0.38 + 0.08 * np.sqrt(n)
    ax.add_patch(Circle((x, yl), r, color=F.STAGE[s], zorder=3))
    ax.text(x, yl, str(n), fontsize=6.5, color='white', ha='center', va='center', zorder=4, fontweight='bold')
    ax.text(x, yl - 1.05, s, fontsize=6.5, color=F.INK, ha='center', va='top')
    ax.text(x, yl - 1.75, rules[i], fontsize=5.3, color=F.MUTED, ha='center', va='top', linespacing=1.15)
    if i < 3:
        xa, xb = x + r + 0.15, stages[i + 1][1] - 0.6
        ax.add_patch(FancyArrowPatch((xa, yl), (xb, yl), arrowstyle='-|>', mutation_scale=5, lw=0.6, color=F.MUTED, zorder=2))
ax.add_patch(FancyArrowPatch((stages[3][1], yl - 4.3), (stages[0][1] + 0.1, yl - 4.3), connectionstyle='arc3,rad=0.22', arrowstyle='-|>', mutation_scale=5, lw=0.6, ls=(0, (2, 2)), color=F.STAGE['renamed'], zorder=2))
ax.text(5.0, yl - 5.35, 'renamed: a fading title whose skill profile\nmatches a growing one', fontsize=5.3, color=F.STAGE['renamed'], ha='center', va='top', linespacing=1.15)
ax.text(0.2, 9.6, 'Canonical titles by stage, October 2026', fontsize=6.5, color=F.INK, va='top')
ax.text(0.2, 8.85, 'circle area grows with the number of titles', fontsize=5.3, color=F.MUTED, va='top')

F.panel(fig, ax_a, 'a', dx=-0.195); F.panel(fig, ax_b, 'b', dx=-0.012); F.panel(fig, ax_c, 'c', dx=-0.195, dy=0.03); F.panel(fig, ax_d, 'd', dx=-0.012, dy=-0.01)
F.save(fig, out, 'fig1_pipeline')
