"""HTML builders for the Milkfish Monitoring Dashboard.

Pure functions: snapshot data in, HTML string out. No backend logic lives here.
Every value shown comes from the Snapshot (behavior.py) or the whole-video stats in dashboard.py;
when a value is missing or unreliable the panel says "Insufficient Data" instead of guessing.
"""
from __future__ import annotations

import html

esc = html.escape

SYM = {"ok": "✓", "warn": "▲", "bad": "✖", "mut": "–"}   # symbol + text, so colour is never the only cue
INSUFFICIENT = "Insufficient Data"
NO_DATA_KINDS = ("idle", "warming", "no_fish")

DEFAULT_EXTRA = {"coh_trend": INSUFFICIENT, "peak": 0, "usable": 0, "unique": 0}

COH_TIP = ("Cohesion (0-100%) = 50% neighbour proximity (average nearest-neighbour distance compared with body "
           "length) + 50% heading alignment of the moving fish. With fewer than 2 moving fish only proximity is "
           "used. Needs at least 2 tracked fish.")


def h(s: str) -> str:
    """Collapse a multi-line template to one line (Markdown treats blank/indented lines as code)."""
    return "".join(line.strip() for line in s.splitlines())


def badge(text: str, tone: str = "mut") -> str:
    return f'<span class="mf-badge {tone}">{SYM[tone]}&nbsp;{esc(text)}</span>'


def fmt_dur(sec) -> str:
    if not sec:
        return "—"
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def _valid(snap) -> bool:
    return getattr(snap, "kind", "") not in NO_DATA_KINDS and snap.count > 0


def _pct(n: int, d: int) -> int:
    return round(100 * n / d) if d else 0


def _count_pct(n: int, d: int, tone: str = "") -> str:
    """'28 (58%)' - the count first, then its share in brackets."""
    style = f' style="color:var(--{tone})"' if tone else ""
    return f'<span{style}>{n}</span><span class="u"> ({_pct(n, d)}%)</span>'


# ------------------------------------------------------------------ page chrome
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


# ------------------------------------------------------------------ KPI row
def _kpi(label: str, value: str, sub: str, tip: str = "") -> str:
    info = f' <span class="mf-info" title="{esc(tip)}">ⓘ</span>' if tip else ""
    return (f'<div class="mf-kpi"><div class="mf-klabel">{esc(label)}{info}</div>'
            f'<div class="mf-kval">{value}</div><div class="mf-ksub">{esc(sub)}</div></div>')


def kpi_row(snap, fps: float, src_fps: float, ended: bool, extra: dict) -> str:
    """Eight cards: tracked / peak / active / low movement, then speed / cohesion / FPS / unusual swimming."""
    valid = _valid(snap)
    n = snap.count
    assessed = snap.active + snap.inactive
    unknown = getattr(snap, "activity_unknown", max(n - assessed, 0))
    classified = snap.normal + snap.schooling + snap.feeding + getattr(snap, "unusual", 0)
    unusual = getattr(snap, "unusual", 0)
    wait = "Collecting movement data" if getattr(snap, "kind", "") == "warming" else "No fish tracked"
    more = f" · {unknown} need more tracking time" if unknown and assessed else ""

    unique = n if ended else extra.get("unique", 0)
    c1 = _kpi("Unique Milkfish Tracked", str(unique),
              "Reliable tracks in this video" if ended else f"Reliable tracks so far · {n} in view now")
    c2 = _kpi("Peak Fish Count", str(extra.get("peak", 0)), "Most fish seen in a single frame")
    if assessed:
        c3 = _kpi("Active Fish", _count_pct(snap.active, assessed), f"of {assessed} fish with enough data{more}")
        c4 = _kpi("Inactive / Low-Movement Fish", _count_pct(snap.inactive, assessed),
                  f"Little movement over several seconds, not one frame{more}")
    else:
        c3 = _kpi("Active Fish", "—", wait if not n else "Not enough tracking data yet")
        c4 = _kpi("Inactive / Low-Movement Fish", "—", wait if not n else "Not enough tracking data yet")

    if valid and getattr(snap, "speed_known", 0):
        sub = (f"Mean of {snap.speed_known} fish · whole video" if ended
               else f"Mean of {snap.speed_known} fish · current frame")
        c5 = _kpi("Average Swimming Speed", f'{snap.avg_speed:.1f}<span class="u"> px/s</span>', sub)
    else:
        c5 = _kpi("Average Swimming Speed", "—", wait if not n else "Not enough tracking data yet")

    coh = snap.cohesion
    c6 = _kpi("Average Schooling Cohesion", f"{coh:.0f}%" if coh is not None else "—",
              ("Mean over video" if ended else "Current frame") if coh is not None else "Not available (needs ≥ 2 fish)",
              tip=COH_TIP)
    c7 = _kpi("Processing FPS", f'{fps:.1f}<span class="u"> fps</span>' if fps > 0 else "—",
              f"Source video: {src_fps:.1f} fps" if src_fps else "Source FPS unknown")
    if classified:
        c8 = _kpi("Unusual Swimming Activity", _count_pct(unusual, classified, "warn" if unusual else ""),
                  f"of {classified} classified fish · video observation, not a diagnosis")
    else:
        c8 = _kpi("Unusual Swimming Activity", "—", wait if not n else "Not enough tracking data yet")
    return f'<div class="mf mf-kpis">{c1}{c2}{c3}{c4}{c5}{c6}{c7}{c8}</div>'


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


def alert_card(label: str, text: str, tone: str) -> str:
    return h(f'<div class="mf-alert {tone}"><div class="mf-ch" style="margin-bottom:6px">{badge(label, tone)}</div>'
             f'<div class="mf-note" style="margin:0">{esc(text)}</div></div>')
