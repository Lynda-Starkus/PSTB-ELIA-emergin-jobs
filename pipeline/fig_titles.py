# -*- coding: utf-8 -*-
"""Fig. 8 - canonical AI and data titles in French postings (France Travail, 2026).

Three columns share the title axis (titles sorted by postings): (a) postings as horizontal bars coloured by group,
(b) distinct employers and (c) departements as dots, each column with a grey hairline at zero.
Axes are placed in millimetres (F.axes_mm) so that labels outside the axes are never clipped.
Usage: python pipeline/fig_titles.py <root>
"""
import sys, os
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from matplotlib import ticker
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figstyle as F, lexicon as L

F.setup()
root = sys.argv[1]
res = os.path.join(root, 'data-lake', 'lake', 'results'); out = os.path.join(root, 'research-paper', 'fig')
BLUE = '#2b8fd6'


def group_colour(family):
    """Data titles (family starting with 'Data') blue, AI titles (family mentioning AI or ML) rose, other grey."""
    if family.startswith('Data'):
        return BLUE
    if 'AI' in family or 'ML' in family:
        return F.ROSE
    return F.GREY


def text_mm(fig, s, size, **kw):
    """Width and height (mm) of a text once rendered."""
    t = fig.text(0, 0, s, fontsize=size, **kw)
    bb = t.get_window_extent(fig.canvas.get_renderer()); t.remove()
    return bb.width / fig.dpi * 25.4, bb.height / fig.dpi * 25.4


def letter(fig, ax, ch, x_mm, y_mm, fw, fh):
    """Panel letter (F.panel) with its right edge at x_mm and its bottom at y_mm, in figure millimetres."""
    b = ax.get_position()
    F.panel(fig, ax, ch, dx=x_mm / fw - b.x0, dy=y_mm / fh - b.y1)


# ---------------- data ----------------
ct = pd.read_csv(os.path.join(res, 'ft_canon_titles.csv'), index_col=0)
ct = ct[ct.index != 'ai_other'].copy()                                   # canonical titles only
ct['label'] = [L.CANON_LABEL.get(c, lab) for c, lab in zip(ct.index, ct.label)]
ct['family'] = [L.CANON_FAMILY.get(c, fam) for c, fam in zip(ct.index, ct.family)]
ct = ct.sort_values(['n', 'employers', 'depts'], ascending=False)
ct['colour'] = [group_colour(f) for f in ct.family]
n = len(ct); y = np.arange(n)

# ---------------- layout (mm) ----------------
FW, FH = 183.0, 95.0
TOP, BOT, RIGHT, GAP = FH - 5.0, 9.0, FW - 1.5, 7.0
fig = plt.figure(figsize=(FW * F.MM, FH * F.MM))
labw = max(text_mm(fig, s, 6)[0] for s in ct.label)
x0 = 1.0 + labw + 1.0                                                     # margin + title labels + tick pad
avail = RIGHT - x0 - 2 * GAP
wa = 0.44 * avail; wb = wc = (avail - wa) / 2
xb = x0 + wa + GAP; xc = xb + wb + GAP
axa = F.axes_mm(fig, x0, BOT, wa, TOP - BOT, FW, FH)
axb = F.axes_mm(fig, xb, BOT, wb, TOP - BOT, FW, FH)
axc = F.axes_mm(fig, xc, BOT, wc, TOP - BOT, FW, FH)

for ax in (axa, axb, axc):
    ax.set_ylim(n - 0.5, -0.5)                                            # identical rows in the three columns
    ax.set_yticks(y)
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', length=0)
    ax.axvline(0, color=F.GREY2, lw=0.5, zorder=1)                        # hairline at zero
axa.set_yticklabels(ct.label)
axb.tick_params(labelleft=False); axc.tick_params(labelleft=False)

# a: postings
axa.barh(y, ct.n, height=0.64, color=ct.colour, zorder=2)
for yi, v in zip(y, ct.n):
    F.label_end(axa, v, yi, f'{int(v)}', color=F.INK, dx=1.5, fontsize=6, va='center_baseline')
axa.set_xlim(0, ct.n.max() * 1.14)
axa.xaxis.set_major_locator(ticker.MultipleLocator(100))
axa.set_xlabel('Postings in 2026')
xr = axa.get_xlim()[1]
axa.text(xr, n - 2.7, 'Data titles', color=BLUE, fontsize=6, ha='right', va='center_baseline')
axa.text(xr, n - 1.6, 'AI titles', color=F.ROSE, fontsize=6, ha='right', va='center_baseline')

# b, c: employers and departements
for ax, col, step, xlab in ((axb, 'employers', 50, 'Distinct employers'), (axc, 'depts', 20, 'Departments')):
    ax.scatter(ct[col], y, s=14, color=ct.colour, linewidths=0, zorder=3, clip_on=False)
    top = ct[col].max()
    ax.set_xlim(0, top * 1.06)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(step))
    ax.set_xlabel(xlab)

ly = TOP + 1.2
letter(fig, axa, 'a', 3.2, ly, FW, FH)
letter(fig, axb, 'b', xb - 1.8, ly, FW, FH)
letter(fig, axc, 'c', xc - 1.8, ly, FW, FH)
F.save(fig, out, 'fig8_ft_canonical_titles')
