# -*- coding: utf-8 -*-
"""Figure 12 - skill content of AI postings (183 x 125 mm, panels a-d).

a  France Travail 2026: share of postings citing at least one skill of each of the ten families, four segments per family
   (one dot per segment, thin grey line from the lowest to the highest segment); families sorted by the AI-core value.
b  France Travail 2026: dumbbell AI engineer (rose) vs data scientist (blue), families sorted by the AI-engineer value.
c  Hacker News AI posts 2015-2026: six small multiples, one family each, shared y 0-100 %, ChatGPT hairline.
d  Co-occurrence network of the 30 most cited skills in French AI postings: node area = postings, colour = family group,
   edges = Jaccard similarity >= 0.18 (width proportional). Spring layout (k = 1.2, 500 iterations) on the Jaccard graph,
   then an iterative repulsion of node + label footprints and a greedy choice of the label side, clamped to the panel;
   the seed with the cleanest result is kept.

Usage: python pipeline/fig_skills.py <project root>
"""
import sys, os, itertools, numpy as np, pandas as pd, networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.text import Text
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figstyle as F, skills as S

F.setup()
root = sys.argv[1]
res = os.path.join(root, 'data-lake', 'lake', 'results'); out = os.path.join(root, 'research-paper', 'fig')
FAM = S.FAMILIES
SHORT = {'AI/ML modelling': 'AI/ML modelling', 'Generative AI & LLM': 'Generative AI & LLM', 'Data engineering': 'Data engineering',
         'Software engineering': 'Software engineering', 'Cloud, DevOps & MLOps': 'Cloud, DevOps & MLOps', 'Data analysis & BI': 'Data analysis & BI',
         'Governance, ethics & regulation': 'Governance & ethics', 'Product & project': 'Product & project',
         'Domain & business': 'Domain & business', 'Transversal & languages': 'Transversal & languages'}
BLUE = F.FAMILY['Data science']
CHATGPT = 2022 + 10 / 12            # 1 November 2022 on a decimal-year axis
PT = 25.4 / 72                      # mm per point
pct = lambda v: f'{v:.1f}' if v < 10 else f'{v:.0f}'

# ---------------- data ----------------
seg = pd.read_csv(os.path.join(res, 'skills_profile_by_segment.csv')).set_index('segment')
can = pd.read_csv(os.path.join(res, 'skills_profile_by_canon_ft.csv')).set_index('canon')
hny = pd.read_csv(os.path.join(res, 'skills_profile_hn_ai_by_year.csv')).set_index('year')
M = pd.read_csv(os.path.join(res, 'skills_cooccurrence_ai_ft.csv'), index_col=0)

# ---------------- canvas (mm) ----------------
FW, FH = 183, 125
fig = plt.figure(figsize=(FW * F.MM, FH * F.MM), dpi=600)   # text is measured at the resolution of the saved PNG
REN = fig.canvas.get_renderer(); PX = 25.4 / fig.dpi


def bbox_mm(a):
    """Bounding box of an artist in figure millimetres (x0, y0, x1, y1)."""
    b = a.get_window_extent(REN)
    return np.array([b.x0, b.y0, b.x1, b.y1]) * PX


def data_mm(ax, x, y):
    return np.asarray(ax.transData.transform((x, y))) * PX


def ov(b1, b2, pad=0.3):
    """Overlap area (mm2) of two boxes, each grown by pad/2."""
    w = min(b1[2], b2[2]) - max(b1[0], b2[0]) + pad; h = min(b1[3], b2[3]) - max(b1[1], b2[1]) + pad
    return w * h if (w > 0 and h > 0) else 0.0


AX_Y, AX_H = 71, 47
A = F.axes_mm(fig, 28, AX_Y, 58, AX_H, FW, FH)
B = F.axes_mm(fig, 123, AX_Y, 55, AX_H, FW, FH)
NR = len(FAM)
Y_LO, BAND_MM = -0.7, 6.4                     # rows 0..NR-1, band above the first row for its direct labels
ROW_MM = (AX_H - BAND_MM) / (NR - 1 - Y_LO)
Y_HI = NR - 1 + BAND_MM / ROW_MM


def dodge(xs, thr, step):
    """Vertical offsets (row units) for dots closer than thr on x; within a cluster the first series stays on top."""
    order = np.argsort(xs, kind='stable'); off = np.zeros(len(xs)); groups = [[order[0]]]
    for a, b in zip(order[:-1], order[1:]):
        if xs[b] - xs[a] < thr: groups[-1].append(b)
        else: groups.append([b])
    for g in groups:
        if len(g) > 1:
            for n, k in enumerate(sorted(g)): off[k] = ((len(g) - 1) / 2 - n) * step
    return off


def rows_panel(ax, V, colors, order, xmax, ms, width_mm):
    """One row per family; one dot per series; thin grey line from the lowest to the highest value."""
    x_lo = -2.6 * xmax / 80
    ax.set_xlim(x_lo, xmax); ax.set_ylim(Y_LO, Y_HI)
    mmpp = width_mm / (xmax - x_lo); d_mm = ms * PT
    thr, step = (d_mm + 0.3) / mmpp, (d_mm + 0.3) / ROW_MM
    for r, i in enumerate(order):
        y = NR - 1 - r; v = V[i]
        ax.plot([v.min(), v.max()], [y, y], color=F.GREY, lw=0.8, solid_capstyle='butt', zorder=1)
        off = dodge(v, thr, step)
        for k in range(len(v)):
            ax.plot(v[k], y + off[k], 'o', ms=ms, mfc=colors[k], mec='white', mew=0.4, zorder=4 - 0.1 * k, clip_on=False)
    ax.set_yticks([NR - 1 - r for r in range(NR)]); ax.set_yticklabels([SHORT[FAM[i]] for i in order])
    F.clean(ax, left=False); ax.tick_params(axis='y', pad=1.5)
    ax.spines['bottom'].set_bounds(0, xmax); ax.set_xticks(np.arange(0, xmax + 1, 20))
    ax.set_xlabel('Postings citing the family (%)', labelpad=2)


# ---------------- a: skill families x segments ----------------
SEGS = [('AI-core (title)', 'AI-core', 'AI-core', F.ROSE), ('AI-related tech', 'AI-related tech', 'AI-related\ntech', F.VIOLET),
        ('Other tech', 'Other tech', 'Other\ntech', F.SLATE), ('AI mention, non-tech', 'AI mention, non-tech', 'AI mention,\nnon-tech', F.AMBER)]
VA = np.array([[100 * seg.loc[s[0], f] for s in SEGS] for f in FAM])
oa = list(np.argsort(-VA[:, 0], kind='stable'))
MS_A = 3.6
rows_panel(A, VA, [s[3] for s in SEGS], oa, 80, MS_A, 58)
# direct labels on the first row: left-aligned at each dot, wrapped onto two lines when the next label is too close
xs = VA[oa[0]]; y0 = NR - 1; r_mm = MS_A * PT / 2; srt = list(np.argsort(xs))
starts = [data_mm(A, xs[k], y0)[0] - r_mm for k in srt]
for n, k in enumerate(srt):
    limit = starts[n + 1] - 0.9 if n + 1 < len(srt) else data_mm(A, 80, y0)[0] + 3
    for txt in (SEGS[k][1], SEGS[k][2]):
        t = A.annotate(txt, (xs[k], y0), xytext=(-r_mm / PT, 3.4), textcoords='offset points', ha='left', va='bottom',
                       fontsize=6, color=SEGS[k][3], linespacing=1.0, annotation_clip=False)
        if bbox_mm(t)[2] <= limit or txt == SEGS[k][2]: break
        t.remove()

# ---------------- b: AI engineer vs data scientist ----------------
ROLES = [('ai_engineer', 'AI engineer', F.ROSE), ('data_scientist', 'Data scientist', BLUE)]
VB = np.array([[100 * can.loc[r[0], f] for r in ROLES] for f in FAM])
ob = list(np.argsort(-VB[:, 0], kind='stable'))
MS_B = 4.0
rows_panel(B, VB, [r[2] for r in ROLES], ob, 100, MS_B, 55)
xs = VB[ob[0]]; lo, hi = np.argsort(xs); r_pt = MS_B / 2
B.annotate(ROLES[lo][1], (xs[lo], y0), xytext=(r_pt, 3.4), textcoords='offset points', ha='right', va='bottom', fontsize=6, color=ROLES[lo][2])
B.annotate(ROLES[hi][1], (xs[hi], y0), xytext=(-r_pt, 3.4), textcoords='offset points', ha='left', va='bottom', fontsize=6, color=ROLES[hi][2])

# ---------------- c: international AI posts by year, small multiples ----------------
CX0, CW, CG = 11, 23, 5.0
CROWS = [(33.5, 20.0), (8.0, 20.0)]                       # (bottom, height) of the two rows
CF = [('AI/ML modelling', 'AI/ML modelling'), ('Generative AI & LLM', 'Generative AI & LLM'), ('Cloud, DevOps & MLOps', 'Cloud/DevOps/MLOps'),
      ('Data engineering', 'Data engineering'), ('Software engineering', 'Software engineering'), ('Governance, ethics & regulation', 'Governance')]
yrs = [int(y) for y in hny.index if 2015 <= int(y) <= 2026]; X = np.array(yrs) + 0.5
CAX = []
for n, (f, lab) in enumerate(CF):
    i, j = divmod(n, 3)
    ax = F.axes_mm(fig, CX0 + j * (CW + CG), CROWS[i][0], CW, CROWS[i][1], FW, FH); CAX.append(ax)
    v = 100 * hny.loc[yrs, f].values.astype(float)
    ax.plot([CHATGPT, CHATGPT], [0, 100], color=F.MUTED, lw=0.5, ls=(0, (1.5, 2)), zorder=1)
    ax.plot(X, v, color=F.VIOLET, lw=1.0, zorder=3)
    ax.plot(X[-1], v[-1], 'o', ms=2.2, color=F.VIOLET, mew=0, zorder=4, clip_on=False)
    ax.annotate(pct(v[-1]), (X[-1], v[-1]), xytext=(2.2, 0), textcoords='offset points', fontsize=6, color=F.VIOLET, ha='left', va='center', annotation_clip=False)
    ax.set_xlim(2015, 2027); ax.set_ylim(0, 128); ax.spines['left'].set_bounds(0, 100)
    ax.set_yticks([0, 50, 100]); ax.set_yticklabels(['0', '50', '100'] if j == 0 else [])
    ax.set_xticks([2015.5, 2020.5, 2025.5]); ax.set_xticklabels(['2015', '2020', '2025'] if i == 1 else [])
    ax.text(2015.3, 128, lab, fontsize=6, color=F.INK, ha='left', va='top')
    if f == 'Generative AI & LLM':
        ax.text(CHATGPT - 0.35, 97, 'ChatGPT', fontsize=6, color=F.MUTED, ha='right', va='top')
fig.text(3.2 / FW, (CROWS[1][0] + CROWS[0][0] + CROWS[0][1]) / 2 / FH, 'Posts citing the family (%)', rotation=90, ha='center', va='center', fontsize=7)

# ---------------- d: co-occurrence network ----------------
DX0, DY0, DW, DH = 96, 3, 85, 52.5
D = F.axes_mm(fig, DX0, DY0, DW, DH, FW, FH); D.set_xlim(0, DW); D.set_ylim(0, DH); D.axis('off')
EN = {'cybersécurité': 'Cybersecurity', 'réseaux': 'Networking', 'amélioration continue': 'Continuous improvement', 'veille': 'Trend watch',
      'python': 'Python', 'rédaction': 'Writing', 'rh': 'HR', 'agile': 'Agile', 'crm': 'CRM', 'ia générative': 'Generative AI', 'devops': 'DevOps',
      'curiosité': 'Curiosity', 'fiabilité': 'Reliability', 'négociation': 'Negotiation', 'ci/cd': 'CI/CD', 'sql': 'SQL', 'coaching': 'Coaching',
      'travail en équipe': 'Teamwork', 'pédagogie': 'Teaching', 'azure': 'Azure', 'défense': 'Defence', 'marketing digital': 'Digital marketing',
      'veille technologique': 'Tech watch', 'llm': 'LLM', 'aéronautique': 'Aeronautics', 'conduite du changement': 'Change management',
      'machine learning': 'Machine learning', 'logistique': 'Logistics', 'modélisation': 'Modelling', 'chatgpt': 'ChatGPT',
      'relation client': 'Customer relations', 'docker': 'Docker', 'gestion de projet': 'Project management', 'aws': 'AWS',
      'sens du service': 'Service orientation', 'comptabilité': 'Accounting', 'monitoring': 'Monitoring', 'java': 'Java',
      'développement logiciel': 'Software development', 'git': 'Git', 'chef de projet': 'Project lead', 'copilot': 'Copilot', 'r&d': 'R&D',
      'rag': 'RAG', 'spécifications': 'Specifications', 'kubernetes': 'Kubernetes', 'gestion des risques': 'Risk management',
      'programmation': 'Programming', 'mise en production': 'Deployment', 'assurance': 'Insurance', 'présentation': 'Presentation',
      'recommandation': 'Recommendation', 'banque': 'Banking', 'gcp': 'GCP', 'agents ia': 'AI agents', "esprit d'analyse": 'Analytical mind',
      'roadmap': 'Roadmap', 'power bi': 'Power BI', 'rgpd': 'GDPR', 'encadrement': 'Team management'}
GROUP = {'Generative AI & LLM': 0, 'AI/ML modelling': 1, 'Software engineering': 2, 'Cloud, DevOps & MLOps': 2, 'Data engineering': 2,
         'Data analysis & BI': 2, 'Product & project': 3, 'Domain & business': 3, 'Governance, ethics & regulation': 3, 'Transversal & languages': 4}
GCOL = [F.ROSE, F.VIOLET, F.SLATE, F.GREY2, F.GREY]
GLAB = ['Generative AI & LLM', 'AI/ML modelling', 'Software, data & cloud', 'Product, domain & business', 'Transversal & languages']
EDGE_COL, J_EDGE, J_LAYOUT = '#d6d9e0', 0.18, 0.08
NT = 30
terms = list(M.index[:NT]); Mt = M.loc[terms, terms].values.astype(float); cnt = np.diag(Mt).copy()
Jm = Mt / (cnt[:, None] + cnt[None, :] - Mt); np.fill_diagonal(Jm, 0)
grp = np.array([GROUP[S.TERM2FAM.get(t, 'Transversal & languages')] for t in terms])
names = [EN.get(t, t.capitalize()) for t in terms]
rad = 1.7 * np.sqrt(cnt / cnt.max())                       # node radius (mm): area proportional to postings
edges = [(a, b) for a in range(NT) for b in range(a + 1, NT) if Jm[a, b] >= J_EDGE]
GL = nx.Graph(); GL.add_nodes_from(range(NT))             # layout graph: weaker ties too, so that no node floats free
for a in range(NT):
    for b in range(a + 1, NT):
        if Jm[a, b] >= J_LAYOUT: GL.add_edge(a, b, w=Jm[a, b])
for a in range(NT):
    b = int(np.argmax(Jm[a])); GL.add_edge(a, b, w=Jm[a, b])

KEY_TOP = 9.0                                              # the colour key occupies the strip below this height (panel mm)
BX0, BX1, BY0, BY1 = 4.0, DW - 4.0, KEY_TOP + 3.0, DH - 2.5    # initial box of the node centres
LX0, LX1, LY0, LY1 = 0.3, DW - 0.8, KEY_TOP, DH - 0.2      # nodes and labels stay inside this box
GAMMA, RANK = 0.6, 0.3                                     # radial compression and rank blending of the spring layout
GAP_L, MX, MY = 0.6, 1.0, 0.35                             # node-label gap; horizontal and vertical footprint margins (mm)
CLEAR = 1.0                                                # an edge must pass at least this far (mm) from a disc it does not join
LW = np.zeros(NT); LH = np.zeros(NT)
for i, s in enumerate(names):
    t = D.text(0, 0, s, fontsize=5.5); b = bbox_mm(t); LW[i], LH[i] = b[2] - b[0], b[3] - b[1]; t.remove()
# label positions around a node: unit x, unit y, horizontal anchor (0 left .. 1 right), vertical anchor, preference cost
CANDS = np.array([(1, 0, 0.0, 0.5, 0.00), (-1, 0, 1.0, 0.5, 0.05), (0, 1, 0.5, 0.0, 0.12), (0, -1, 0.5, 1.0, 0.12),
                  (0.72, 0.72, 0.0, 0.0, 0.25), (-0.72, 0.72, 1.0, 0.0, 0.25), (0.72, -0.72, 0.0, 1.0, 0.25), (-0.72, -0.72, 1.0, 1.0, 0.25)])
CDIR = CANDS[:, :2] / np.hypot(CANDS[:, 0], CANDS[:, 1])[:, None]
EA = np.array(edges, int).reshape(-1, 2); EJ = Jm[EA[:, 0], EA[:, 1]]
NBR = [[b if a == i else a for a, b in edges if i in (a, b)] for i in range(NT)]


def side_cost(P):
    """(NT, 8) preference for each label position: base preference + penalty for pointing towards the node's neighbours."""
    V = np.array([P[i] - (P[NBR[i]].mean(0) if NBR[i] else P.mean(0)) for i in range(NT)])
    V /= np.maximum(np.hypot(V[:, 0], V[:, 1]), 1e-6)[:, None]
    return CANDS[:, 4][None, :] + 0.35 * (1 - V @ CDIR.T)


def anchors(P, cand):
    c = CANDS[cand]; g = rad + GAP_L
    return P[:, 0] + c[:, 0] * g, P[:, 1] + c[:, 1] * g


def label_boxes(P, cand):
    c = CANDS[cand]; ax_, ay_ = anchors(P, cand)
    x0 = ax_ - c[:, 2] * LW; y0 = ay_ - c[:, 3] * LH
    return np.stack([x0, y0, x0 + LW, y0 + LH], 1)


def feet(P, cand):
    """Footprint of each node and its label: union of the disc box and the label box, padded by MX, MY."""
    Lb = label_boxes(P, cand)
    return np.stack([np.minimum(Lb[:, 0], P[:, 0] - rad) - MX, np.minimum(Lb[:, 1], P[:, 1] - rad) - MY,
                     np.maximum(Lb[:, 2], P[:, 0] + rad) + MX, np.maximum(Lb[:, 3], P[:, 1] + rad) + MY], 1)


def spread(P, cand, iters=1500):
    """Iterative repulsion of overlapping node + label footprints and of nodes grazed by an edge they do not belong to,
    clamped to the panel. Returns positions and the number of footprint overlaps left."""
    P = P.copy(); idx = np.arange(NT); tie = np.where(idx[:, None] > idx[None, :], 1.0, -1.0); age = np.zeros((NT, NT))
    for _ in range(iters):
        x0, y0, x1, y1 = feet(P, cand).T
        dx = np.minimum(x1[:, None], x1[None, :]) - np.maximum(x0[:, None], x0[None, :])
        dy = np.minimum(y1[:, None], y1[None, :]) - np.maximum(y0[:, None], y0[None, :])
        hit = (dx > 0) & (dy > 0); np.fill_diagonal(hit, False)
        e_i, k_i, deficit, nrm = near_misses(P)
        if not hit.any() and not len(e_i): return P, 0
        if len(e_i):                                       # move the grazed node off the edge, the edge slightly the other way
            mv = 0.25 * deficit[:, None] * nrm; np.add.at(P, k_i, mv)
            np.add.at(P, EA[e_i, 0], -0.15 * mv); np.add.at(P, EA[e_i, 1], -0.15 * mv)
        age = np.where(hit, age + 1, 0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        sx = np.sign(cx[:, None] - cx[None, :]); sx = np.where(sx == 0, tie, sx)
        sy = np.sign(cy[:, None] - cy[None, :]); sy = np.where(sy == 0, tie, sy)
        vert = dy < dx                                     # separate along the cheaper direction ...
        stuck = age > 300                                  # ... or along both when a pair stays blocked (e.g. by the frame)
        P[:, 0] += 0.3 * np.where(hit & (~vert | stuck), dx * sx, 0).sum(1)
        P[:, 1] += 0.3 * np.where(hit & (vert | stuck), dy * sy, 0).sum(1)
        off = feet(P, cand) - np.c_[P, P]
        P[:, 0] = np.clip(P[:, 0], LX0 - off[:, 0], LX1 - off[:, 2]); P[:, 1] = np.clip(P[:, 1], LY0 - off[:, 1], LY1 - off[:, 3])
    return P, int(hit.sum() // 2)


def edge_points(P):
    t = np.linspace(0.04, 0.96, 30)[:, None]
    return np.vstack([P[a] + t * (P[b] - P[a]) for a, b in edges]) if edges else np.zeros((0, 2))


def box_cost(P, i, b, others, E, w_out=40.0):
    """Cost of label box b of node i: overlaps with other labels and with discs, leaving the panel, edges underneath.
    While positions are still being optimised (w_out small) a label outside the panel is cheap: spread() moves its node back in."""
    w = np.minimum(b[2], others[:, 2]) - np.maximum(b[0], others[:, 0]) + 0.3
    h = np.minimum(b[3], others[:, 3]) - np.maximum(b[1], others[:, 1]) + 0.3
    lab = (np.clip(w, 0, None) * np.clip(h, 0, None)).sum()
    cx = np.clip(P[:, 0], b[0], b[2]); cy = np.clip(P[:, 1], b[1], b[3]); pen = rad + 0.25 - np.hypot(P[:, 0] - cx, P[:, 1] - cy)
    out = max(0, LX0 - b[0]) + max(0, b[2] - LX1) + max(0, LY0 - b[1]) + max(0, b[3] - LY1)
    under = ((E[:, 0] > b[0]) & (E[:, 0] < b[2]) & (E[:, 1] > b[1]) & (E[:, 1] < b[3])).sum()
    return 30 * lab + 12 * pen[pen > 0].sum() + w_out * out + 0.15 * under


def greedy(P, cand):
    """Node by node (largest first), keep the label position with the lowest cost given all the other labels."""
    cand = cand.copy(); E = edge_points(P); SC = side_cost(P)
    for i in np.argsort(-rad):
        others = np.delete(label_boxes(P, cand), i, 0); best = None
        for k in range(len(CANDS)):
            cc = cand.copy(); cc[i] = k
            cost = SC[i, k] + box_cost(P, i, label_boxes(P, cc)[i], others, E, w_out=0.25)
            if best is None or cost < best[0]: best = (cost, k)
        cand[i] = best[1]
    return cand


def crosses(p1, p2, p3, p4):
    d = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return d(p1, p2, p3) * d(p1, p2, p4) < 0 and d(p3, p4, p1) * d(p3, p4, p2) < 0


def near_misses(P):
    """Edges passing closer than CLEAR to a disc they do not join: edge index, node index, deficit (mm), unit normal edge -> node."""
    A_ = P[EA[:, 0]]; U = P[EA[:, 1]] - A_
    s = np.clip(((P[None] - A_[:, None]) * U[:, None]).sum(2) / (U ** 2).sum(1)[:, None], 0, 1)
    Dv = P[None] - (A_[:, None] + s[..., None] * U[:, None]); d = np.hypot(Dv[..., 0], Dv[..., 1])
    deficit = rad[None] + CLEAR - d
    mask = (deficit > 0) & (s > 0) & (s < 1); r_ = np.arange(len(EA)); mask[r_, EA[:, 0]] = False; mask[r_, EA[:, 1]] = False
    e_i, k_i = np.where(mask)
    return e_i, k_i, deficit[mask], Dv[mask] / np.maximum(d[mask], 1e-6)[:, None]


def clutter(P, margin=3.0):
    """Squared intrusion of nodes into a band of rad + margin around the edges they do not belong to (nodes sitting inside
    another cluster read as members of it)."""
    A_ = P[EA[:, 0]]; U = P[EA[:, 1]] - A_
    s = np.clip(((P[None] - A_[:, None]) * U[:, None]).sum(2) / (U ** 2).sum(1)[:, None], 0, 1)
    Q = A_[:, None] + s[..., None] * U[:, None]; d = np.hypot(P[None, :, 0] - Q[..., 0], P[None, :, 1] - Q[..., 1])
    mask = np.ones_like(d, bool); r_ = np.arange(len(EA)); mask[r_, EA[:, 0]] = False; mask[r_, EA[:, 1]] = False
    return (np.clip(rad[None] + margin - d, 0, None) ** 2 * mask).sum()


def evaluate(P, cand, P0, residual, parts=False):
    """Layout score (lower is better), calibrated by eye on rendered candidates."""
    Lb = label_boxes(P, cand); E = edge_points(P); SC = side_cost(P); deficit = near_misses(P)[2]
    c = {'labels': sum(SC[i, cand[i]] + box_cost(P, i, Lb[i], np.delete(Lb, i, 0), E) for i in range(NT)), 'residual': 0.3 * residual,
         'near': (8 + 10 * deficit[deficit > 0.1]).sum(),     # an edge grazing a third node reads as a link to it
         'clutter': clutter(P),
         'cross': 3.0 * sum(crosses(P[a], P[b], P[c_], P[d]) for (a, b), (c_, d) in itertools.combinations(edges, 2) if len({a, b, c_, d}) == 4),
         'length': 0.5 * (EJ * np.hypot(*(P[EA[:, 0]] - P[EA[:, 1]]).T)).sum(),    # strong ties should stay short
         'moved': 0.15 * np.hypot(*(P - P0).T).mean()}
    return {k: round(float(v), 1) for k, v in c.items()} if parts else sum(c.values())


def build(seed):
    pos = nx.spring_layout(GL, k=1.2, iterations=500, weight='w', seed=seed)
    P = np.array([pos[i] for i in range(NT)]); P -= P.mean(0)
    P = P @ np.linalg.svd(P, full_matrices=False)[2].T     # principal axis horizontal (the panel is wide)
    r = np.maximum(np.hypot(P[:, 0], P[:, 1]), 1e-9); P *= ((r / r.max()) ** (GAMMA - 1))[:, None]
    P = (P - P.min(0)) / np.ptp(P, 0)
    P = (1 - RANK) * P + RANK * P.argsort(0).argsort(0) / (NT - 1)   # spread dense clusters, keep the order on each axis
    P[:, 0] = BX0 + P[:, 0] * (BX1 - BX0); P[:, 1] = BY0 + P[:, 1] * (BY1 - BY0); P0 = P.copy()
    cand = side_cost(P).argmin(1)                          # first guess: label pointing away from the node's neighbours
    for _ in range(4):
        P, residual = spread(P, cand); cand = greedy(P, cand)
    P, residual = spread(P, cand)
    if os.environ.get('FIG12_DEBUG'): print(seed, evaluate(P, cand, P0, residual, parts=True))
    return P, cand, evaluate(P, cand, P0, residual), residual


runs = [(build(seed), seed) for seed in range(60)]
(P, cand, score, residual), SEED = min(runs, key=lambda r: r[0][2])
LB = label_boxes(P, cand); AX_, AY_ = anchors(P, cand)
HA = {0.0: 'left', 0.5: 'center', 1.0: 'right'}; VA_ = {0.0: 'bottom', 0.5: 'center', 1.0: 'top'}
print(f'network: seed {SEED}, score {score:.2f}, residual footprint overlaps {residual}, {len(edges)} edges drawn '
      f'(Jaccard >= {J_EDGE}), {sum(1 for i in range(NT) if all(i not in e for e in edges))} nodes without a drawn edge')
print('  best scores:', sorted(round(float(r[0][2]), 1) for r in runs)[:8])
for e, k, deficit in zip(*near_misses(P)[:3]):
    if deficit > 0.1: print(f'EDGE NEAR NODE: {names[EA[e, 0]]} - {names[EA[e, 1]]} passes {deficit:.2f} mm too close to {names[k]}')
print('  edge crossings:', sum(crosses(P[a], P[b], P[c], P[d]) for (a, b), (c, d) in itertools.combinations(edges, 2) if len({a, b, c, d}) == 4))
DL = []
for i in range(NT):
    D.add_patch(Circle(P[i], rad[i], fc=GCOL[grp[i]], ec='white', lw=0.4, zorder=3))
    c = CANDS[cand[i]]                                     # anchored on the side that faces the node
    DL.append(D.text(AX_[i], AY_[i], names[i], fontsize=5.5, ha=HA[c[2]], va=VA_[c[3]], color=F.INK, zorder=5))


def inside(p, q, b):
    """Parameter interval of the segment p -> q that lies inside box b (Liang-Barsky clipping), or None."""
    t0, t1 = 0.0, 1.0; d = q - p
    for pk, qk in ((-d[0], p[0] - b[0]), (d[0], b[2] - p[0]), (-d[1], p[1] - b[1]), (d[1], b[3] - p[1])):
        if pk == 0:
            if qk < 0: return None
        elif pk < 0: t0 = max(t0, qk / pk)
        else: t1 = min(t1, qk / pk)
    return (t0, t1) if t0 < t1 else None


# edges are interrupted where they pass under a label (same effect as a white halo, but the labels stay editable text)
TB = [bbox_mm(t) - np.array([DX0, DY0, DX0, DY0]) + np.array([-0.25, -0.05, 0.25, 0.05]) for t in DL]
for a, b in edges:
    cuts = sorted(iv for iv in (inside(P[a], P[b], bb) for bb in TB) if iv)
    pieces, t = [], 0.0
    for c0, c1 in cuts:
        if c0 > t: pieces.append((t, c0))
        t = max(t, c1)
    if t < 1: pieces.append((t, 1.0))
    L_ = np.hypot(*(P[b] - P[a]))
    for s0, s1 in pieces:
        visible = (s1 - s0) * L_ - (rad[a] if s0 == 0 else 0) - (rad[b] if s1 == 1 else 0)
        if visible < 0.6: continue                         # no stray stubs between a disc and a label
        p0, p1 = P[a] + s0 * (P[b] - P[a]), P[a] + s1 * (P[b] - P[a])
        D.plot([p0[0], p1[0]], [p0[1], p1[1]], color=EDGE_COL, lw=2.2 * Jm[a, b], solid_capstyle='butt', zorder=1)
# two-line colour key
present = set(grp.tolist())
for line, yk in (([0, 1, 2], 6.4), ([3, 4], 2.6)):
    x = 1.0
    for g in line:
        if g not in present: continue
        D.add_patch(Circle((x, yk), 0.85, fc=GCOL[g], ec='white', lw=0.3, zorder=3))
        t = D.text(x + 1.5, yk, GLAB[g], fontsize=6, va='center', ha='left', color=F.INK)
        x = bbox_mm(t)[2] - DX0 + 3.2


# ---------------- panel letters ----------------
def letter(ax, l, x_mm, y_mm):
    b = ax.get_position(); F.panel(fig, ax, l, dx=x_mm / FW - b.x0, dy=y_mm / FH - b.y1)


letter(A, 'a', 3.6, 119.4); letter(B, 'b', 97.6, 119.4); letter(CAX[0], 'c', 3.6, 55.9); letter(D, 'd', 97.6, 55.9)

# ---------------- audit: overlapping or clipped text, labels on nodes ----------------
fig.canvas.draw()
txt = [t for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()]
bbs = [bbox_mm(t) for t in txt]
for t, b in zip(txt, bbs):
    if b[0] < 0 or b[1] < 0 or b[2] > FW or b[3] > FH: print('CLIPPED:', repr(t.get_text()), b.round(1))
for i in range(len(txt)):
    for j in range(i + 1, len(txt)):
        if ov(bbs[i], bbs[j], pad=0.2) > 0: print('OVERLAP:', repr(txt[i].get_text()), '|', repr(txt[j].get_text()))
for i, t in enumerate(DL):                                  # rendered label boxes against node discs (panel mm)
    b = bbox_mm(t) - np.array([DX0, DY0, DX0, DY0]); cx = np.clip(P[:, 0], b[0], b[2]); cy = np.clip(P[:, 1], b[1], b[3])
    gap = np.hypot(P[:, 0] - cx, P[:, 1] - cy) - rad
    if gap.min() < 0.3: print(f'LABEL NEAR NODE: {names[i]} -> {names[int(gap.argmin())]} gap {gap.min():.2f} mm')
    if b[0] < LX0 - 0.05 or b[2] > LX1 + 0.05 or b[1] < LY0 - 0.05 or b[3] > LY1 + 0.05: print('LABEL OUTSIDE PANEL:', names[i], b.round(2))
F.save(fig, out, 'fig12_skills')
