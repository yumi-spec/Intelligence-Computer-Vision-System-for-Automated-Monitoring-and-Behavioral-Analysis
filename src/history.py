"""Saved video analyses (monitoring history) and downloadable reports (CSV / PDF). Put this file in src/."""
from __future__ import annotations

import csv
import io
from datetime import datetime

from src import behavior_ui as bui
from src import db


def make_record(view: dict, idmap: dict) -> dict:
    """Turn a finished video's view into a plain record (date, filename, results, tracked fish)."""
    snap = view["snap"]
    when = view.get("analyzed_at") or datetime.now()
    dur = view.get("duration")
    return {"analyzed_at": when.strftime("%Y-%m-%d %H:%M:%S"), "video": str(view.get("label", "")),
            "duration": f"{dur:.0f}" if dur else "", **bui.facts(snap),
            "fish": bui.fish_rows(snap, idmap, glyph=False)}


def save(rec: dict) -> None:
    db.add_video(rec)


def load() -> list:
    """Saved records, newest first."""
    return db.load_videos()


def _classified(rec: dict) -> int:
    return sum(rec[k] for k in ("normal", "schooling", "feeding", "unusual"))


def _pct(rec: dict, key: str) -> str:
    return bui.np_text(rec[key], _classified(rec))


def _sp(r: dict, unit: bool = True) -> str:
    return "—" if r.get("speed") is None else f"{r['speed']:.1f}" + (" px/s" if unit else "")


def report_csv(rec: dict) -> str:
    rows = [("Video", "Source file", rec["video"]), ("Video", "Analyzed on", rec["analyzed_at"]),
            ("Video", "Duration (s)", rec["duration"] or "—"),
            ("Results", "Milkfish tracked", rec["n"])]
    rows += [("Results", f"{title} (fish)", _pct(rec, k)) for k, title, *_ in bui.CATS]
    rows += [("Results", "Not classified yet (tracked too briefly)", max(rec["n"] - _classified(rec), 0)),
             ("Results", "Dominant behavior", rec["dominant"]),
             ("Results", "Average swimming speed (px/s)", f"{rec['avg_speed']:.1f}"),
             ("Results", "Group movement", bui.group_text(rec.get("cohesion"))),
             ("Results", "Overall monitoring status", "Normal" if rec["ok"] else "Unusual activity observed")]
    rows += [("Summary", "Report", s) for s in bui.sentences(rec)]
    rows += [("Tracked fish", f"Fish {r['id']}", f"{r['behavior']} | {r.get('activity', '—')} | {r['pattern']} | {_sp(r)}")
             for r in rec["fish"]]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["section", "item", "value"])
    w.writerows(rows)
    return buf.getvalue()


def report_pdf(rec: dict):
    """PDF bytes, or None when reportlab is not installed (pip install reportlab)."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return None
    green = colors.HexColor("#14532D")
    st = getSampleStyleSheet()

    def table(data, widths):
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), green), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("FONTSIZE", (0, 0), (-1, -1), 9), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D2E4D8")),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0FAF3")])]))
        return t

    story = [Paragraph("Milkfish Monitoring Report", st["Title"]),
             Paragraph(f"Video: {rec['video']}<br/>Analyzed on: {rec['analyzed_at']}", st["Normal"]),
             Spacer(1, 6 * mm), Paragraph("Monitoring Results", st["Heading2"])]
    story += [Paragraph(s, st["Normal"]) for s in bui.sentences(rec)]
    story += [Spacer(1, 5 * mm), Paragraph("Behavior statistics", st["Heading2"]),
              table([["Behavior", "Fish", "Share"]] + [[title, rec[k], f"{round(100 * rec[k] / _classified(rec)) if _classified(rec) else 0}%"]
                                                      for k, title, *_ in bui.CATS], [90 * mm, 30 * mm, 30 * mm]),
              Spacer(1, 5 * mm), Paragraph("Tracked fish", st["Heading2"])]
    fish = [["Fish ID", "Behavior", "Swimming pattern", "Speed (px/s)"]] + [
        [r["id"], r["behavior"], Paragraph(r["pattern"], st["BodyText"]), _sp(r, False)] for r in rec["fish"]]
    story += [table(fish, [20 * mm, 35 * mm, 85 * mm, 30 * mm]), Spacer(1, 5 * mm),
              Paragraph("Unusual swimming is an observation from video. It is not a confirmed disease diagnosis.",
                        st["Italic"])]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                      bottomMargin=16 * mm).build(story)
    return buf.getvalue()
