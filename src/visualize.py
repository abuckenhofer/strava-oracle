"""visualize.py — Information-design visualizations for the Strava Oracle demo.

Generates one figure per SQL paradigm:
  fig_routes.png        — GPS traces colored by heart rate        (00_setup)
  fig_h3_heatmap.html   — Interactive hex density on real map tiles (01_spatial)
  fig_effort.png        — Cosine distance ranking                  (03_vector)
  fig_graph_a.png       — Movement network, hub cells highlighted  (04_graph)
  fig_hr_zones.png      — HR zone distribution per run             (06_relational)

All figures use a black background for publication contrast.

Usage:
    pip install pandas matplotlib numpy folium h3
    python src/visualize.py
"""

from pathlib import Path
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import folium
import branca.colormap as cm
import h3

# ── Paths & files ─────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'
FIG_DIR  = ROOT / 'figures'

CSV_FILES = sorted(f.name for f in DATA_DIR.glob('*.csv'))

_LABELS_KNOWN = {
    '2022_06_01_Lauf_am_Morgen_9.csv': 'Morgen 9 · Jun 2022',
    '2022_06_04_Lauf_am_Morgen_8.csv': 'Morgen 8 · Jun 2022',
    '2022_06_06_Lauf_am_Morgen_7.csv': 'Morgen 7 · Jun 2022',
    '2022_06_11_Lauf_am_Morgen_6.csv': 'Morgen 6 · Jun 2022',
    '2023_05_01_Lauf_am_Morgen_4.csv': 'Morgen 4 · May 2023',
    '2023_07_03_Lauf_am_Morgen_3.csv': 'Morgen 3 · Jul 2023',
    '2023_08_02_Lauf_am_Morgen_2.csv': 'Morgen 2 · Aug 2023',
    '2023_08_05_Lauf_am_Morgen_1.csv': 'Morgen 1 · Aug 2023',
    '2024_09_29_HM_Ulm_2024.csv':     'HM Ulm 2024',
    '2025_06_09_Lauf_am_Morgen_5.csv': 'Morgen 5 · Jun 2025',
    '2025_09_03_Intervall_3x2km.csv':  'Interval 3\u00d72 km',
    '2025_09_08_Morning_run_17km.csv':  'Morning 17 km',
    '2025_09_13_Saturday_Morning_Run.csv': 'Saturday Morning',
    '2025_09_24_Intervall_4x1km.csv':  'Interval 4\u00d71 km',
    '2025_09_28_HM_Ulm_2025.csv':     'HM Ulm 2025',
    '2025_11_05_Wednesday_Morning_Run_7km.csv': 'Wednesday 7 km',
    '2025_11_17_Monday_Morning_Run_4km.csv':    'Monday 4 km',
}

_MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

def _label(fname):
    if fname in _LABELS_KNOWN:
        return _LABELS_KNOWN[fname]
    stem = fname[:-4] if fname.endswith('.csv') else fname
    m = re.match(r'^(\d{4})_(\d{2})_\d{2}_(.*)', stem)
    if m:
        year, mon, rest = m.group(1), int(m.group(2)), m.group(3)
        return f'{rest.replace("_", " ")} · {_MONTHS[mon - 1]} {year}'
    return stem.replace('_', ' ')

# 17-colour palette — all readable on dark backgrounds
PAL = {
    '2022_06_01_Lauf_am_Morgen_9.csv': '#f87171',
    '2022_06_04_Lauf_am_Morgen_8.csv': '#fb923c',
    '2022_06_06_Lauf_am_Morgen_7.csv': '#fbbf24',
    '2022_06_11_Lauf_am_Morgen_6.csv': '#fde047',
    '2023_05_01_Lauf_am_Morgen_4.csv': '#a3e635',
    '2023_07_03_Lauf_am_Morgen_3.csv': '#4ade80',
    '2023_08_02_Lauf_am_Morgen_2.csv': '#34d399',
    '2023_08_05_Lauf_am_Morgen_1.csv': '#2dd4bf',
    '2024_09_29_HM_Ulm_2024.csv':     '#22d3ee',
    '2025_06_09_Lauf_am_Morgen_5.csv': '#38bdf8',
    '2025_09_03_Intervall_3x2km.csv':  '#60a5fa',
    '2025_09_08_Morning_run_17km.csv':  '#818cf8',
    '2025_09_13_Saturday_Morning_Run.csv': '#a78bfa',
    '2025_09_24_Intervall_4x1km.csv':  '#c084fc',
    '2025_09_28_HM_Ulm_2025.csv':     '#e879f9',
    '2025_11_05_Wednesday_Morning_Run_7km.csv': '#f472b6',
    '2025_11_17_Monday_Morning_Run_4km.csv':    '#fb7185',
}

HR_ZONE_COLS = ['#caf0f8', '#48cae4', '#f9c74f', '#f3722c', '#d00000']
HR_ZONE_TAGS = ['Z1 Easy', 'Z2 Aerobic', 'Z3 Tempo', 'Z4 Threshold', 'Z5 Max']

# ── Dark-mode colour tokens ────────────────────────────────────
BG   = '#111111'   # figure / axes background
FG   = '#e8e8e8'   # primary text / labels
DIM  = '#888888'   # secondary text / tick labels
EDGE = '#3a3a3a'   # axes spines


# ── Style ─────────────────────────────────────────────────────
def _style():
    plt.rcParams.update({
        'font.family':       'sans-serif',
        'font.sans-serif':   ['Inter', 'Helvetica Neue', 'Arial', 'DejaVu Sans'],
        'font.size':         10,
        'axes.titlesize':    12,
        'axes.titleweight':  'medium',
        'axes.spines.top':   False,
        'axes.spines.right': False,
        'axes.linewidth':    0.6,
        'axes.grid':         False,
        'figure.facecolor':  BG,
        'axes.facecolor':    BG,
        'text.color':        FG,
        'axes.labelcolor':   FG,
        'axes.edgecolor':    EDGE,
        'xtick.color':       DIM,
        'ytick.color':       DIM,
        'xtick.labelcolor':  DIM,
        'ytick.labelcolor':  DIM,
        'savefig.dpi':       300,
        'savefig.facecolor': BG,
    })


def _cb_dark(cb, label=''):
    """Apply dark-mode styling to a colorbar."""
    cb.ax.tick_params(colors=DIM, labelsize=8)
    cb.outline.set_edgecolor(EDGE)
    if label:
        cb.set_label(label, color=FG, fontsize=9)


# ── Data ──────────────────────────────────────────────────────
def load():
    frames = []
    for f in CSV_FILES:
        d = pd.read_csv(DATA_DIR / f, parse_dates=['ts'])
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def _runs_with_hr(df):
    """Return list of filenames that have at least some heart-rate data."""
    return [f for f in CSV_FILES
            if df.loc[(df['filename'] == f) & (df['heart_rate'] > 0),
                      'heart_rate'].any()]


# ── 1  Routes (00_setup) ─────────────────────────────────────
def fig_routes(df):
    """Small multiples: GPS traces (dynamic grid) + horizontal colorbar row."""
    NCOLS = 6
    NROWS = (len(CSV_FILES) + NCOLS - 1) // NCOLS

    # HR colour range from runs that have HR data
    hr_valid = df.loc[df['heart_rate'] > 0, 'heart_rate']
    if len(hr_valid) > 0:
        hr_lo = hr_valid.quantile(0.02)
        hr_hi = hr_valid.quantile(0.98)
    else:
        hr_lo, hr_hi = 80, 180
    norm = mcolors.Normalize(hr_lo, hr_hi)
    cmap = plt.cm.YlOrRd

    fig = plt.figure(figsize=(28, 4.5 * NROWS + 1.5), facecolor=BG)
    gs  = GridSpec(
        NROWS + 1, NCOLS,
        figure=fig,
        left=0.01, right=0.99,
        top=0.92, bottom=0.06,
        hspace=0.45, wspace=0.05,
        height_ratios=[1] * NROWS + [0.04],
    )

    for idx, fname in enumerate(CSV_FILES):
        row, col = divmod(idx, NCOLS)
        ax = fig.add_subplot(gs[row, col])
        ax.set_facecolor(BG)

        g       = df[df['filename'] == fname]
        cos_lat = np.cos(np.radians(g['latitude'].mean()))

        has_hr = g['heart_rate'].notna().any() and (g['heart_rate'] > 0).any()
        if has_hr:
            ax.scatter(g['longitude'], g['latitude'],
                       c=g['heart_rate'], cmap=cmap, norm=norm,
                       s=2, linewidths=0, rasterized=True)
        else:
            ax.plot(g['longitude'], g['latitude'],
                    color='#94a3b8', lw=0.5, alpha=0.7)

        ax.set_aspect(1 / cos_lat)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)

        dist_km = g['distance'].max()
        elapsed = (g['ts'].max() - g['ts'].min()).total_seconds()

        # Title: date only in DD-Mon-YYYY format
        m_d = re.match(r'^(\d{4})_(\d{2})_(\d{2})_', fname)
        if m_d:
            date_str = f'{int(m_d.group(3)):02d}-{_MONTHS[int(m_d.group(2))-1]}-{m_d.group(1)}'
        else:
            date_str = fname[:-4]
        ax.set_title(date_str, fontsize=8, pad=4, color=FG, fontweight='medium')

        dist_str = f'{dist_km:.1f} km' if pd.notna(dist_km) else '?'
        dur_str  = f'{int(elapsed // 60)} min'
        ax.text(0.5, -0.08, f'{dist_str} \u00b7 {dur_str}',
                transform=ax.transAxes, ha='center', fontsize=8.5, color='#cccccc')

    # Fill remaining blank slots
    for idx in range(len(CSV_FILES), NROWS * NCOLS):
        row, col = divmod(idx, NCOLS)
        ax_blank = fig.add_subplot(gs[row, col])
        ax_blank.set_facecolor(BG)
        ax_blank.axis('off')

    # Horizontal colorbar spanning all columns in the dedicated strip
    cax = fig.add_subplot(gs[NROWS, :])
    sm  = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb  = fig.colorbar(sm, cax=cax, orientation='horizontal')
    cb.set_label('Heart Rate (bpm)', color=FG, fontsize=10)
    cb.ax.tick_params(colors=DIM, labelsize=9)
    cb.outline.set_edgecolor(EDGE)

    fig.suptitle('GPS Routes \u2014 Colored by Heart Rate',
                 fontsize=15, fontweight='semibold', color=FG)

    fig.savefig(FIG_DIR / 'fig_routes.png', facecolor=BG,
                dpi=300, bbox_inches='tight', pad_inches=0.15)
    plt.close(fig)


# ── 2  H3 Heatmap (01_spatial) — H3 polygons on real tiles ───
def fig_h3_heatmap(df):
    """H3 hex polygons at resolution 11 on real map tiles (folium -> HTML + PNG)."""
    pts = df[df['latitude'].notna()]

    # ── Compute H3 cells and visit counts ──────────────────────
    cells = [
        h3.latlng_to_cell(lat, lon, 11)
        for lat, lon in zip(pts['latitude'], pts['longitude'])
    ]
    from collections import Counter
    cell_counts = Counter(cells)

    # ── Centre map on all data ────────────────────────────────
    center_lat = pts['latitude'].mean()
    center_lon = pts['longitude'].mean()

    # Pitch-black base (road lines present but no text labels)
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles='https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
        attr='© OpenStreetMap contributors © CARTO',
        zoom_control=False,
    )

    # ── Colour scale: bright yellow → deep blood-red ───────────
    max_count = max(cell_counts.values())
    colormap = cm.LinearColormap(
        colors=['#ffff33', '#ffc300', '#ff6600', '#cc0000', '#7f0000'],
        vmin=1, vmax=max_count,
        caption='visit_count  (samples per cell)',
    )

    # ── Draw H3 hexagonal polygons (80% opaque, 0.5 px border) ─
    for cell, count in cell_counts.items():
        boundary = h3.cell_to_boundary(cell)
        coords = [[lat, lng] for lat, lng in boundary]
        folium.Polygon(
            locations=coords,
            color='#1a1a1a',
            weight=0.5,
            fill=True,
            fill_color=colormap(count),
            fill_opacity=0.80,
        ).add_to(m)

    colormap.add_to(m)

    # ── Street-level labels ON TOP of hexagons (transparent overlay) ─
    # CartoDB dark_only_labels renders OSM street names / road labels
    # on a fully transparent background — no base map, just the text.
    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png',
        attr='© OpenStreetMap contributors © CARTO',
        subdomains='abcd',
        overlay=True,
        name='street labels',
    ).add_to(m)

    # ── Title overlay ──────────────────────────────────────────
    n_runs = df['filename'].nunique()
    title_html = f'''
    <div style="position:fixed; top:12px; left:12px;
                z-index:1000; background:rgba(17,17,17,0.85); color:#e8e8e8;
                padding:8px 16px; border-radius:8px; font-family:sans-serif;
                font-size:13px; font-weight:600; pointer-events:none;">
        Which streets do I run most often?<br>
        <span style="font-weight:400; font-size:12px; color:#aaa;">
            H3 resolution 11 (~25&thinsp;m cells) &mdash; all {n_runs} runs
        </span>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(title_html))

    html_path = FIG_DIR / 'fig_h3_heatmap.html'
    m.save(str(html_path))

    # ── Screenshot -> PNG via Edge headless ─────────────────────
    try:
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
        import time

        opts = Options()
        opts.add_argument('--headless=new')
        opts.add_argument('--window-size=1400,900')
        opts.add_argument('--force-device-scale-factor=2')  # retina-like
        driver = webdriver.Edge(options=opts)
        driver.get(html_path.as_uri())
        time.sleep(4)  # wait for tiles + polygons to render
        driver.save_screenshot(str(FIG_DIR / 'fig_h3_heatmap.png'))
        driver.quit()
    except Exception as exc:
        print(f'  Warning: PNG screenshot failed ({exc}); HTML saved OK')



# ── 4  Effort: cosine distance ranking (03_vector) ────────────
def _features(df, run_list):
    """11-dim effort signature per run (mirrors 03_vector.sql)."""
    raw = {}
    for fname in run_list:
        g   = df[df['filename'] == fname]
        hr  = g.loc[g['heart_rate'] > 0, 'heart_rate']
        spd = g.loc[g['speed'] > 0, 'speed']
        nh, ns = max(len(hr), 1), max(len(spd), 1)
        raw[fname] = dict(
            z1=(hr < 110).sum() / nh,
            z2=((hr >= 110) & (hr < 130)).sum() / nh,
            z3=((hr >= 130) & (hr < 150)).sum() / nh,
            z4=((hr >= 150) & (hr < 170)).sum() / nh,
            z5=(hr >= 170).sum() / nh,
            avg_spd=spd.mean() if len(spd) else 0,
            avg_hr=hr.mean() if len(hr) else 0,
            cv=spd.std() / spd.mean() if len(spd) and spd.mean() > 0 else 0,
            slow=(spd < 9.0).sum() / ns,
            mod=((spd >= 9.0) & (spd < 12.0)).sum() / ns,
            fast=(spd >= 12.0).sum() / ns,
        )

    mx_s = max((r['avg_spd'] for r in raw.values()), default=1) or 1
    mx_h = max((r['avg_hr']  for r in raw.values()), default=1) or 1

    vecs = {}
    for f in run_list:
        r = raw[f]
        vecs[f] = np.array([
            r['z1'], r['z2'], r['z3'], r['z4'], r['z5'],
            r['avg_spd'] / mx_s, r['avg_hr'] / mx_h, r['cv'],
            r['slow'], r['mod'], r['fast'],
        ])
    return vecs


def fig_effort(df):
    """Pairwise cosine-distance matrix — runs with HR data."""
    hr_runs = _runs_with_hr(df)
    if len(hr_runs) < 2:
        print('  skipped fig_effort (fewer than 2 runs with HR data)')
        return

    vecs = _features(df, hr_runs)
    nf   = len(hr_runs)
    va   = [vecs[f] for f in hr_runs]

    # Build symmetric distance matrix
    mat = np.zeros((nf, nf))
    for i in range(nf):
        for j in range(nf):
            dot = np.dot(va[i], va[j])
            nrm = np.linalg.norm(va[i]) * np.linalg.norm(va[j])
            mat[i, j] = max(0.0, 1 - dot / nrm) if nrm > 0 else 0.0

    labs = [_label(f) for f in hr_runs]

    fig, ax = plt.subplots(figsize=(max(9, nf * 0.9), max(7, nf * 0.7)))

    im = ax.imshow(mat, cmap='YlOrRd', vmin=0, aspect='equal')

    # Cell text
    thresh = mat.max() * 0.52
    fs = 8.5 if nf <= 10 else 7
    for i in range(nf):
        for j in range(nf):
            tc = 'white' if mat[i, j] > thresh else '#1a1a1a'
            ax.text(j, i, f'{mat[i, j]:.3f}',
                    ha='center', va='center', fontsize=fs, color=tc)

    lbl_fs = 8.5 if nf <= 10 else 7
    ax.set_xticks(range(nf))
    ax.set_xticklabels(labs, fontsize=lbl_fs, rotation=40, ha='right', color=FG)
    ax.set_yticks(range(nf))
    ax.set_yticklabels(labs, fontsize=lbl_fs, color=FG)
    ax.set_title('Pairwise cosine distance \u2014 lower = more similar effort',
                 fontsize=11, pad=12, color=FG)

    cb = fig.colorbar(im, ax=ax, shrink=0.72, pad=0.03)
    _cb_dark(cb, 'Cosine Distance')

    fig.tight_layout()
    fig.savefig(FIG_DIR / 'fig_effort.png', facecolor=BG,
                dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)


# ── 5  Graph: Movement Network (04_graph) ────────────────────

def _movement_network(df, cell_deg=0.002):
    """Derive H3-cell movement network from GPS sequences.

    Approximates H3 cells with a fixed-degree grid (~200 m at lat 48deg).
    Returns:
        nodes: {cell_key: {lat, lon, visit_count, out_degree, in_degree}}
        edges: {(src, dst): {count, avg_speed}}
    """
    pts = df[df['latitude'].notna()].copy()
    pts['cl']   = (pts['latitude']  / cell_deg).round().astype(int)
    pts['cn']   = (pts['longitude'] / cell_deg).round().astype(int)
    pts['cell'] = list(zip(pts['cl'], pts['cn']))

    node_visits = pts.groupby('cell').size().to_dict()
    node_lat    = pts.groupby('cell')['latitude'].mean().to_dict()
    node_lon    = pts.groupby('cell')['longitude'].mean().to_dict()

    edge_data = {}
    for fname in CSV_FILES:
        run    = pts[pts['filename'] == fname].sort_values('ts')
        cells  = run['cell'].tolist()
        speeds = run['speed'].fillna(0).tolist()
        for i in range(len(cells) - 1):
            src, dst = cells[i], cells[i + 1]
            if src != dst:
                key = (src, dst)
                if key not in edge_data:
                    edge_data[key] = {'count': 0, 'speeds': []}
                edge_data[key]['count'] += 1
                edge_data[key]['speeds'].append(speeds[i])

    edges = {k: {'count': v['count'], 'avg_speed': np.mean(v['speeds'])}
             for k, v in edge_data.items()}

    out_deg, in_deg = {}, {}
    for src, dst in edges:
        out_deg[src] = out_deg.get(src, 0) + 1
        in_deg[dst]  = in_deg.get(dst, 0) + 1

    nodes = {
        cell: {
            'lat':         node_lat[cell],
            'lon':         node_lon[cell],
            'visit_count': node_visits.get(cell, 0),
            'out_degree':  out_deg.get(cell, 0),
            'in_degree':   in_deg.get(cell, 0),
        }
        for cell in node_visits
    }
    return nodes, edges


def fig_graph_a(df):
    """Movement network on geographic canvas, top hub cells highlighted."""
    nodes, edges = _movement_network(df, cell_deg=0.002)

    # Bounding box: focus on the main running area.
    # Exclude geographically distant outlier runs (> ~15 km from median).
    pts = df[df['latitude'].notna()]
    run_centers = pts.groupby('filename').agg(
        mlat=('latitude', 'mean'), mlon=('longitude', 'mean')).reset_index()
    med_lat = run_centers['mlat'].median()
    med_lon = run_centers['mlon'].median()
    nearby = run_centers[
        (abs(run_centers['mlat'] - med_lat) < 0.15) &
        (abs(run_centers['mlon'] - med_lon) < 0.15)]
    focus_runs = nearby['filename'].tolist()
    focus_pts = pts[pts['filename'].isin(focus_runs)]
    pad = 0.008
    lon_lo = focus_pts['longitude'].min() - pad
    lon_hi = focus_pts['longitude'].max() + pad
    lat_lo = focus_pts['latitude'].min()  - pad
    lat_hi = focus_pts['latitude'].max()  + pad

    # Filter nodes and edges to the visible area
    nodes_in = {k: v for k, v in nodes.items()
                if lon_lo <= v['lon'] <= lon_hi and lat_lo <= v['lat'] <= lat_hi}
    edges_in = {(s, d): e for (s, d), e in edges.items()
                if s in nodes_in and d in nodes_in}

    # Top 10 hubs by out-degree, minimum degree 3 (genuine junctions only)
    top5 = [k for k in sorted(nodes_in, key=lambda k: nodes_in[k]['out_degree'],
                               reverse=True)
            if nodes_in[k]['out_degree'] >= 3][:10]
    top5_set = set(top5)

    max_visit = max((v['visit_count'] for v in nodes_in.values()), default=1)
    max_count = max((e['count'] for e in edges_in.values()), default=1)

    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_facecolor(BG)
    ax.axis('off')

    # Ghost route traces for geographic context (focus-area runs only)
    for fname in focus_runs:
        g = pts[pts['filename'] == fname].sort_values('ts')
        ax.plot(g['longitude'].values, g['latitude'].values,
                color='#ffffff', alpha=0.07, linewidth=0.5)

    # Edges: top 300 by count
    for (src, dst), edata in sorted(edges_in.items(),
                                    key=lambda x: x[1]['count'], reverse=True)[:300]:
        x0, y0 = nodes_in[src]['lon'], nodes_in[src]['lat']
        x1, y1 = nodes_in[dst]['lon'], nodes_in[dst]['lat']
        frac   = edata['count'] / max_count
        ax.plot([x0, x1], [y0, y1],
                color='#f5c518', linewidth=0.4 + 3.0 * frac,
                alpha=0.25 + 0.60 * frac, solid_capstyle='round', zorder=2)

    # Regular nodes
    non_hubs = [k for k in nodes_in if k not in top5_set]
    if non_hubs:
        ax.scatter([nodes_in[k]['lon'] for k in non_hubs],
                   [nodes_in[k]['lat'] for k in non_hubs],
                   s=[5 + 35 * nodes_in[k]['visit_count'] / max_visit for k in non_hubs],
                   color='#94a3b8', alpha=0.45, linewidths=0, zorder=3)

    # Hub nodes: amber fill + white ring
    if top5:
        ax.scatter([nodes_in[k]['lon'] for k in top5],
                   [nodes_in[k]['lat'] for k in top5],
                   s=[5 + 35 * nodes_in[k]['visit_count'] / max_visit for k in top5],
                   color='#e53935', edgecolors='#ffffff', linewidths=0.9,
                   alpha=0.95, zorder=6)

    ax.set_xlim(lon_lo, lon_hi)
    ax.set_ylim(lat_lo, lat_hi)

    ax.set_title('Which locations connect different parts of my running network?\n'
                 'Movement network \u2014 node size: visit count  \u00b7  '
                 'edge thickness: transition count',
                 fontsize=11, pad=14, color=FG)

    ax.legend(handles=[
        Line2D([0], [0], marker='o', color='none', markerfacecolor='#94a3b8',
               markersize=7, label='H3 cell  (size = visit count)'),
        Line2D([0], [0], marker='o', color='none', markerfacecolor='#e53935',
               markersize=9, markeredgecolor='#ffffff', markeredgewidth=0.9,
               label='Hub cell  (top 10 out-degree)'),
        Line2D([0], [0], color='#f5c518', linewidth=1.5, alpha=0.7,
               label='Transition  (thickness = count)'),
    ], loc='lower right', fontsize=9, frameon=True,
       facecolor='#1a1a1a', edgecolor=EDGE, labelcolor=FG)

    fig.tight_layout()
    fig.savefig(FIG_DIR / 'fig_graph_a.png', facecolor=BG,
                dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)


# ── 6  HR Zones (06_relational) ──────────────────────────────
def fig_hr_zones(df):
    """Horizontal stacked bars: % time in each HR zone per run (HR data only)."""
    hr_runs = _runs_with_hr(df)
    if not hr_runs:
        print('  skipped fig_hr_zones (no runs with HR data)')
        return

    fig, ax = plt.subplots(figsize=(10, max(5, len(hr_runs) * 0.55)))

    bins = [0, 110, 130, 150, 170, 9999]
    zone_data = {}
    for fname in hr_runs:
        hr = df.loc[(df['filename'] == fname) & (df['heart_rate'] > 0), 'heart_rate']
        counts = pd.cut(hr, bins=bins, right=False).value_counts(
            sort=False, normalize=True) * 100
        zone_data[fname] = counts.values

    y    = np.arange(len(hr_runs))
    left = np.zeros(len(hr_runs))

    for i, (col, tag) in enumerate(zip(HR_ZONE_COLS, HR_ZONE_TAGS)):
        widths = np.array([zone_data[f][i] for f in hr_runs])
        ax.barh(y, widths, left=left, color=col, height=0.55, label=tag)
        for j, w in enumerate(widths):
            if w > 7:
                tc = 'white' if i >= 3 else '#1a1a1a'
                ax.text(left[j] + w / 2, j, f'{w:.0f}%',
                        ha='center', va='center', fontsize=8,
                        color=tc, fontweight='medium')
        left += widths

    ax.set_yticks(y)
    ax.set_yticklabels([_label(f) for f in hr_runs], fontsize=8)
    ax.set_xlim(0, 100)
    ax.set_xlabel('% of Samples', color=FG)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color(EDGE)
    ax.tick_params(axis='y', length=0)
    ax.tick_params(axis='x', colors=DIM)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12),
              ncol=5, frameon=False, fontsize=8)
    ax.set_title('Heart Rate Zone Distribution \u2014 runs with valid HR telemetry',
                 pad=10, color=FG)

    fig.tight_layout()
    fig.savefig(FIG_DIR / 'fig_hr_zones.png', facecolor=BG,
                dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)


# ── 7  Gap-fill (02_timeseries option B) ─────────────────────
def fig_gap_fill(df):
    """Visualise gap-fill for Wednesday_Morning_Run_7km (original demo data)."""

    # ── 1 -- Use the designated run ────────────────────────────
    GAP_FILL_RUN = next(
        (f for f in CSV_FILES if 'Wednesday_Morning_Run_7km' in f), None
    )
    fname = GAP_FILL_RUN or CSV_FILES[0]

    g = (df[df['filename'] == fname]
         .sort_values('ts').copy())
    g['sec'] = g['ts'].dt.floor('s')
    per_sec  = g.groupby('sec')[['heart_rate', 'speed']].mean()
    spine    = pd.date_range(per_sec.index.min(),
                             per_sec.index.max(), freq='s')
    full     = per_sec.reindex(spine)
    is_gap   = full['heart_rate'].isna().to_numpy()
    n_gaps   = int(is_gap.sum())

    # Find center on the most prominent gap cluster
    gap_runs_, in_g_, s_ = [], False, 0
    for i, v in enumerate(is_gap):
        if v and not in_g_:
            s_ = i; in_g_ = True
        elif not v and in_g_:
            gap_runs_.append((s_, i - s_)); in_g_ = False
    if in_g_:
        gap_runs_.append((s_, len(is_gap) - s_))

    hr_s = full['heart_rate']
    best_score, center = -1, len(full) // 2
    for gs_, gl_ in gap_runs_:
        prev_v = hr_s.iloc[:gs_].dropna()
        next_v = hr_s.iloc[gs_ + gl_:].dropna()
        pv = float(prev_v.iloc[-1]) if len(prev_v) else 0.0
        nv = float(next_v.iloc[0])  if len(next_v) else 0.0
        score = gl_ * min(pv, nv)
        if score > best_score:
            best_score = score
            center = gs_ + gl_ // 2

    best = {'fname': fname, 'n_gaps': n_gaps, 'data': full, 'center': center}

    data = best['data'].copy()

    # ── 2 -- Extract 10-minute window; skip long leading warm-up gap ──
    W = 5 * 60
    leading_len = gap_runs_[0][1] if gap_runs_ and gap_runs_[0][0] == 0 else 0
    if leading_len > 10:
        w0 = max(0, leading_len - 2)
    else:
        w0 = max(0, best['center'] - W)
    w1     = min(len(data), w0 + 2 * W)
    window = data.iloc[w0:w1].copy()
    is_gap = window['heart_rate'].isna().to_numpy()
    t_min  = np.arange(len(window)) / 60.0
    rec    = ~is_gap
    n_shown = int(is_gap.sum())

    # ── 3 -- Plot: speed only ──────────────────────────────────
    GAP_COL = '#ff7070'
    fig, ax = plt.subplots(1, 1, figsize=(13, 4.5), layout='constrained')

    # Shade gap spans
    in_g, t0_ = False, 0.0
    for i, v in enumerate(is_gap):
        if v and not in_g:
            t0_ = t_min[i]; in_g = True
        elif not v and in_g:
            ax.axvspan(t0_, t_min[i], color=GAP_COL, alpha=0.30, linewidth=0, zorder=1)
            in_g = False
    if in_g:
        ax.axvspan(t0_, t_min[-1], color=GAP_COL, alpha=0.30, linewidth=0, zorder=1)

    ax.plot(t_min[rec], window['speed'].to_numpy()[rec],
            color='#f5c518', lw=1.4, zorder=2)

    ax.set_title(
        f'Gap-Fill - {_label(best["fname"])}: {n_shown} missing seconds detected',
        fontsize=12, pad=10, color=FG)
    ax.set_ylabel('Speed (km/h)', color=FG)
    ax.set_xlabel('Elapsed in window (min)', color=FG)
    ax.tick_params(colors=DIM, labelsize=9)
    ax.legend(handles=[
        Line2D([0], [0], color='#f5c518', lw=1.5, label='Speed (km/h)'),
        Patch(facecolor=GAP_COL, alpha=0.5, label='Missing seconds'),
    ], fontsize=9, frameon=False, loc='upper left')
    for sp in ax.spines.values():
        sp.set_color(EDGE)

    fig.savefig(FIG_DIR / 'fig_gap_fill.png', facecolor=BG,
                dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)


# ── Main ──────────────────────────────────────────────────────
def main():
    _style()
    FIG_DIR.mkdir(exist_ok=True)
    df = load()
    print(f'Loaded {len(df):,} samples from {df["filename"].nunique()} runs\n')

    for fn in [fig_routes, fig_h3_heatmap,
               fig_gap_fill, fig_effort, fig_graph_a, fig_hr_zones]:
        fn(df)
        ext = 'html+png' if fn.__name__ == 'fig_h3_heatmap' else 'png'
        print(f'  saved {fn.__name__}.{ext}')

    print(f'\nAll figures saved to {FIG_DIR}/')


if __name__ == '__main__':
    main()
