"""DXF drawing -> plain JSON geometry, so a browser can render it as SVG.

UI helper (not part of the check engine). Block references are exploded so every
customer's drawing renders the same way regardless of how they built it.
"""
from __future__ import annotations

import math
from pathlib import Path

import ezdxf


def _walk(entities, out: dict) -> None:
    for e in entities:
        t = e.dxftype()
        layer = e.dxf.layer
        if t == "LINE":
            s, n = e.dxf.start, e.dxf.end
            out["lines"].append({"x1": s.x, "y1": s.y, "x2": n.x, "y2": n.y, "layer": layer})
        elif t == "LWPOLYLINE":
            pts = [[p[0], p[1]] for p in e.get_points("xy")]
            out["polylines"].append({"points": pts, "closed": bool(e.closed), "layer": layer})
        elif t == "POLYLINE":
            pts = [[v.dxf.location.x, v.dxf.location.y] for v in e.vertices]
            out["polylines"].append({"points": pts, "closed": bool(e.is_closed), "layer": layer})
        elif t == "CIRCLE":
            c = e.dxf.center
            out["circles"].append({"cx": c.x, "cy": c.y, "r": e.dxf.radius, "layer": layer})
        elif t in ("TEXT", "MTEXT"):
            if t == "TEXT":
                p = e.dxf.align_point if e.dxf.hasattr("align_point") else e.dxf.insert
                text, h = e.dxf.text, e.dxf.height
            else:
                p, text, h = e.dxf.insert, e.plain_text(), e.dxf.char_height
            if text.strip():
                out["texts"].append({"x": p.x, "y": p.y, "text": text.strip(), "h": h, "layer": layer})
        elif t == "INSERT":
            _walk(e.virtual_entities(), out)
            for a in e.attribs:
                p = e.dxf.insert
                if a.dxf.text.strip():
                    out["texts"].append({"x": p.x, "y": p.y, "text": a.dxf.text.strip(),
                                         "h": a.dxf.height, "layer": e.dxf.layer})


def drawing_geometry(path: Path) -> dict:
    doc = ezdxf.readfile(path)
    out: dict = {"lines": [], "polylines": [], "circles": [], "texts": []}
    _walk(doc.modelspace(), out)
    xs, ys = [], []
    for ln in out["lines"]:
        xs += [ln["x1"], ln["x2"]]; ys += [ln["y1"], ln["y2"]]
    for pl in out["polylines"]:
        xs += [p[0] for p in pl["points"]]; ys += [p[1] for p in pl["points"]]
    for c in out["circles"]:
        xs += [c["cx"] - c["r"], c["cx"] + c["r"]]; ys += [c["cy"] - c["r"], c["cy"] + c["r"]]
    for tx in out["texts"]:
        xs.append(tx["x"]); ys.append(tx["y"])
    xs = [v for v in xs if math.isfinite(v)] or [0.0]
    ys = [v for v in ys if math.isfinite(v)] or [0.0]
    out["bbox"] = {"minx": min(xs), "miny": min(ys), "maxx": max(xs), "maxy": max(ys)}
    out["layers"] = sorted({i["layer"] for k in ("lines", "polylines", "circles", "texts") for i in out[k]})
    return out
