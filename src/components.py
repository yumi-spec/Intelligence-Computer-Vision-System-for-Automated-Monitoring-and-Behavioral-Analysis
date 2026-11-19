"""HTML builders for the Milkfish Monitoring Dashboard.

Pure functions: snapshot data in, HTML string out. No backend logic lives here.
Every value shown comes from the Snapshot (behavior.py) or the whole-video stats in dashboard.py;
when a value is missing or unreliable the panel says "Insufficient Data" instead of guessing.
"""
from __future__ import annotations

import html
from collections import Counter

esc = html.escape

SYM = {"ok": "✓", "warn": "▲", "bad": "✖", "mut": "–"}   # symbol + text, so colour is never the only cue
BEHAVIOR = {  # backend per-fish status -> (display label, tone)
    "Normal": ("Normal Movement", "ok"),
    "Erratic": ("Erratic Movement", "warn"),
    "Low Oxygen": ("Possible Low-Oxygen Stress", "bad"),
}
COH_MAINTAINED, COH_LOOSENING = 60.0, 30.0   # same bands as behavior.py ("Schooling" detail)
INSUFFICIENT = "Insufficient Data"
NO_DATA_KINDS = ("idle", "warming", "no_fish")

DEFAULT_EXTRA = {"coh_trend": INSUFFICIENT, "peak": 0, "usable": 0}

COH_TIP = ("Cohesion (0-100%) = 50% neighbour proximity (average nearest-neighbour distance compared with "
           "25% of the frame diagonal) + 50% heading alignment of the moving fish. With fewer than 2 moving "
           "fish only proximity is used. Needs at least 2 tracked fish.")


def h(s: str) -> str:
    """Collapse a multi-line template to one line (Markdown treats blank/indented lines as code)."""
    return "".join(line.strip() for line in s.splitlines())


def badge(text: str, tone: str = "mut") -> str:
    return f'<span class="mf-badge {tone}">{SYM[tone]}&nbsp;{esc(text)}</span>'


def fmt_dur(sec) -> str:
    if not sec:
        return "—"
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def _warming(snap) -> bool:
    return getattr(snap, "kind", "") == "warming"


def _valid(snap) -> bool:
    return getattr(snap, "kind", "") not in NO_DATA_KINDS and snap.count > 0


# ------------------------------------------------------------------ header / brand
def header(status: str, tone: str, now) -> str:
    tone = tone if tone in ("ok", "warn", "bad") else "mut"
    return h(f'''<div class="mf mf-head"><div><div class="mf-title">Milkfish Monitoring Dashboard</div>
<div class="mf-sub">Automated Detection and Behavioral Analysis</div></div>
<div class="mf-headr">{badge(status, tone)}<span class="mf-time">{now:%d %b %Y · %I:%M:%S %p}</span></div></div>''')


def page_title(title: str, sub: str = "") -> str:
    return h(f'''<div class="mf mf-head"><div><div class="mf-title">{esc(title)}</div>
<div class="mf-sub">{esc(sub)}</div></div></div>''')


def section(title: str) -> str:
    return f'<div class="mf mf-sec"><div class="mf-h2">{esc(title)}</div></div>'


def sidebar_brand() -> str:
    return h('''<div class="mf mf-brand"><div class="mf-logo">MF</div>
<div><div class="mf-bname">Milkfish Monitor</div><div class="mf-bsub">Behavior Analysis</div></div></div>''')


def sidebar_label(text: str) -> str:
    return f'<div class="mf mf-slabel">{esc(text)}</div>'


# ------------------------------------------------------------------ labels
def behavior_label(snap) -> tuple:
    """Cautious label from what the backend (behavior.py `kind`) actually flagged."""
    kind = getattr(snap, "kind", "idle")
    if kind in NO_DATA_KINDS or snap.count == 0:
        return INSUFFICIENT, "mut"
    if kind == "low_oxygen":
        return "Possible Low-Oxygen Stress", "bad" if snap.level == "critical" else "warn"
    if kind == "erratic":
        return "Erratic Movement", "warn"
    if kind == "normal":
        return "Normal Movement", "ok"
    return "No Specific Indicator Detected", "mut"


def coh_status(c) -> tuple:
    if c is None:
        return "Not available", "mut"
    if c >= COH_MAINTAINED:
        return "Maintained", "ok"
    if c >= COH_LOOSENING:
        return "Loosening", "warn"
    return "Dispersed", "warn"


def speed_trend(snap) -> str:
    if _warming(snap):
        return INSUFFICIENT
    v = (getattr(snap, "details", None) or {}).get("Speed Trend", "—")
    return INSUFFICIENT if v in ("—", "", None) else v


# ------------------------------------------------------------------ KPI row
def _kpi(label: str, value: str, sub: str, tip: str = "") -> str:
    info = f' <span class="mf-info" title="{esc(tip)}">ⓘ</span>' if tip else ""
    return (f'<div class="mf-kpi"><div class="mf-klabel">{esc(label)}{info}</div>'
            f'<div class="mf-kval">{value}</div><div class="mf-ksub">{esc(sub)}</div></div>')


def kpi_row(snap, fps: float, src_fps: float, ended: bool, extra: dict) -> str:
    valid = _valid(snap)
    if ended:
        c1 = _kpi("Unique Milkfish Tracked", str(snap.count),
                  f"Unique tracks · peak {extra['peak']} in one frame")
    else:
        c1 = _kpi("Milkfish Detected", str(snap.count),
                  f"In current frame · peak {extra['peak']} (detections, not unique fish)")

    if valid:
        sub = "Mean over video" if ended else "Current frame"
        c2 = _kpi("Average Swimming Speed", f'{snap.avg_speed:.1f}<span class="u"> px/s</span>', sub)
    else:
        c2 = _kpi("Average Swimming Speed", "—", "Warming up" if _warming(snap) else "No fish tracked")

    coh = snap.cohesion
    c3 = _kpi("Average Schooling Cohesion", f"{coh:.0f}%" if coh is not None else "—",
              ("Mean over video" if ended else "Current frame") if coh is not None else "Not available (needs ≥ 2 fish)",
              tip=COH_TIP)

    c4 = _kpi("Processing FPS", f'{fps:.1f}<span class="u"> fps</span>' if fps > 0 else "—",
              f"Source video: {src_fps:.1f} fps" if src_fps else "Source FPS unknown")
    return f'<div class="mf mf-kpis">{c1}{c2}{c3}{c4}</div>'


def _kv(k: str, v: str, raw: bool = False) -> str:
    return f'<div class="mf-kv"><span>{esc(k)}</span><b>{v if raw else esc(v)}</b></div>'


def _card(title: str, body: str, right: str = "") -> str:
    return (f'<div class="mf-card"><div class="mf-cardhead"><div class="mf-ch">{esc(title)}</div>{right}</div>'
            f'{body}</div>')


def kv_card(title: str, rows: list) -> str:
    return h(_card(title, "".join(_kv(k, v) for k, v in rows)))


# ------------------------------------------------------------------ video card
def video_card(media: str, running: bool, ended: bool, label, size, src_fps, duration) -> str:
    if ended:
        b = badge("ENDED", "mut")
    elif running:
        b = badge("LIVE", "ok")
    else:
        b = badge("PAUSED", "warn")
    res = f"{size[0]}×{size[1]}" if size else "—"
    fps = f"{src_fps:.1f} fps" if src_fps else "—"
    overlay = ('<div class="mf-ended"><b>Video ended</b><span>Press Start to replay</span></div>'
               if ended else "")
    name = esc(str(label))
    return h(f'''<div class="mf-card"><div class="mf-cardhead"><div class="mf-ch">Live Milkfish Monitoring</div>{b}</div>
<div class="mf-stage">{media}{overlay}</div>
<div class="mf-meta"><span class="fn" title="{name}">{name}</span><span>Resolution {res}</span>
<span>Source {fps}</span><span>Duration {fmt_dur(duration)}</span></div></div>''')


def message_card(title: str, detail: str = "", tone: str = "bad") -> str:
    return h(f'<div class="mf-msg {tone}"><b>{esc(title)}</b><span>{esc(detail)}</span></div>')


def setup_card(problems: list, models_dir: str, videos_dir: str) -> str:
    items = "".join(f"<span>• {esc(p)}</span>" for p in problems)
    return h(f'<div class="mf-msg warn"><b>Setup required</b>{items}'
             f'<span>Models: {esc(models_dir)}</span><span>Videos: {esc(videos_dir)}</span></div>')


# ------------------------------------------------------------------ side column
def behavior_card(snap, extra: dict, ended: bool) -> str:
    label, tone = behavior_label(snap)
    valid = _valid(snap)
    coh_txt, _ = coh_status(snap.cohesion)
    parts = []
    if snap.erratic:
        parts.append(f"{snap.erratic} erratic")
    if snap.low_oxygen:
        parts.append(f"{snap.low_oxygen} possible low-oxygen")
    alerts = " · ".join(parts) if parts else ("None observed" if valid else "—")
    rows = (_kv("Movement pattern", label) + _kv("Speed trend", speed_trend(snap)) +
            _kv("Schooling cohesion", coh_txt) + _kv("Abnormal movement", alerts))
    note = esc(getattr(snap, "description", "") or "") if valid else ""
    note_html = f'<div class="mf-note">{note}</div>' if note else ""
    return h(_card("Behavior Summary", rows + note_html, badge(label, tone)))


def rec_card(snap) -> str:
    act = getattr(snap, "action", "") or "—"
    det = getattr(snap, "action_detail", "") or ""
    det_html = f'<div class="mf-note">{esc(det)}</div>' if det else ""
    return h(_card("Recommended Action", f'<div class="mf-act">{esc(act)}</div>{det_html}'))


def alert_card(label: str, text: str, tone: str) -> str:
    return h(f'<div class="mf-alert {tone}"><div class="mf-ch" style="margin-bottom:6px">{badge(label, tone)}</div>'
             f'<div class="mf-note" style="margin:0">{esc(text)}</div></div>')


# ------------------------------------------------------------------ analysis summary
def _group_movement(snap) -> str:
    arrows = [getattr(f, "arrow", "—") for f in snap.fish]
    arrows = [a for a in arrows if a not in ("—", "", None)]
    if len(arrows) < 2:
        return INSUFFICIENT
    a, c = Counter(arrows).most_common(1)[0]
    return f"Mostly {a}" if c / len(arrows) >= 0.5 else "Mixed directions"


def analysis(snap, extra: dict, ended: bool, s) -> str:
    valid = _valid(snap)
    n = snap.count
    # A. movement
    speed = f"{snap.avg_speed:.1f} px/s" if valid else INSUFFICIENT
    erratic = f"{snap.erratic} of {n} fish" if valid else INSUFFICIENT
    a = _card("Movement Analysis",
              _kv("Average swimming speed", speed) + _kv("Speed trend", speed_trend(snap)) +
              _kv("Erratic movement observed", erratic))
    # B. schooling
    coh = snap.cohesion
    coh_txt = f"{coh:.0f}% ({coh_status(coh)[0]})" if coh is not None else INSUFFICIENT
    b = _card("Schooling Analysis",
              _kv("Average cohesion", coh_txt) + _kv("Observed group movement", _group_movement(snap)) +
              _kv("Schooling trend", extra["coh_trend"]))
    return h(f'<div class="mf mf-sec"><div class="mf-h2">Behavioral Analysis Summary</div>'
             f'<div class="mf-grid2">{a}{b}</div></div>')


# ------------------------------------------------------------------ distribution + table
def distribution(snap, ended: bool) -> str:
    nm, er, lo = snap.normal, snap.erratic, snap.low_oxygen
    total = nm + er + lo
    cap = "Whole video · per tracked fish" if ended else "Current frame · per detected fish"
    if _warming(snap) or total == 0:
        body = f'<div class="mf-note">{INSUFFICIENT}</div>'
    else:
        rows = []
        for name, val, tone in (("Normal Movement", nm, "ok"), ("Erratic Movement", er, "warn"),
                                ("Possible Low-Oxygen Stress", lo, "bad")):
            pct = 100.0 * val / total
            rows.append(f'<div><div class="mf-brow"><span>{name}</span><span>{val} · {pct:.0f}%</span></div>'
                        f'<div class="mf-bar"><i class="{tone}" style="width:{pct:.0f}%"></i></div></div>')
        body = f'<div class="mf-bars">{"".join(rows)}</div>'
    return h(_card("Behavior Distribution", f'<div class="mf-note" style="margin:0 0 12px">{cap}</div>{body}'))


def fish_table(snap) -> str:
    warming = _warming(snap)
    fish = sorted(snap.fish, key=lambda f: f.id)
    track_tone = {"Tracked": "ok", "Tracking": "ok", "Short track": "warn"}
    rows = []
    for f in fish:
        if warming or f.status not in BEHAVIOR:
            beh, sp = badge(INSUFFICIENT, "mut"), "—"          # no usable history: never shown as Normal
        elif f.status == "Normal" and getattr(f, "active", True) is False:
            beh, sp = badge("Low Activity", "mut"), f"{f.speed:.1f}"   # stationary is not "moving normally"
        else:
            lab, tone = BEHAVIOR[f.status]
            beh, sp = badge(lab, tone), f"{f.speed:.1f}"
        track = getattr(f, "track", "Tracking")
        arrow = getattr(f, "arrow", "") or "—"
        rows.append(f'<tr><td>#{f.id}</td><td class="ctr">{esc(str(arrow))}</td><td class="num">{sp}</td>'
                    f'<td>{beh}</td><td>{badge(track, track_tone.get(track, "mut"))}</td></tr>')
    if not rows:
        rows.append('<tr><td colspan="5" style="color:#9AAECC">No milkfish tracked yet</td></tr>')
    more = ""
    table = ('<div class="mf-tw"><table class="mf-tbl"><colgroup><col style="width:13%"><col style="width:13%">'
             '<col style="width:15%"><col style="width:33%"><col style="width:26%"></colgroup>'
             '<tr><th>Track ID</th><th class="ctr">Direction</th><th class="num">Speed (px/s)</th>'
             f'<th>Behavior</th><th>Tracking Status</th></tr>{"".join(rows)}</table></div>{more}')
    return h(_card("Tracked Fish", table, f'<span class="mf-ksub">{len(fish)} tracked</span>'))


def bottom_row(snap, ended: bool) -> str:
    return h(f'<div class="mf mf-sec"><div class="mf-h2">Behavior Distribution and Tracking</div>'
             f'<div class="mf-bottom">{distribution(snap, ended)}{fish_table(snap)}</div></div>')