"""KrishiSetu — lightweight SVG chart builders (no external JS libs).

All charts render as inline SVG strings marked safe for Jinja, so the app
works fully offline / inside sandboxed previews.
"""

from markupsafe import Markup


def _fmt(v):
    if v >= 1000:
        return f"{v/1000:.1f}k"
    if v >= 100:
        return f"{v:.0f}"
    return f"{v:,.1f}".rstrip("0").rstrip(".")


def line_chart(labels, series, w=680, h=260, unit="", y_pad=0.08):
    """Multi-series line chart.

    labels : list of x labels
    series : list of (name, color, values[list[float]])
    """
    n = len(labels)
    if n == 0:
        return Markup("<div class='chart-empty'>No data</div>")
    pad_l, pad_r, pad_t, pad_b = 46, 14, 16, 30
    cw, ch = w - pad_l - pad_r, h - pad_t - pad_b

    allv = [v for _, _, vals in series for v in vals if v is not None] or [0]
    lo, hi = min(allv), max(allv)
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    rng = hi - lo
    lo -= rng * y_pad
    hi += rng * y_pad

    def X(i):
        return pad_l + (cw * i / max(n - 1, 1))

    def Y(v):
        return pad_t + ch - ch * (v - lo) / (hi - lo)

    grid, ylabels = [], []
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        y = Y(v)
        grid.append(f"<line x1='{pad_l}' y1='{y:.1f}' x2='{w-pad_r}' y2='{y:.1f}' "
                    f"stroke='#e3e9df' stroke-width='1'/>")
        ylabels.append(f"<text x='{pad_l-6}' y='{y+4:.1f}' text-anchor='end' "
                       f"class='ax'>{_fmt(v)}{unit}</text>")

    xlabels = []
    step = max(1, n // 6)
    for i in range(0, n, step):
        xlabels.append(f"<text x='{X(i):.1f}' y='{h-8}' text-anchor='middle' "
                       f"class='ax'>{labels[i]}</text>")

    paths = []
    for si, (name, color, vals) in enumerate(series):
        gid = f"grad{si}_{abs(hash(name)) % 99999}"
        paths.append(
            f"<linearGradient id='{gid}' x1='0' y1='0' x2='0' y2='1'>"
            f"<stop offset='0%' stop-color='{color}' stop-opacity='.22'/>"
            f"<stop offset='100%' stop-color='{color}' stop-opacity='0'/></linearGradient>")
        if any(v is None for v in vals):
            # split into contiguous segments (for bridged forecast overlays)
            segs, seg = [], []
            for i, v in enumerate(vals):
                if v is None:
                    if seg:
                        segs.append(seg)
                        seg = []
                else:
                    seg.append((i, v))
            if seg:
                segs.append(seg)
            for seg in segs:
                pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in seg)
                paths.append(f"<polyline points='{pts}' fill='none' stroke='{color}' "
                             f"stroke-width='2.4' stroke-linejoin='round' "
                             f"stroke-linecap='round'{' stroke-dasharray=|7 5|'.replace('|', chr(34)) if any(v2 is None for v2 in vals) else ''}/>")
            last_i, last_v = segs[-1][-1]
            paths.append(f"<circle cx='{X(last_i):.1f}' cy='{Y(last_v):.1f}' r='3.6' "
                         f"fill='{color}' stroke='#fff' stroke-width='1.5'/>")
            paths.append(f"<text x='{X(last_i):.1f}' y='{Y(last_v)-8:.1f}' text-anchor='end' "
                         f"fill='{color}' class='ax' font-weight='700'>"
                         f"{_fmt(last_v)}{unit}</text>")
        else:
            pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
            fill_pts = f"{X(0):.1f},{pad_t+ch} {pts} {X(n-1):.1f},{pad_t+ch}"
            paths.append(f"<polygon points='{fill_pts}' fill='url(#{gid})'/>")
            paths.append(f"<polyline points='{pts}' fill='none' stroke='{color}' "
                         f"stroke-width='2.4' stroke-linejoin='round' stroke-linecap='round'/>")
            lx, ly = X(n - 1), Y(vals[-1])
            paths.append(f"<circle cx='{lx:.1f}' cy='{ly:.1f}' r='3.6' fill='{color}' "
                         f"stroke='#fff' stroke-width='1.5'/>")
            paths.append(f"<text x='{lx:.1f}' y='{ly-8:.1f}' text-anchor='end' fill='{color}' "
                         f"class='ax' font-weight='700'>{_fmt(vals[-1])}{unit}</text>")

    legend = ""
    if len(series) > 1:
        chips = "".join(
            f"<tspan x='0' dy='{0 if i == 0 else 18}'><tspan fill='{c}'>■</tspan>"
            f"<tspan fill='#5b6b5d' dx='4'>{n_}</tspan></tspan>"
            for i, (n_, c, _) in enumerate(series))
        legend = (f"<text x='{pad_l}' y='{h-8}' class='ax'>{chips}</text>")

    svg = (f"<svg viewBox='0 0 {w} {h}' width='100%' role='img' class='chart'>"
           f"<defs>{''.join(p for p in paths if p.startswith('<linear'))}</defs>"
           f"{''.join(grid)}{''.join(ylabels)}{''.join(xlabels)}"
           f"{''.join(p for p in paths if not p.startswith('<linear'))}{legend}</svg>")
    return Markup(svg)


def bar_chart(labels, values, color="#2e7d32", w=680, h=260, unit=""):
    """Horizontal bar chart."""
    if not values:
        return Markup("<div class='chart-empty'>No data</div>")
    pad_l = max(112, max(len(l) for l in labels) * 7 + 12)
    pad_r, pad_t, pad_b = 58, 10, 10
    cw, ch = w - pad_l - pad_r, h - pad_t - pad_b
    hi = max(values) * 1.08 or 1
    row_h = ch / len(values)
    bar_h = min(18, row_h * 0.62)

    parts = []
    for k in range(1, 5):
        x = pad_l + cw * k / 4
        parts.append(f"<line x1='{x:.1f}' y1='{pad_t}' x2='{x:.1f}' y2='{h-pad_b}' "
                     f"stroke='#e3e9df' stroke-width='1'/>")
    for i, (lab, v) in enumerate(zip(labels, values)):
        y = pad_t + row_h * i + (row_h - bar_h) / 2
        bw = cw * v / hi
        parts.append(f"<text x='{pad_l-8}' y='{y+bar_h/2+4:.1f}' text-anchor='end' "
                     f"class='ax'>{lab}</text>")
        parts.append(f"<rect x='{pad_l}' y='{y:.1f}' width='{bw:.1f}' height='{bar_h}' "
                     f"rx='{bar_h/2}' fill='{color}' fill-opacity='.85'/>")
        parts.append(f"<text x='{pad_l+bw+6:.1f}' y='{y+bar_h/2+4:.1f}' class='ax' "
                     f"font-weight='700' fill='#33443a'>{_fmt(v)}{unit}</text>")

    svg = (f"<svg viewBox='0 0 {w} {h}' width='100%' role='img' class='chart'>"
           f"{''.join(parts)}</svg>")
    return Markup(svg)
