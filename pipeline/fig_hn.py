# -*- coding: utf-8 -*-
"""Hacker News 'Who is hiring', April 2011 - September 2026.

fig3_hn_series            a: share of posts mentioning AI and share with an AI role title (3-month centred means);
                          b: AI and data title families as a share of posts, five stacked groups (3-month centred means).
fig4_hn_first_appearance  dumbbell timeline: first and fifth post of each canonical title.

Usage: python pipeline/fig_hn.py <project root>
"""
import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figstyle as F  # noqa: E402

ROOT = sys.argv[1]
RES = os.path.join(ROOT, 'data-lake', 'lake', 'results')
OUT = os.path.join(ROOT, 'research-paper', 'fig')

LAST = '2026-09'            # 2026-10 is incomplete and excluded
CHATGPT = 2022 + 11 / 12    # 30 November 2022
BLUE = '#2b8fd6'            # data titles
PT = 72 / 25.4              # points per mm
NS = ' '               # narrow no-break space before %

# stacked groups of panel 3b, bottom to top: (label, families, fill colour, text colour)
GROUPS = [
    ('AI engineering', ['AI engineering', 'AI engineering (new titles)'], F.ROSE, F.ROSE),
    ('ML engineering', ['ML engineering'], F.FAMILY['ML engineering'], F.FAMILY['ML engineering']),
    ('Other AI roles', ['AI research', 'AI architecture & leadership', 'AI business roles',
                        'AI governance & ethics', 'AI training & data labelling'], F.VIOLET, F.VIOLET),
    ('Data roles', ['Data science', 'Data engineering', 'Data analytics', 'Data leadership'], BLUE, BLUE),
    ('Other\nAI-labelled', ['Other AI-labelled'], F.GREY, F.MUTED),
]

SHORT = {  # English row labels of the canonical titles
    'forward_deployed_engineer': 'Forward deployed engineer', 'agent_engineer': 'AI agent engineer',
    'prompt_engineer': 'Prompt engineer', 'genai_engineer': 'Generative AI engineer', 'ai_engineer': 'AI engineer',
    'ml_engineer': 'Machine learning engineer', 'mlops_engineer': 'MLOps engineer', 'nlp_engineer': 'NLP engineer',
    'computer_vision_engineer': 'Computer vision engineer', 'ai_researcher': 'AI research scientist',
    'ai_architect': 'AI architect', 'head_of_ai': 'Head of AI', 'ai_product_manager': 'AI product manager',
    'ai_governance': 'AI governance & ethics', 'ai_consultant': 'AI consultant', 'ai_trainer': 'AI trainer / annotator',
    'ai_sales': 'AI sales / solutions', 'data_scientist': 'Data scientist', 'data_engineer': 'Data engineer',
    'data_analyst': 'Data analyst / BI', 'data_architect': 'Data architect', 'data_leader': 'Data leadership',
    'ai_other': 'Other AI-labelled',
}


def mx(m):
    """'YYYY-MM' -> decimal year at mid-month."""
    return int(m[:4]) + (int(m[5:7]) - 0.5) / 12


def ma3(s):
    return s.rolling(3, center=True, min_periods=1).mean()


def pct(v):
    return f'{v:.1f}{NS}%' if v < 10 else f'{v:.0f}{NS}%'


def group_colour(family):
    if family.startswith('Data'):
        return BLUE
    if family.startswith(('AI', 'ML')):
        return F.ROSE
    return F.GREY2


def spread(y, h, lo=-np.inf, hi=np.inf):
    """Move label centres apart (keeping their order) so that neighbours are at least (h_i + h_j) / 2 apart."""
    o = np.argsort(y)
    p = np.asarray(y, float)[o].copy()
    hh = np.asarray(h, float)[o]
    for _ in range(500):
        moved = False
        for k in range(1, len(p)):
            gap = (hh[k] + hh[k - 1]) / 2 - (p[k] - p[k - 1])
            if gap > 1e-9:
                p[k] += gap / 2
                p[k - 1] -= gap / 2
                moved = True
        p[0] = max(p[0], lo + hh[0] / 2)
        p[-1] = min(p[-1], hi - hh[-1] / 2)
        if not moved:
            break
    r = np.empty_like(p)
    r[o] = p
    return r


def year_axis(ax, x0, x1):
    ax.set_xticks(np.arange(2012, 2027, 2))
    ax.set_xticks(np.arange(2011, 2027), minor=True)
    ax.set_xlim(x0, x1)                          # after set_xticks, which would widen the limits
    ax.tick_params(axis='x', which='minor', length=1.5, width=0.4)


def fig3():
    hm = pd.read_csv(os.path.join(RES, 'hn_monthly.csv'), index_col=0)
    hm = hm[(hm.index <= LAST) & (hm.n >= 50)]          # drop 2026-10 and the near-empty December 2011 thread
    months = pd.period_range(hm.index[0], LAST, freq='M').strftime('%Y-%m')
    x = np.array([mx(m) for m in months])
    ai = 100 * ma3(hm.ai_share.reindex(months)).values
    core = 100 * ma3(hm.core_share.reindex(months)).values
    fam = pd.read_csv(os.path.join(RES, 'hn_family_share_monthly.csv'), index_col=0)
    fam = fam.reindex(hm.index).fillna(0).reindex(months)  # zero in observed months, missing months filled by the mean
    band = np.array([100 * ma3(fam[cols].sum(axis=1, min_count=1)).values for _, cols, _, _ in GROUPS])
    top = np.cumsum(band, axis=0)
    bot = top - band

    FW, FH = 183, 95
    L, R = 12.5, 20.0
    W = FW - L - R
    ha_, hb_ = 38.8, 39.5
    fig = plt.figure(figsize=(FW / 25.4, FH / 25.4))
    axa = F.axes_mm(fig, L, 52.0, W, ha_, FW, FH)
    axb = F.axes_mm(fig, L, 5.0, W, hb_, FW, FH)
    for ax in (axa, axb):
        year_axis(ax, x[0], x[-1])
        ax.axvline(CHATGPT, color=F.GREY2, lw=0.5, zorder=0.5)

    # a: AI mentioned anywhere / AI in the role title
    axa.plot(x, ai, color=F.VIOLET, lw=1.0, zorder=3)
    axa.plot(x, core, color=F.ROSE, lw=1.0, zorder=3)
    axa.set_ylim(0, 70)
    axa.set_yticks(np.arange(0, 71, 10))
    axa.set_ylabel('Share of posts (%)')
    axa.text(CHATGPT + 0.12, 70, 'ChatGPT', fontsize=6, color=F.MUTED, ha='left', va='top')
    F.label_end(axa, x[-1], ai[-1], f'AI mentioned\n{pct(ai[-1])}', color=F.VIOLET)
    F.label_end(axa, x[-1], core[-1], f'AI in title\n{pct(core[-1])}', color=F.ROSE)

    # b: composition of AI and data titles
    for (_, _, col, _), b0, b1 in zip(GROUPS, bot, top):
        axb.fill_between(x, b0, b1, color=col, lw=0, zorder=1)
    for t in top[:-1]:
        axb.plot(x, t, color='white', lw=0.4, zorder=2, solid_capstyle='butt')
    ymax = 20
    axb.set_ylim(0, ymax)
    axb.set_yticks(np.arange(0, ymax + 1, 5))
    axb.set_ylabel('Share of posts (%)')
    ppu = hb_ * PT / ymax                       # points per data unit
    line = 6.5 * 1.2 / ppu                      # height of one label line in data units
    yc = (bot[:, -1] + top[:, -1]) / 2
    nl = np.array([g[0].count('\n') + 1 for g in GROUPS])
    yl = spread(yc, nl * line, 0, ymax)
    for i, (name, _, _, tcol) in enumerate(GROUPS):
        if band[i, -1] < line or abs(yl[i] - yc[i]) > 0.15 * line:
            F.leader(axb, (x[-1], yc[i]), (8, (yl[i] - yc[i]) * ppu), name, color=tcol, fontsize=6.5)
        else:
            F.label_end(axb, x[-1], yl[i], name, color=tcol, dx=8)

    for ax, k in ((axa, 'a'), (axb, 'b')):
        F.panel(fig, ax, k, dx=(3.2 - L) / FW, dy=0.8 / FH)
    F.save(fig, OUT, 'fig3_hn_series')


def fig4():
    ct = pd.read_csv(os.path.join(RES, 'hn_canon_titles.csv'))
    ct = ct[ct.canon != 'ai_other'].copy()
    ct['x1'] = ct.first_seen.map(mx)
    ct['x5'] = ct.first_seen_5.map(lambda m: mx(m) if isinstance(m, str) else np.nan)
    ct = ct.sort_values(['x5', 'x1'], na_position='last').reset_index(drop=True)
    ct['col'] = ct.family.map(group_colour)
    n = len(ct)

    FW, FH = 183, 100
    L, R, B, T = 29.0, 13.0, 10.5, 4.5
    W, H = FW - L - R, FH - B - T
    K = 0.8                                      # marker area (pt^2) per post in the last 12 months
    fig = plt.figure(figsize=(FW / 25.4, FH / 25.4))
    ax = F.axes_mm(fig, L, B, W, H, FW, FH)
    ax.axvline(CHATGPT, color=F.GREY2, lw=0.5, zorder=0.5)
    for i, r in ct.iterrows():
        if r.x5 > r.x1:
            ax.plot([r.x1, r.x5], [i, i], color=r.col, lw=0.8, alpha=0.45, solid_capstyle='butt', zorder=1)
    ax.scatter(ct.x1, ct.index, s=9, facecolor='white', edgecolor=ct.col, lw=0.7, zorder=3)
    ax.scatter(ct.x5, ct.index, s=np.maximum(K * ct.last12, 2.0), color=ct.col, lw=0, zorder=4)
    ax.set_yticks(range(n))
    ax.set_yticklabels([SHORT.get(c, c) for c in ct.canon])
    ax.set_ylim(n - 0.5, -0.6)
    year_axis(ax, 2011, 2026.75)
    F.clean(ax, left=False)

    # right-hand column: posts in the last 12 months
    xc = 1 + 9.5 / W
    tr = ax.get_yaxis_transform()
    for i, r in ct.iterrows():
        ax.text(xc, i, f'{int(r.last12)}', transform=tr, ha='right', va='center', fontsize=6, color=F.MUTED)
    ax.text(xc, 1 + 1.0 / H, 'Posts, last 12 months', transform=ax.transAxes, ha='right', va='bottom',
            fontsize=6, color=F.MUTED)
    ax.text(CHATGPT, 1 + 1.0 / H, 'ChatGPT', transform=ax.get_xaxis_transform(), ha='center', va='bottom',
            fontsize=6, color=F.MUTED)

    # one-line key under the axis (positions in mm)
    kh = 6.0
    kx = fig.add_axes([0, 0, 1, kh / FH])
    kx.set_xlim(0, FW)
    kx.set_ylim(0, kh)
    kx.axis('off')
    rend = fig.canvas.get_renderer()
    yk = 2.6
    cur = [L]

    def word(s, gap=3.0):
        t = kx.text(cur[0], yk, s, fontsize=6, color=F.MUTED, ha='left', va='center')
        cur[0] += t.get_window_extent(rend).width / fig.dpi * 25.4 + gap

    def dot(s, face, edge=None, lw=0.0, gap=0.6):
        d = np.sqrt(s) / PT                       # marker diameter in mm
        kx.scatter([cur[0] + d / 2], [yk], s=s, facecolor=face, edgecolor=edge or face, lw=lw, clip_on=False)
        cur[0] += d + gap

    dot(9, 'white', F.GREY2, 0.7)
    word('First post')
    dot(K * 50, F.GREY2)
    word('Fifth post', gap=4.0)
    word('Posts, last 12 months', gap=1.2)
    for v in (10, 50, 100):
        dot(K * v, F.GREY2)
        word(str(v), gap=1.8)
    cur[0] += 2.2
    dot(K * 25, F.ROSE)
    word('AI title')
    dot(K * 25, BLUE)
    word('Data title')
    F.save(fig, OUT, 'fig4_hn_first_appearance')


if __name__ == '__main__':
    F.setup()
    fig3()
    fig4()
