# -*- coding: utf-8 -*-
"""Fig. 10 - Emergence Index of the canonical AI and data titles; Fig. 11 - title n-grams discovered from the data.

Fig. 10: (a) Emergence Index as a dot plot coloured by lifecycle stage, (b) percentile ranks of the four components
(novelty N, growth G, breadth B, persistence P) as a heat strip, (c) volumes on log scales: international (HN) posts in
the last 12 months and French postings in 2026. The columns share the rows exactly (same y limits, same axes height).
Fig. 11: (a) title n-grams first seen after November 2022 in international hiring posts (dot timeline, dot area = posts),
(b) the most frequent AI title n-grams in French AI-titled postings, 2026.
Axes are placed in millimetres (F.axes_mm) so that labels outside the axes are never clipped.
Usage: python pipeline/fig_emergence.py <root>
"""
import sys, os
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from matplotlib import colors as mcolors, ticker, transforms
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figstyle as F, lexicon as L

F.setup()
root = sys.argv[1]
res = os.path.join(root, 'data-lake', 'lake', 'results'); out = os.path.join(root, 'research-paper', 'fig')
PT = 25.4 / 72                      # millimetres per point
CHATGPT = 2022 + 11 / 12 - 0.03     # 30 November 2022, in decimal years


def text_mm(fig, s, size, **kw):
    """Width and height (mm) of a text once rendered."""
    t = fig.text(0, 0, s, fontsize=size, **kw)
    bb = t.get_window_extent(fig.canvas.get_renderer()); t.remove()
    return bb.width / fig.dpi * 25.4, bb.height / fig.dpi * 25.4


def letter(fig, ax, ch, x_mm, y_mm, fw, fh):
    """Panel letter (F.panel) with its right edge at x_mm and its bottom at y_mm, in figure millimetres."""
    b = ax.get_position()
    F.panel(fig, ax, ch, dx=x_mm / fw - b.x0, dy=y_mm / fh - b.y1)


def header(fig, x_mm, y_mm, s, fw, fh, ha='center', color=F.MUTED):
    """Column header, 6 pt, bottom at y_mm."""
    fig.text(x_mm / fw, y_mm / fh, s, fontsize=6, ha=ha, va='bottom', color=color)


def xlabel_at(ax, s, y_mm, bot, h, x=0.5):
    """x-axis label whose top sits at y_mm (figure mm), so that labels of all panels share one baseline."""
    ax.set_xlabel(s)
    ax.xaxis.set_label_coords(x, (y_mm - bot) / h)
    ax.xaxis.label.set_va('top')


ACRONYM = {'ai': 'AI', 'ia': 'IA', 'ml': 'ML', 'llm': 'LLM', 'llms': 'LLMs', 'nlp': 'NLP', 'mlops': 'MLOps', 'genai': 'GenAI', 'bi': 'BI', 'rag': 'RAG'}
ACCENT = {'ingenieur': 'ingénieur', 'developpeur': 'développeur', 'developpement': 'développement', 'generative': 'générative',
          'cybersecurite': 'cybersécurité', 'securite': 'sécurité', 'donnees': 'données', 'specialiste': 'spécialiste',
          'integrateur': 'intégrateur', 'strategie': 'stratégie', 'deploiement': 'déploiement', 'systemes': 'systèmes'}


def pretty(s, french=False):
    """Display form of a normalised n-gram: acronyms in capitals and, for French n-grams, accents restored."""
    return ' '.join(ACRONYM.get(w, ACCENT.get(w, w) if french else w) for w in s.split())


# =====================================================================================================
# Fig. 10  Emergence Index
# =====================================================================================================
e = pd.read_csv(os.path.join(res, 'emergence_index.csv'))
e = e[(e.canon != 'ai_other') & (e.stage != 'too rare')].copy()
e['label'] = [L.CANON_LABEL.get(c, lab) for c, lab in zip(e.canon, e.label)]
e = e.sort_values(['E', 'N_rank'], ascending=False, kind='mergesort').reset_index(drop=True)
n = len(e); y = np.arange(n)

FW, FH = 183.0, 110.0
TOP, BOT, RIGHT = FH - 5.0, 9.5, FW - 1.0
H = TOP - BOT
YLAB = BOT - 4.9                                   # top of the x-axis labels
fig = plt.figure(figsize=(FW * F.MM, FH * F.MM))
labw = max(text_mm(fig, s, 6)[0] for s in e.label)
XA = 1.0 + labw + 4.5 * PT                         # labels + tick (2.5 pt) + pad (2 pt)
WA = 33.0
DX = 4.0                                           # stage label offset from the dot centre (pt)
reach = max(XA + r.E * WA + DX * PT + text_mm(fig, r.stage, 6)[0] for r in e.itertuples())
XB = max(reach, XA + WA + 2.0) + 3.0
CW = 11.5; WB = 4 * CW
XC = XB + WB + 6.0; GC = 5.0
WC = (RIGHT - XC - GC) / 2
axa = F.axes_mm(fig, XA, BOT, WA, H, FW, FH)
axb = F.axes_mm(fig, XB, BOT, WB, H, FW, FH)
axc1 = F.axes_mm(fig, XC, BOT, WC, H, FW, FH)
axc2 = F.axes_mm(fig, XC + WC + GC, BOT, WC, H, FW, FH)
for ax in (axa, axb, axc1, axc2):
    ax.set_ylim(n - 0.5, -0.5)

# a: index and stage
cols = [F.STAGE.get(s, F.GREY2) for s in e.stage]
axa.scatter(e.E, y, s=20, color=cols, linewidths=0, zorder=3, clip_on=False)
for yi, r, c in zip(y, e.itertuples(), cols):
    F.label_end(axa, r.E, yi, r.stage, color=c, dx=DX, fontsize=6, va='center_baseline')
axa.set_yticks(y); axa.set_yticklabels(e.label)
axa.set_xlim(0, 1)
axa.xaxis.set_major_locator(ticker.MultipleLocator(0.2))
axa.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: f'{v:g}'))
xlabel_at(axa, 'Emergence Index', YLAB, BOT, H)

# b: components as percentile ranks
comp = e[['N_rank', 'G_rank', 'B_rank', 'P_rank']].to_numpy()
cmap = mcolors.LinearSegmentedColormap.from_list('rank', ['#f6f3ff', F.VIOLET])
axb.pcolormesh(np.arange(5), np.arange(n + 1) - 0.5, comp, cmap=cmap, vmin=0, vmax=1, edgecolors='white', linewidth=0.6)
for i in range(n):
    for j in range(4):
        v = comp[i, j]; r_, g_, b_ = cmap(v)[:3]
        dark = 0.2126 * r_ + 0.7152 * g_ + 0.0722 * b_ < 0.45
        axb.text(j + 0.5, i, f'{v:.2f}', ha='center', va='center_baseline', fontsize=5.5, color='white' if dark else F.INK)
axb.set_xlim(0, 4)
for s in axb.spines.values():
    s.set_visible(False)
axb.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
xlabel_at(axb, 'Percentile rank', YLAB, BOT, H)
for j, name in enumerate(['Novelty', 'Growth', 'Breadth', 'Persistence']):
    header(fig, XB + (j + 0.5) * CW, TOP + 1.0, name, FW, FH, color=F.INK)

# c: volumes on log scales (symlog keeps the titles with no post in the last 12 months at zero)
for ax, col, head, xl in ((axc1, 'hn_last12', 'International (HN)', 'Posts, last 12 months'),
                          (axc2, 'fr_postings_2026', 'France', 'Postings in 2026')):
    ax.set_xscale('symlog', linthresh=1, linscale=0.5)
    ax.set_xlim(0, 700)
    ax.xaxis.set_major_locator(ticker.FixedLocator([0, 1, 10, 100]))
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: F.thousands(v)))
    ax.xaxis.set_minor_locator(ticker.NullLocator())
    ax.scatter(e[col], y, s=14, color=F.GREY2, linewidths=0, zorder=3, clip_on=False)
    ax.spines['left'].set_visible(False)
    ax.tick_params(left=False, labelleft=False)
    xlabel_at(ax, xl, YLAB, BOT, H)
    b = ax.get_position()
    header(fig, (b.x0 + b.x1) / 2 * FW, TOP + 1.0, head, FW, FH, color=F.INK)

letter(fig, axa, 'a', 3.2, TOP + 1.0, FW, FH)
letter(fig, axb, 'b', XB - 1.8, TOP + 1.0, FW, FH)
letter(fig, axc1, 'c', XC - 1.8, TOP + 1.0, FW, FH)
F.save(fig, out, 'fig10_emergence_index')

# =====================================================================================================
# Fig. 11  Discovered title n-grams
# =====================================================================================================
hn = pd.read_csv(os.path.join(res, 'discovery_hn_ngrams.csv'))
bad = hn.ngram.str.contains(r'https|\.ai|is |\bx\b', regex=True)     # URLs, company domains, "is hiring", "AI x"
hn = hn[(hn.first_seen > '2022-11') & ~bad & (hn.employers >= 2)].copy()   # one-employer n-grams are boilerplate
hn = hn.sort_values(['first_seen', 'n'], ascending=[True, False]).reset_index(drop=True)
hn['t'] = [int(s[:4]) + (int(s[5:7]) - 0.5) / 12 for s in hn.first_seen]
hn['label'] = [pretty(s) for s in hn.ngram]
fr = pd.read_csv(os.path.join(res, 'discovery_ft_ngrams.csv'))
fr = fr[fr.employers >= 2].sort_values(['n', 'employers'], ascending=False).head(16).reset_index(drop=True)
fr['label'] = [pretty(s, french=True) for s in fr.ngram]
na, nb = len(hn), len(fr)

FW, FH = 183.0, 72.0
TOP, BOT, RIGHT = FH - 5.0, 9.5, FW - 1.0
H = TOP - BOT
YLAB = BOT - 4.9
fig = plt.figure(figsize=(FW * F.MM, FH * F.MM))
labwa = max(text_mm(fig, s, 6)[0] for s in hn.label)
labwb = max(text_mm(fig, s, 6)[0] for s in fr.label)
wemp = text_mm(fig, 'Employers', 6)[0]; wdep = text_mm(fig, 'Departments', 6)[0]
XA = 1.0 + labwa + 2 * PT                          # labels + pad (no y ticks)
GAP = 6.0
fixed = (XA + 1.5 + wemp) + GAP + (labwb + 2 * PT) + (1.5 + wemp + 2.0 + wdep)
WA = WB = (RIGHT - fixed) / 2
XB = XA + WA + 1.5 + wemp + GAP + labwb + 2 * PT
axa = F.axes_mm(fig, XA, BOT, WA, H, FW, FH)
axb = F.axes_mm(fig, XB, BOT, WB, H, FW, FH)

# a: dot timeline of the n-grams born after ChatGPT
K = 1.1                                            # marker area (pt^2) per post
axa.set_ylim(na - 0.5, -0.5)
axa.axvline(CHATGPT, color=F.GREY2, lw=0.5, zorder=1)
axa.scatter(hn.t, np.arange(na), s=K * hn.n, color=F.ROSE, linewidths=0, zorder=3, clip_on=False)
axa.set_yticks(np.arange(na)); axa.set_yticklabels(hn.label)
axa.spines['left'].set_visible(False); axa.tick_params(axis='y', length=0)
axa.set_xlim(2022.65, 2025.35)
axa.xaxis.set_major_locator(ticker.FixedLocator([2023, 2024, 2025]))
axa.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: f'{v:.0f}'))
axa.xaxis.set_minor_locator(ticker.FixedLocator([2022.75, 2023.25, 2023.5, 2023.75, 2024.25, 2024.5, 2024.75, 2025.25]))
axa.tick_params(axis='x', which='minor', length=1.5, width=0.4)
xlabel_at(axa, 'Month of first post', YLAB, BOT, H)
ba = axa.get_position()
header(fig, (ba.x0 + (CHATGPT - 2022.65) / 2.7 * ba.width) * FW, TOP + 1.0, 'ChatGPT', FW, FH)
xe = XA + WA + 1.5 + wemp
header(fig, xe, TOP + 1.0, 'Employers', FW, FH, ha='right')
tr = transforms.blended_transform_factory(fig.transFigure, axa.transData)
for yi, v in enumerate(hn.employers):
    axa.text(xe / FW, yi, f'{int(v)}', transform=tr, fontsize=6, color=F.MUTED, ha='right', va='center_baseline')
# dot-size key in the header band, right-aligned on the plot area (texts share the headers' bottom line)
keys = (10, 20, 40)
dmm = [np.sqrt(K * v) * PT for v in keys]                          # dot diameters (mm)
wk = [text_mm(fig, f'{v}', 6)[0] for v in keys]
x = XA + WA - 2.0 - sum(d + 0.8 + w for d, w in zip(dmm, wk)) - 2.0 * (len(keys) - 1)
header(fig, x - 1.5, TOP + 1.0, 'Posts', FW, FH, ha='right')
for v, d, w in zip(keys, dmm, wk):
    axa.scatter([(x + d / 2) / FW], [(TOP + 2.2) / FH], s=K * v, color=F.ROSE, linewidths=0, transform=fig.transFigure, clip_on=False)
    header(fig, x + d + 0.8, TOP + 1.0, f'{v}', FW, FH, ha='left')
    x += d + 0.8 + w + 2.0

# b: most frequent AI title n-grams in France
axb.set_ylim(nb - 0.5, -0.5)
axb.barh(np.arange(nb), fr.n, height=0.64, color=F.VIOLET, zorder=2)
axb.set_yticks(np.arange(nb)); axb.set_yticklabels(fr.label)
axb.tick_params(axis='y', length=0)
axb.set_xlim(0, fr.n.max() * 1.05)
axb.xaxis.set_major_locator(ticker.MultipleLocator(50))
xlabel_at(axb, 'Postings in 2026', YLAB, BOT, H)
xe1 = XB + WB + 1.5 + wemp; xe2 = xe1 + 2.0 + wdep
header(fig, xe1, TOP + 1.0, 'Employers', FW, FH, ha='right')
header(fig, xe2, TOP + 1.0, 'Departments', FW, FH, ha='right')
tr = transforms.blended_transform_factory(fig.transFigure, axb.transData)
for yi, r in enumerate(fr.itertuples()):
    axb.text(xe1 / FW, yi, f'{int(r.employers)}', transform=tr, fontsize=6, color=F.MUTED, ha='right', va='center_baseline')
    axb.text(xe2 / FW, yi, f'{int(r.depts)}', transform=tr, fontsize=6, color=F.MUTED, ha='right', va='center_baseline')

letter(fig, axa, 'a', 3.2, TOP + 1.0, FW, FH)
letter(fig, axb, 'b', XB - 2 * PT - labwb - 0.6, TOP + 1.0, FW, FH)
F.save(fig, out, 'fig11_discovered_titles')
