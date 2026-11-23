"""Render a GA drawing with findings marked on it (UI helper, not part of the engine)."""
from __future__ import annotations

import io
from collections import defaultdict
from pathlib import Path

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from ezdxf.addons.drawing import Frontend, RenderContext  # noqa: E402
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402

from keel.engine import RunResult  # noqa: E402

COLORS = {"error": "#d62728", "warning": "#ff9f1c"}


def render(dxf_path: Path, result: RunResult) -> bytes:
    doc = ezdxf.readfile(dxf_path)
    fig = plt.figure(figsize=(14, 5.2), dpi=130)
    ax = fig.add_axes([0, 0, 1, 1])
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.BLACK)
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(doc.modelspace(), finalize=True)

    # where each space sits on the drawing (centroid of its drawn equipment)
    pos = {t.tag: (t.x, t.y) for t in result.tags}
    by_space = defaultdict(list)
    for e in result.equipment:
        if e.tag in pos:
            by_space[e.space].append(pos[e.tag])

    for f in result.findings:
        c = COLORS[f.severity]
        if f.x is not None:
            ax.add_patch(plt.Circle((f.x, f.y), 2.1, fill=False, lw=2.5, ec=c))
            ax.annotate(f.check.replace("_", " "), (f.x, f.y + 2.3), color=c, fontsize=8,
                        ha="center", weight="bold")
        elif f.check == "missing_on_drawing":
            eq = next(e for e in result.equipment if e.tag == f.tag)
            pts = by_space.get(eq.space)
            if pts:
                cx = sum(p[0] for p in pts) / len(pts)
                ax.annotate(f"? {f.tag} missing\n(listed in {eq.space})", (cx, -9.6), color=c,
                            fontsize=8, ha="center", va="top", weight="bold",
                            bbox=dict(boxstyle="round", fc="white", ec=c, ls="--"))
        elif f.check.startswith("rule:"):
            pts = by_space.get(f.tag)
            if pts:
                xs = [p[0] for p in pts]
                ax.add_patch(plt.Rectangle((min(xs) - 3, -7.6), max(xs) - min(xs) + 6, 15.2,
                                           color=c, alpha=0.08, lw=0))
                ax.annotate("over weight limit", ((min(xs) + max(xs)) / 2, 9.0), color=c,
                            fontsize=9, ha="center", weight="bold")
    ax.set_ylim(-16, 11)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()
