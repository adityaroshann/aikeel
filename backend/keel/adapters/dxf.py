"""DXF drawing -> canonical DrawingTag. Driven entirely by the profile.

Customers store equipment tags in different ways:
  text    plain TEXT entities on some layer
  mtext   MTEXT entities on some layer
  attrib  an attribute (e.g. TAG) inside block references on some layer
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterator, Optional

import ezdxf

from keel.ontology import DrawingTag
from keel.profile import DrawingSpec

Key = tuple[str, str, Optional[str]]  # (layer, source, attribute)


def iter_strings(path: Path) -> Iterator[tuple[Key, str, float, float]]:
    """Every string in the model space, keyed by where it lives."""
    doc = ezdxf.readfile(path)
    for e in doc.modelspace():
        t = e.dxftype()
        if t == "TEXT":
            p = e.dxf.align_point if e.dxf.hasattr("align_point") else e.dxf.insert
            yield (e.dxf.layer, "text", None), e.dxf.text.strip(), p.x, p.y
        elif t == "MTEXT":
            p = e.dxf.insert
            yield (e.dxf.layer, "mtext", None), e.plain_text().strip(), p.x, p.y
        elif t == "INSERT":
            for a in e.attribs:
                p = e.dxf.insert
                yield (e.dxf.layer, "attrib", a.dxf.tag), a.dxf.text.strip(), p.x, p.y


def scan(path: Path) -> dict[Key, list[tuple[str, float, float]]]:
    groups: dict[Key, list] = defaultdict(list)
    for key, s, x, y in iter_strings(path):
        if s:
            groups[key].append((s, x, y))
    return dict(groups)


def load_tags(customer_dir: Path, spec: DrawingSpec) -> list[DrawingTag]:
    out = []
    for (layer, source, attr), s, x, y in iter_strings(customer_dir / spec.file):
        if layer.lower() != spec.layer.lower() or source != spec.source:
            continue
        if source == "attrib" and (attr or "").upper() != (spec.attribute or "").upper():
            continue
        if s:
            out.append(DrawingTag(tag=s, x=x, y=y, layer=layer))
    return out
