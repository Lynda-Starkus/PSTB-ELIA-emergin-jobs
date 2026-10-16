# -*- coding: utf-8 -*-
"""Journal figure style for the ELIA paper (matplotlib).

Design contract (Nature / Science conventions):
  * Arial 7 pt, tick labels 6 pt, panel letters bold lowercase 8 pt outside the top-left corner.
  * No titles inside panels (the caption carries the title); sentence-case axis labels with units.
  * Only left and bottom spines, 0.5 pt, ticks outward; no gridlines; zero-based bars and areas.
  * Fixed semantic colours: AI mention = violet, AI title = rose, technology = slate, everything else = light grey;
    teal and amber only when a third/fourth category is unavoidable. No gradients, no shadows, no rounded bars.
  * Direct labels at line/bar ends instead of legends; legends only above four series, frameless.
  * Annotations are rare (at most two per panel), thin leader lines, no boxes.
  * Widths: single column 89 mm, double column 183 mm. Output PDF (Type 42 fonts) + PNG 600 dpi + SVG.
"""
import os, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

MM = 1 / 25.4
W1, W2 = 89 * MM, 183 * MM

# semantic colours
VIOLET = '#6520ff'   # AI mentioned anywhere
ROSE = '#e8103f'     # AI in the job title
SLATE = '#475569'    # technology jobs / baseline
GREY = '#c9cdd8'     # all other postings / context
GREY2 = '#9ba1b7'
TEAL = '#009B72'
AMBER = '#E08600'
INK = '#1a1a24'
MUTED = '#6b7280'
HAIR = '#d9dce3'
VIOLET_L = '#ddd3ff'; ROSE_L = '#ffd6de'; SLATE_L = '#cfd5de'

STAGE = {'appearing': ROSE, 'diffusing': VIOLET, 'established': SLATE, 'fading': AMBER, 'intermittent': GREY2, 'too rare': GREY, 'renamed': '#8a3b8f'}
FAMILY = {  # title families: two hues (AI = rose scale, data = blue scale) plus grey
    'AI engineering (new titles)': '#b3002d', 'AI engineering': ROSE, 'ML engineering': '#ff7a93', 'AI research': '#ffb3c1',
    'AI architecture & leadership': '#3b1fa3', 'AI business roles': VIOLET, 'AI governance & ethics': TEAL, 'AI training & data labelling': AMBER,
    'Data science': '#1f6aa5', 'Data engineering': '#2b8fd6', 'Data analytics': '#8fc3ea', 'Data leadership': SLATE, 'Other AI-labelled': GREY,
}

def setup():
    fam = 'Arial' if any(f.name == 'Arial' for f in font_manager.fontManager.ttflist) else 'DejaVu Sans'
    plt.rcParams.update({
        'font.family': fam, 'font.size': 7, 'axes.labelsize': 7, 'xtick.labelsize': 6, 'ytick.labelsize': 6, 'legend.fontsize': 6,
        'axes.titlesize': 7, 'axes.titleweight': 'normal',
        'axes.edgecolor': '#333333', 'axes.linewidth': 0.5, 'axes.labelcolor': INK, 'text.color': INK,
        'xtick.color': '#333333', 'ytick.color': '#333333', 'xtick.major.width': 0.5, 'ytick.major.width': 0.5,
        'xtick.major.size': 2.5, 'ytick.major.size': 2.5, 'xtick.direction': 'out', 'ytick.direction': 'out', 'xtick.major.pad': 2, 'ytick.major.pad': 2,
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': False, 'axes.axisbelow': True,
        'legend.frameon': False, 'legend.handlelength': 1.2, 'legend.handletextpad': 0.5, 'legend.borderaxespad': 0.2,
        'lines.linewidth': 1.0, 'lines.solid_capstyle': 'round', 'patch.linewidth': 0,
        'figure.dpi': 110, 'savefig.dpi': 600, 'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
        'axes.formatter.use_mathtext': False, 'mathtext.default': 'regular',
    })

def save(fig, outdir, name):
    os.makedirs(outdir, exist_ok=True)
    for ext in ('pdf', 'png', 'svg'):
        fig.savefig(os.path.join(outdir, f'{name}.{ext}'), facecolor='white')
    plt.close(fig); print('saved', name)

def panel(fig, ax, letter, dx=-0.012, dy=0.004):
    """Bold lowercase panel letter outside the top-left corner of an axes (figure coordinates)."""
    b = ax.get_position()
    fig.text(b.x0 + dx, b.y1 + dy, letter, fontsize=8, fontweight='bold', ha='right', va='bottom', color=INK)

def clean(ax, left=True, bottom=True):
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(left); ax.spines['bottom'].set_visible(bottom)
    if not left: ax.tick_params(axis='y', length=0)
    if not bottom: ax.tick_params(axis='x', length=0)

def thousands(n):
    """1 075 585 with thin spaces (French / SI style)."""
    return f'{int(round(n)):,}'.replace(',', ' ')

def label_end(ax, x, y, text, color=INK, dx=3, fontsize=6.5, weight='normal', va='center'):
    """Direct label at the end of a line (offset in points)."""
    ax.annotate(text, (x, y), xytext=(dx, 0), textcoords='offset points', color=color, fontsize=fontsize, va=va, ha='left', fontweight=weight, annotation_clip=False)

def leader(ax, xy, xytext, text, color=MUTED, fontsize=6, ha='left', va='center'):
    ax.annotate(text, xy, xytext=xytext, textcoords='offset points', fontsize=fontsize, color=color, ha=ha, va=va,
                arrowprops=dict(arrowstyle='-', color=color, lw=0.5, shrinkA=0, shrinkB=1.5), annotation_clip=False)

def axes_mm(fig, x, y, w, h, fw, fh):
    """Axes placed in millimetres from the bottom-left of a figure of size fw x fh (mm)."""
    return fig.add_axes([x / fw, y / fh, w / fw, h / fh])

def wilson(k, n, z=1.96):
    import numpy as np
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); s = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - s) / d, (c + s) / d
