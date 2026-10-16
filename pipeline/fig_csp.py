# -*- coding: utf-8 -*-
"""French public sector (Choisir le Service Public), January 2022 - September 2026.

fig9_csp_public_sector  a: AI mentions per 10 000 postings: monthly bars, 3-month centred mean, linear trends before and
                           after November 2022, annual means; b: the ten most frequent canonical AI and data titles.

Usage: python pipeline/fig_csp.py <project root>
"""
import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figstyle as F  # noqa: E402
import lexicon as LX  # noqa: E402

ROOT = sys.argv[1]
RES = os.path.join(ROOT, 'data-lake', 'lake', 'results')
OUT = os.path.join(ROOT, 'research-paper', 'fig')

CHATGPT = 2022 + 11 / 12    # 30 November 2022
BLUE = '#2b8fd6'            # data titles
PT = 72 / 25.4              # points per mm
MINUS = '−'

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


def group_colour(family):
    if family.startswith('Data'):
        return BLUE
    if family.startswith(('AI', 'ML')):
        return F.ROSE
    return F.GREY2


def num(v):
    return f'{v:.1f}' if v < 10 else f'{v:.0f}'


def per_year(s):
    return f'{"+" if s >= 0 else MINUS}{abs(s):.1f} per year'


def main():
    cm = pd.read_csv(os.path.join(RES, 'csp_monthly.csv'), index_col=0)
    cm = cm[cm.n >= 2000]
    months = pd.period_range(cm.index[0], cm.index[-1], freq='M').strftime('%Y-%m')
    rate = (1e4 * cm.ai / cm.n).reindex(months)
    m3 = rate.rolling(3, center=True, min_periods=1).mean().values
    x = np.array([mx(m) for m in months])
    v = rate.values
    ok = ~np.isnan(v)
    pre = np.array([m <= '2022-11' for m in months])
    xend = int(months[-1][:4]) + int(months[-1][5:7]) / 12          # end of the last month
    yearly = pd.read_csv(os.path.join(RES, 'csp_yearly.csv'), index_col=0).ai_per_10k
    cc = pd.read_csv(os.path.join(RES, 'csp_ai_canon.csv'), index_col=0).iloc[:, 0]
    cc = cc.drop('ai_other', errors='ignore').sort_values(ascending=False).head(10)

    FW, FH = 183, 62
    B, T = 8.5, 4.3
    H = FH - B - T
    La, Wa = 12.5, 86.0
    Lb, Wb = 138.5, 41.5
    fig = plt.figure(figsize=(FW / 25.4, FH / 25.4))
    axa = F.axes_mm(fig, La, B, Wa, H, FW, FH)
    axb = F.axes_mm(fig, Lb, B, Wb, H, FW, FH)

    # a: AI mentions per 10 000 postings
    ymax = 36
    ppu = H * PT / ymax                                             # points per data unit
    axa.bar(x, v, width=0.8 / 12, color=F.GREY, lw=0, zorder=1)
    axa.axvline(CHATGPT, color=F.GREY2, lw=0.5, zorder=0.5)
    fits = []
    for mask in (pre & ok, ~pre & ok):
        slope, icpt = np.polyfit(x[mask], v[mask], 1)
        xs = np.array([x[mask][0], x[mask][-1]])
        axa.plot(xs, icpt + slope * xs, color=F.SLATE, lw=0.8, zorder=3, solid_capstyle='butt')
        fits.append((slope, icpt))
    axa.plot(x, m3, color=F.ROSE, lw=1.0, zorder=4)
    F.label_end(axa, x[-1], m3[-1], '3-month\nmean', color=F.ROSE, dx=5)
    for (slope, icpt), xa, ylab, word in ((fits[0], 2022.45, 16.0, 'trend before'), (fits[1], 2023.3, 21.5, 'trend after')):
        ya = icpt + slope * xa
        F.leader(axa, (xa, ya), (0, (ylab - ya) * ppu), f'{word}\n{per_year(slope)}', color=F.SLATE,
                 ha='center', va='bottom')
    axa.text(CHATGPT + 0.04, 31.0, 'ChatGPT', fontsize=6, color=F.MUTED, ha='left', va='center')
    ytop = 34.6
    axa.text(2022.03, ytop, 'Mean', fontsize=6, color=F.MUTED, ha='left', va='center')
    years = list(range(2022, int(np.ceil(xend))))
    centres = [(y + min(y + 1, xend)) / 2 for y in years]
    for y, c in zip(years, centres):
        if y in yearly.index:
            axa.text(c, ytop, num(yearly[y]), fontsize=6, color=F.INK, ha='center', va='center')
    axa.set_xlim(2022, xend)
    axa.set_xticks(years)
    axa.set_xticklabels([])
    axa.set_xticks(centres, minor=True)
    axa.set_xticklabels([str(y) for y in years], minor=True)
    axa.tick_params(axis='x', which='minor', length=0, pad=4.5)
    axa.set_ylim(0, ymax)
    axa.set_yticks([0, 10, 20, 30])
    axa.set_ylabel(f'AI mentions (per {F.thousands(10000)} postings)')

    # b: canonical titles
    yb = np.arange(len(cc))
    axb.barh(yb, cc.values, height=0.62, color=[group_colour(LX.CANON_FAMILY.get(c, '')) for c in cc.index], lw=0)
    for i, val in enumerate(cc.values):
        F.label_end(axb, val, i, f'{int(val)}', color=F.MUTED, dx=2, fontsize=6)
    axb.set_yticks(yb)
    axb.set_yticklabels([SHORT.get(c, c) for c in cc.index])
    axb.tick_params(axis='y', length=0)
    axb.set_ylim(len(cc) - 0.5, -0.5)
    axb.set_xlim(0, 760)
    axb.set_xticks([0, 200, 400, 600])
    axb.set_xlabel('Postings, 2022–2026')
    axb.text(0.98, 0.17, 'AI title', transform=axb.transAxes, ha='right', va='center', fontsize=6, color=F.ROSE)
    axb.text(0.98, 0.07, 'Data title', transform=axb.transAxes, ha='right', va='center', fontsize=6, color=BLUE)

    F.panel(fig, axa, 'a', dx=(3.2 - La) / FW, dy=0.8 / FH)
    F.panel(fig, axb, 'b', dx=(112.0 - Lb) / FW, dy=0.8 / FH)
    F.save(fig, OUT, 'fig9_csp_public_sector')


if __name__ == '__main__':
    F.setup()
    main()
