# -*- coding: utf-8 -*-
"""France Travail 2026 cross-section figures of the ELIA paper.

fig5_ft_ai_share_breakdowns  share of postings mentioning AI by sector, region, contract and establishment size
fig6_ft_map_dept             share of postings mentioning AI by metropolitan departement (choropleth)
fig7_ft_salary_experience    posted salary distribution and experience requirement by segment

Usage: python pipeline/fig_ft.py <project root>
"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figstyle as F  # selects the Agg backend before pyplot is imported
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import colors as mcolors, cm
from matplotlib.collections import PolyCollection
from matplotlib.path import Path
from matplotlib.ticker import FixedLocator, FuncFormatter
from matplotlib.transforms import blended_transform_factory

F.setup()
ROOT = sys.argv[1]
RES = os.path.join(ROOT, 'data-lake', 'lake', 'results')
LAKE = os.path.join(ROOT, 'data-lake', 'lake', 'ft_enriched.parquet')
GEO = os.path.join(ROOT, 'data-lake', 'geo', 'departements.geojson')
OUT = os.path.join(ROOT, 'research-paper', 'fig')
NB = ' '                 # narrow no-break space (thousands separator, before %)
EN = '–'                 # en dash for ranges
PT = 25.4 / 72                # one typographic point in mm
TICK_MM = (2.5 + 2.0) * PT    # tick length + tick pad set by figstyle

NAF_EN = {'A': 'Agriculture', 'B': 'Mining', 'C': 'Manufacturing', 'D': 'Energy', 'E': 'Water & waste',
          'F': 'Construction', 'G': 'Trade', 'H': 'Transport', 'I': 'Accommodation & food',
          'J': 'Information & communication', 'K': 'Finance & insurance', 'L': 'Real estate',
          'M': 'Professional & technical services', 'N': 'Administrative & support services',
          'O': 'Public administration', 'P': 'Education', 'Q': 'Health & social work',
          'R': 'Arts & entertainment', 'S': 'Other services'}
CONTRACT_EN = {'CDI': 'Permanent', 'CDD': 'Fixed-term', 'MIS': 'Temp agency', 'LIB': 'Freelance',
               'CCE': 'Commercial agent', 'FRA': 'Franchise', 'SAI': 'Seasonal', 'DIN': 'Intermittent',
               'DDI': 'Insertion'}
SEGMENTS = [('AI-core (title)', 'AI-core (title)', F.ROSE), ('AI-related tech', 'AI-related tech', F.VIOLET),
            ('Other tech', 'Other tech', F.SLATE), ('AI mention, non-tech', 'AI mention, non-tech', F.AMBER),
            ('All other postings', 'All other postings', F.GREY)]

# ------------------------------------------------------------------ helpers
_MFIG = plt.figure(figsize=(3, 3))
_REND = _MFIG.canvas.get_renderer()


def tw(s, size=6, weight='normal'):
    """Rendered width of a string in mm (same font as the figures)."""
    t = _MFIG.text(0, 0, s, fontsize=size, fontweight=weight)
    w = t.get_window_extent(_REND).width / _MFIG.dpi * 25.4
    t.remove()
    return w


def nice_axis(vmax, max_ticks=6):
    """Upper limit and evenly spaced ticks starting at zero."""
    for step in (0.25, 0.5, 1, 2, 5, 10, 20, 50):
        top = np.ceil(vmax / step - 1e-9) * step
        if top / step + 1 <= max_ticks:
            return top, list(np.arange(0, top + step / 2, step))
    return vmax, [0, vmax]


def pct_axis(ax, top, ticks):
    ax.set_xlim(0, top)
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    dec = any(abs(t - round(t)) > 1e-9 for t in ticks)
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, p: '0' if abs(v) < 1e-9 else (f'{v:.1f}' if dec else f'{v:.0f}')))


def letter(fig, ax, s, x_left_mm, fw, fh, dy_mm=0.6):
    """Panel letter whose left edge sits at x_left_mm, just above the top of the axes."""
    x0 = ax.get_position().x0 * fw
    F.panel(fig, ax, s, dx=(x_left_mm + tw(s, 8, 'bold') - x0) / fw, dy=dy_mm / fh)


# ------------------------------------------------------------------ fig 5
def dotplot(ax, d, ref):
    """Dot plot of shares (fractions) with Wilson intervals; first row on top."""
    y = np.arange(len(d))
    ax.hlines(y, 100 * d.lo.clip(lower=0), 100 * d.hi, color=F.GREY2, lw=0.6, zorder=2)
    ax.plot(100 * d.share, y, 'o', ms=3.0, mfc=F.VIOLET, mec='white', mew=0.3, zorder=3, clip_on=False)
    ax.axvline(100 * ref, color=F.MUTED, lw=0.5, ls=(0, (2.4, 1.6)), zorder=1)
    ax.set_yticks(y)
    ax.set_yticklabels(list(d.index))
    ax.set_ylim(len(d) - 0.4, -0.6)
    pct_axis(ax, *nice_axis(100 * d.hi.max()))
    ax.spines['left'].set_position(('outward', 2.5))
    ax.set_xlabel('Postings mentioning AI (%)', labelpad=2.5)
    # the reference is labelled once, in a row whose interval ends left of it
    free = [i for i in (len(d) - 1, 0) if d.hi.iloc[i] < ref]
    yr = free[0] if free else len(d) - 0.4
    ax.annotate(f'National {100 * ref:.2f}{NB}%', (100 * ref, yr), xytext=(2, 0), textcoords='offset points',
                fontsize=6, color=F.MUTED, ha='left', va='center')


def size_class(s):
    s = str(s)
    if s.startswith('Non employeur') or s.startswith('0 salari'):
        return 'None / 0', -1
    nums = [int(re.sub(r'\D', '', x)) for x in re.split(r' à | ou ', s.split(' salari')[0])]
    if 'et plus' in s:
        return F.thousands(nums[0]) + '+', nums[0]
    return f'{F.thousands(nums[0])}{EN}{F.thousands(nums[1])}', nums[0]


def fig5(ref):
    naf = pd.read_csv(os.path.join(RES, 'ft_ai_share_by_naf.csv'), index_col=0)
    naf = naf[~naf.index.str.startswith('T')]
    naf.index = [NAF_EN[s.split()[0]] for s in naf.index]
    naf = naf.sort_values('share', ascending=False)
    reg = pd.read_csv(os.path.join(RES, 'ft_ai_share_by_region.csv'), index_col=0)
    reg = reg[reg.k > 0].sort_values('share', ascending=False)          # drops Mayotte (no AI posting)
    con = pd.read_csv(os.path.join(RES, 'ft_ai_share_by_contract.csv'), index_col=0)
    con.index = [CONTRACT_EN.get(i, i) for i in con.index]
    con = con.sort_values('share', ascending=False)
    raw = pd.read_csv(os.path.join(RES, 'ft_ai_share_by_size.csv'), index_col=0)
    cls = [size_class(i) for i in raw.index]
    raw['label'], raw['key'] = [c[0] for c in cls], [c[1] for c in cls]
    size = raw.groupby(['key', 'label'], as_index=False)[['n', 'k']].sum().sort_values('key').set_index('label')
    size['share'] = size.k / size.n
    size['lo'], size['hi'] = F.wilson(size.k.astype(float), size.n.astype(float))

    FW, FH = 183, 115
    fig = plt.figure(figsize=(FW * F.MM, FH * F.MM))
    gut = 2.5 * PT + TICK_MM + 0.4                       # outward spine + tick + pad
    la, lb, lc, ld = (max(tw(s) for s in d.index) for d in (naf, reg, con, size))
    wn = tw(F.thousands(naf.n.max()))
    X0, RM, G, NG = 1.0, 2.0, 5.5, 1.8
    ylab = 7 * PT * 1.2 + 2 * PT + 0.4                   # rotated y label of panel d
    W = (FW - RM - X0 - la - gut - NG - wn - G - lb - gut) / 2
    xa0 = X0 + la + gut
    xa1 = xa0 + W
    Xb = xa1 + NG + wn + G
    xb0 = Xb + lb + gut
    xb1 = xb0 + W
    xc0 = X0 + lc + gut
    xd0 = Xb + ylab + ld + gut
    yb, gap_mid, top_m = 9.0, 12.6, 4.0
    na, nc = max(len(naf), len(reg)), max(len(con), len(size))
    p = (FH - top_m - gap_mid - yb) / (na + nc + 0.4)
    Hc, Ha = (nc + 0.2) * p, (na + 0.2) * p
    ya0 = yb + Hc + gap_mid
    axa = F.axes_mm(fig, xa0, ya0, W, Ha, FW, FH)
    axb = F.axes_mm(fig, xb0, ya0, W, Ha, FW, FH)
    axc = F.axes_mm(fig, xc0, yb, xa1 - xc0, Hc, FW, FH)
    axd = F.axes_mm(fig, xd0, yb, xb1 - xd0, Hc, FW, FH)
    for ax, d in ((axa, naf), (axb, reg), (axc, con), (axd, size)):
        dotplot(ax, d, ref)
    axd.set_ylabel('Establishment size (employees)', labelpad=2)
    # n column, panel a only
    tr = blended_transform_factory(axa.transAxes, axa.transData)
    xn = 1 + (NG + wn) / W
    for i, n in enumerate(naf.n):
        axa.text(xn, i, F.thousands(n), transform=tr, fontsize=6, color=F.MUTED, ha='right', va='center')
    axa.text(xn, 1 + 0.4 / Ha, 'n', transform=axa.transAxes, fontsize=6, color=F.MUTED, ha='right', va='bottom')
    for ax, s, x in ((axa, 'a', X0), (axb, 'b', Xb), (axc, 'c', X0), (axd, 'd', Xb)):
        letter(fig, ax, s, x, FW, FH)
    F.save(fig, OUT, 'fig5_ft_ai_share_breakdowns')
    return (FW, FH)


# ------------------------------------------------------------------ fig 6
def ring_area(xy):
    x, y = xy[:, 0], xy[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def inner_point(xy, n=50):
    """Interior point farthest from the boundary (grid approximation of the pole of inaccessibility)."""
    x0, y0 = xy.min(0)
    x1, y1 = xy.max(0)
    gx, gy = np.meshgrid(np.linspace(x0, x1, n), np.linspace(y0, y1, n))
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    pts = pts[Path(xy).contains_points(pts)]
    if not len(pts):
        return xy.mean(0)
    d = np.min(np.hypot(pts[:, None, 0] - xy[None, :, 0], pts[:, None, 1] - xy[None, :, 1]), axis=1)
    return pts[np.argmax(d)]


def fig6():
    dep = pd.read_csv(os.path.join(RES, 'ft_ai_share_by_dept.csv'), dtype={'dept': str}).set_index('dept')
    dep.index = dep.index.str.zfill(2)
    dep = dep[~dep.index.str.startswith('97')]                         # metropolitan France only
    share = (100 * dep.share).to_dict()
    value = lambda c: share.get('20' if c in ('2A', '2B') else c, np.nan)  # Corsica is one row in the data
    gj = json.load(open(GEO, encoding='utf-8'))
    kx = np.cos(np.radians(46.5))                                      # equirectangular at mid-latitude
    parts, names = [], {}
    for f in gj['features']:
        code = str(f['properties']['code'])
        if code.startswith('97'):
            continue
        names[code] = f['properties']['nom']
        g = f['geometry']
        rings = [g['coordinates'][0]] if g['type'] == 'Polygon' else [q[0] for q in g['coordinates']]
        for r in rings:
            a = np.asarray(r, float)[:, :2]
            xy = np.column_stack([a[:, 0] * kx, a[:, 1]])
            parts.append((ring_area(xy), xy, code))
    parts.sort(key=lambda t: -t[0])                                    # enclaves drawn last, on top
    vmax = float(np.ceil(dep.share.max() * 100))
    norm = mcolors.PowerNorm(gamma=0.5, vmin=0, vmax=vmax)
    cmap = mcolors.LinearSegmentedColormap.from_list('elia_violet', ['#f5f2ff', '#3b0fb0'])

    FW, FH = 89, 92
    allxy = np.vstack([p[1] for p in parts])
    (xmin, ymin), (xmax, ymax) = allxy.min(0), allxy.max(0)
    pad = 0.04
    s = (FW - 2.0) / (xmax - xmin + 2 * pad)                           # mm per map unit
    mh = (ymax - ymin + 2 * pad) * s
    fig = plt.figure(figsize=(FW * F.MM, FH * F.MM))
    ax = F.axes_mm(fig, 1.0, FH - 1.0 - mh, FW - 2.0, mh, FW, FH)
    pc = PolyCollection([p[1] for p in parts], facecolors=[cmap(norm(value(p[2]))) for p in parts],
                        edgecolors='white', linewidths=0.3)
    ax.add_collection(pc)
    ax.set_xlim(xmin - pad, xmax + pad)
    ax.set_ylim(ymin - pad, ymax + pad)
    ax.set_aspect('equal')
    ax.axis('off')

    # five highest départements, labelled with thin leaders. When they cluster around Paris (2026 data),
    # the labels form two aligned columns either side of Paris, ordered so that leaders never cross.
    top = dep.share.nlargest(5)
    big = {}
    for a, xy, code in parts:
        big.setdefault(code, xy)                                       # largest ring of each code
    tgt = {c: inner_point(big[c]) for c in top.index if c in big}
    columns = {'92': ('L', 3.0), '78': ('L', -1.6), '75': ('R', 4.2), '94': ('R', -0.7), '91': ('R', -5.4)}
    colx = 7.5                                                         # mm from Paris to each column
    radial = [(8, 6), (-8, 6), (8, -6), (-8, -6), (10, 0)]
    for j, (code, v) in enumerate(top.items()):
        if code not in tgt:
            continue
        if '75' in tgt and set(tgt) <= set(columns):
            side, dy = columns[code]
            dx = colx if side == 'R' else -colx
            pos = (tgt['75'][0] + dx / s, tgt['75'][1] + dy / s)
        else:
            dx, dy = radial[j]
            pos = (tgt[code][0] + dx / s, tgt[code][1] + dy / s)
        ha = 'left' if dx > 0 else 'right'
        ax.annotate(f'{names.get(code, code)} {100 * v:.1f}{NB}%', tgt[code], xytext=pos, textcoords='data',
                    fontsize=6, color=F.INK, ha=ha, va='center',
                    arrowprops=dict(arrowstyle='-', color=F.INK, lw=0.35, shrinkA=0.5, shrinkB=0,
                                    relpos=(0, 0.5) if ha == 'left' else (1, 0.5)),
                    annotation_clip=False)

    # compact horizontal colour bar, bottom left
    cax = F.axes_mm(fig, 4.0, 5.0, 26.0, 1.6, FW, FH)
    ticks = [0, 1, vmax] if vmax > 2 else [0, vmax / 2, vmax]
    cb = fig.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation='horizontal', ticks=ticks)
    cb.outline.set_visible(False)
    cb.solids.set_edgecolor('face')
    cb.ax.tick_params(labelsize=6, length=2, width=0.5, pad=1.5)
    cb.ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: f'{v:g}'))
    cb.ax.minorticks_off()
    cb.set_label('Postings mentioning AI (%)', fontsize=7)
    cb.ax.xaxis.set_label_position('top')
    cb.ax.xaxis.label.set_horizontalalignment('left')
    cb.ax.xaxis.set_label_coords(0, 1 + 0.9 / 1.6)                    # left-aligned, 0.9 mm above the bar
    F.save(fig, OUT, 'fig6_ft_map_dept')
    return (FW, FH)


# ------------------------------------------------------------------ fig 7
def fig7(ft):
    keys = [k for k, _, _ in SEGMENTS]
    labels = [l for _, l, _ in SEGMENTS]
    cols = [c for _, _, c in SEGMENTS]
    sal = ft.dropna(subset=['sal_mid'])
    q = sal.groupby('segment').sal_mid.quantile([0.10, 0.25, 0.50, 0.75, 0.90]).unstack().reindex(keys) / 1000
    ns = sal.groupby('segment').size().reindex(keys)
    exp = pd.crosstab(ft.segment, ft.experienceExige, normalize='index').reindex(keys).fillna(0)

    FW, FH = 183, 62
    fig = plt.figure(figsize=(FW * F.MM, FH * F.MM))
    X0 = 1.0
    xa0 = X0 + max(tw(s) for s in labels) + TICK_MM + 0.4
    xb1 = FW - 2.5
    gab = 9.0
    total = xb1 - xa0 - gab
    Wa = 0.6 * total
    Wb = total - Wa
    y0, y1 = 9.5, FH - 4.2
    axa = F.axes_mm(fig, xa0, y0, Wa, y1 - y0, FW, FH)
    axb = F.axes_mm(fig, xa0 + Wa + gab, y0, Wb, y1 - y0, FW, FH)
    y = np.arange(len(keys))
    ylim = (len(keys) - 0.5, -0.75)

    # a: range plots
    axa.hlines(y, q[0.10], q[0.90], color=F.GREY2, lw=0.7, capstyle='butt', zorder=1)
    axa.hlines(y, q[0.25], q[0.75], colors=cols, lw=4.5, capstyle='butt', zorder=2)
    axa.scatter(q[0.50], y, s=4.8 ** 2, facecolor='white', edgecolors=[c if c != F.GREY else F.GREY2 for c in cols],
                linewidths=0.8, zorder=3)
    for i, k in enumerate(keys):
        med = f'{q.loc[k, 0.50]:.1f}'
        axa.annotate(med, (q.loc[k, 0.90], i), xytext=(3, 0), textcoords='offset points', fontsize=6,
                     color=F.INK, ha='left', va='center')
        axa.annotate(f'n = {F.thousands(ns[k])}', (q.loc[k, 0.90], i), xytext=(3 + tw(med) / PT + 4, 0),
                     textcoords='offset points', fontsize=6, color=F.MUTED, ha='left', va='center')
    axa.set_xlim(10, 100)
    axa.xaxis.set_major_locator(FixedLocator(range(10, 101, 10)))
    axa.set_yticks(y)
    axa.set_yticklabels(labels)
    axa.set_ylim(*ylim)
    axa.set_xlabel('Posted annual salary (k€)', labelpad=2.5)

    # b: experience requirement, 100 % stacked bars
    slate50 = mcolors.to_hex(0.5 * np.array(mcolors.to_rgb(F.SLATE)) + 0.5)
    cats = [('D', 'Open to beginners', F.GREY, F.INK, F.MUTED), ('S', 'Experience desired', slate50, F.INK, F.SLATE),
            ('E', 'Experience required', F.ROSE, 'white', F.ROSE)]
    cats = [c for c in cats if c[0] in exp.columns and exp[c[0]].sum() > 0]
    left = np.zeros(len(keys))
    for j, (code, name, col, tcol, lcol) in enumerate(cats):
        v = 100 * exp[code].values
        axb.barh(y, v, left=left, height=0.48, color=col, lw=0, zorder=2)
        for i in range(len(keys)):
            if v[i] >= 8:
                axb.text(left[i] + v[i] / 2, i, f'{v[i]:.0f}', ha='center', va='center', fontsize=6, color=tcol)
        if j == 0:
            xl, ha = left[0], 'left'
        elif j == len(cats) - 1:
            xl, ha = left[0] + v[0], 'right'
        else:
            xl, ha = left[0] + v[0] / 2, 'center'
        axb.text(xl, -0.34, name, ha=ha, va='bottom', fontsize=6, color=lcol)
        left += v
    axb.set_xlim(0, 100)
    axb.xaxis.set_major_locator(FixedLocator([0, 50, 100]))
    axb.set_ylim(*ylim)
    axb.set_yticks([])
    F.clean(axb, left=False)
    axb.set_xlabel('Share of postings (%)', labelpad=2.5)

    letter(fig, axa, 'a', X0, FW, FH)
    letter(fig, axb, 'b', xa0 + Wa + gab - 2.5, FW, FH)
    F.save(fig, OUT, 'fig7_ft_salary_experience')
    return (FW, FH), q, ns, exp


if __name__ == '__main__':
    ft = pd.read_parquet(LAKE, columns=['segment', 'sal_mid', 'experienceExige', 'ai_any'])
    ref = float(ft.ai_any.mean())
    print('national share', round(100 * ref, 3))
    print('fig5 size', fig5(ref))
    print('fig6 size', fig6())
    size7, q, ns, exp = fig7(ft)
    print('fig7 size', size7)
    print(q.round(1).assign(n=ns).to_string())
    print(exp.round(3).to_string())
    plt.close(_MFIG)
