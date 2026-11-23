"""Onboarding Autopilot: propose a CustomerProfile from a customer's sample files.

Heuristics first (fast, offline, explainable). Claude only for low-confidence decisions.
Every decision becomes a Proposal with a confidence and evidence, for an engineer to approve.
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Optional

from rapidfuzz import fuzz

from keel.adapters import dxf as dxf_adapter
from keel.adapters.tabular import read_raw, to_number
from keel.llm import LLM
from keel.profile import (ColumnMap, CustomerProfile, DrawingSpec, EquipmentListSpec, Proposal,
                          TagConvention)
from keel.rules import parse_rules_heuristic

LOW_CONFIDENCE = 0.6

SYNONYMS = {
    "tag": ["tag", "tag no", "item no", "equipment id", "equip id", "id", "ref", "code", "number"],
    "name": ["description", "desc", "name", "equipment name", "item", "title"],
    "space": ["location", "room", "space", "compartment", "deck", "zone", "area"],
    "mass_kg": ["weight", "mass", "wt", "dry weight", "weight kg", "mass t"],
}
MASS_UNITS = {
    1000.0: {"t", "tonne", "tonnes", "ton", "tons", "mt"},
    0.45359237: {"lb", "lbs", "pound", "pounds"},
    1.0: {"kg", "kgs", "kilogram", "kilograms"},
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


# ---------------------------------------------------------------- files

def discover(customer_dir: Path) -> dict[str, Optional[Path]]:
    files = [p for p in customer_dir.iterdir() if p.is_file() and not p.name.startswith("_")]
    pick = lambda exts: next((p for p in sorted(files) if p.suffix.lower() in exts), None)  # noqa: E731
    return {"list": pick({".csv", ".xlsx"}), "drawing": pick({".dxf"}), "standards": pick({".md", ".txt"})}


# ---------------------------------------------------------------- tabular

def detect_delimiter(path: Path) -> tuple[str, float, str]:
    sample = path.read_text(encoding="utf-8", errors="ignore")[:4096]
    try:
        d = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        return d, 0.95, f"csv.Sniffer found '{d}' consistently across the first lines"
    except csv.Error:
        return ",", 0.5, "could not sniff a delimiter; defaulted to ','"


def detect_header_row(raw) -> tuple[int, float, str]:
    rows = raw.fillna("").astype(str).values.tolist()
    for i, row in enumerate(rows[:20]):
        cells = [c.strip() for c in row if c.strip() and c.strip().lower() != "nan"]
        nxt = [c for c in (rows[i + 1] if i + 1 < len(rows) else []) if str(c).strip() and str(c) != "nan"]
        if len(cells) >= 3 and sum(to_number(c) is None for c in cells) / len(cells) >= 0.8 and len(nxt) >= 3:
            if i == 0:
                return 0, 0.95, "first row holds the column labels"
            return i, 0.85, (f"rows 1-{i} look like a title block ({rows[0][0][:40]!r}...); "
                             f"row {i + 1} is the first row of labels followed by data")
    return 0, 0.4, "no clear header row found; assumed row 1"


def column_features(values: list[str]) -> dict:
    vals = [v.strip() for v in values if v and v.strip() and v.strip().lower() != "nan"]
    n = len(vals)
    if n == 0:
        return {"n": 0}
    return {
        "n": n,
        "uniq": len(set(vals)) / n,
        "distinct": len(set(vals)),
        "digit": sum(any(ch.isdigit() for ch in v) for v in vals) / n,
        "spaces": sum(" " in v for v in vals) / n,
        "numeric": sum(to_number(v) is not None for v in vals) / n,
        "median": median([to_number(v) for v in vals if to_number(v) is not None] or [0]),
    }


def value_score(field: str, f: dict) -> tuple[float, str]:
    if f["n"] == 0:
        return 0.0, "empty column"
    if field == "tag":
        s = 0.4 * min(1, f["uniq"] / 0.9) + 0.3 * f["digit"] + 0.3 * (1 - f["spaces"]) - 0.5 * f["numeric"]
        why = f"{f['uniq']:.0%} unique, {f['digit']:.0%} contain digits, {f['spaces']:.0%} contain spaces"
    elif field == "name":
        s = 0.4 * f["spaces"] + 0.4 * min(1, f["uniq"] / 0.8) + 0.2 * (1 - f["numeric"])
        why = f"{f['spaces']:.0%} multi-word, {f['uniq']:.0%} unique"
    elif field == "space":
        s = 0.6 * (1 - f["uniq"]) + 0.4 * (1 - f["numeric"])
        if f["distinct"] <= 1:
            s *= 0.3
        why = f"{f['distinct']} distinct values over {f['n']} rows (categorical)"
    else:
        s = f["numeric"]
        why = f"{f['numeric']:.0%} numeric, median {f['median']:,.1f}"
    return max(0.0, min(1.0, s)), why


def header_score(field: str, header: str) -> tuple[float, str]:
    h = norm(header)
    best = max(SYNONYMS[field], key=lambda s: fuzz.ratio(h, s))
    score = fuzz.ratio(h, best) / 100
    tokens = set(h.split())
    if any(s in tokens for s in SYNONYMS[field] if " " not in s):
        score = max(score, 0.85)
    return score, best


def detect_mass_scale(header: str, f: dict) -> tuple[float, float, str]:
    tokens = set(norm(header).split())
    for scale, words in MASS_UNITS.items():
        hit = tokens & words
        if hit:
            unit = sorted(hit)[0]
            return scale, 0.9, f"header '{header}' states the unit '{unit}' -> x{scale:g} to kg"
    if f.get("median", 0) and f["median"] < 100:
        return 1000.0, 0.45, f"no unit in header; median value {f['median']:.2f} looks like tonnes (verify)"
    return 1.0, 0.5, "no unit in header; assumed kg (verify)"


# ---------------------------------------------------------------- tags

def shape_regex(s: str) -> str:
    runs: list[list] = []
    for ch in s:
        cls = "A" if ch.isupper() else "a" if ch.islower() else "9" if ch.isdigit() else ch
        if runs and runs[-1][0] == cls:
            runs[-1][1] += 1
        else:
            runs.append([cls, 1])
    out = []
    for cls, n in runs:
        base = {"A": "[A-Z]", "a": "[a-z]", "9": r"\d"}.get(
            cls, "\\" + cls if cls in r".^$*+?{}[]\|()" else cls)  # readable: '-' stays '-'
        out.append(base if n == 1 else f"{base}{{{n}}}")
    return "^" + "".join(out) + "$"


def infer_tag_convention(tags: list[str]) -> tuple[TagConvention, Proposal]:
    shapes = Counter(shape_regex(t) for t in tags)
    pattern, count = shapes.most_common(1)[0]
    outliers = [t for t in tags if not re.match(pattern, t)]
    example = next(t for t in tags if re.match(pattern, t))
    conf = count / len(tags)
    ev = f"{count} of {len(tags)} tags share this shape (e.g. {example})"
    if outliers:
        ev += f"; outliers to review: {', '.join(sorted(set(outliers))[:4])}"
    return TagConvention(pattern=pattern, example=example), Proposal(
        field="tag_convention.pattern", value=pattern, confidence=round(conf, 2), evidence=ev)


# ---------------------------------------------------------------- drawing

def infer_drawing(path: Path, list_tags: set[str], pattern: str) -> tuple[DrawingSpec, Proposal]:
    groups = dxf_adapter.scan(path)
    rx = re.compile(pattern)
    scored = []
    for (layer, source, attr), items in groups.items():
        strings = [s for s, _, _ in items]
        if len(strings) < 3:
            continue
        fmt = sum(bool(rx.match(s)) for s in strings) / len(strings)
        overlap = len(set(strings) & list_tags) / len(set(strings))
        scored.append((0.5 * fmt + 0.5 * overlap, layer, source, attr, len(strings),
                       len(set(strings) & list_tags)))
    if not scored:
        raise ValueError("no text found in drawing")
    scored.sort(reverse=True)
    best = scored[0]
    score, layer, source, attr, n, hits = best
    where = {"text": "TEXT entities", "mtext": "MTEXT entities", "attrib": f"block attribute '{attr}'"}[source]
    ev = f"layer '{layer}', {where}: {hits} of {n} strings match equipment-list tags"
    if len(scored) > 1:
        s2 = scored[1]
        ev += f"; runner-up layer '{s2[1]}' ({s2[2]}{'/' + s2[3] if s2[3] else ''}) scored {s2[0]:.2f}"
    return DrawingSpec(file=path.name, layer=layer, source=source, attribute=attr), Proposal(
        field="drawing.tags", value={"layer": layer, "source": source, "attribute": attr},
        confidence=round(score, 2), evidence=ev)


# ---------------------------------------------------------------- main

def infer_profile(customer_dir: Path, customer: Optional[str] = None,
                  llm: Optional[LLM] = None) -> tuple[CustomerProfile, list[Proposal]]:
    files = discover(customer_dir)
    if not files["list"] or not files["drawing"]:
        raise ValueError("need an equipment list (.csv/.xlsx) and a drawing (.dxf)")
    proposals: list[Proposal] = []
    lpath = files["list"]

    # format, delimiter, header row
    fmt = "xlsx" if lpath.suffix.lower() == ".xlsx" else "csv"
    delim = ","
    if fmt == "csv":
        delim, c, ev = detect_delimiter(lpath)
        proposals.append(Proposal(field="equipment_list.delimiter", value=delim, confidence=c, evidence=ev))
    raw = read_raw(lpath, fmt, delim)
    hrow, c, ev = detect_header_row(raw)
    proposals.append(Proposal(field="equipment_list.header_row", value=hrow, confidence=c, evidence=ev))
    headers = [str(h).strip() for h in raw.iloc[hrow].tolist()]
    body = raw.iloc[hrow + 1:].fillna("").astype(str)
    feats = {h: column_features(body.iloc[:, i].tolist()) for i, h in enumerate(headers) if h and h != "nan"}

    # column mapping: score every (field, column), assign greedily
    cand = []
    for field in SYNONYMS:
        for h, f in feats.items():
            hs, syn = header_score(field, h)
            vs, why = value_score(field, f)
            cand.append((0.55 * hs + 0.45 * vs, field, h, f"header '{h}' ~ '{syn}' ({hs:.0%}); values: {why}"))
    cand.sort(reverse=True)
    chosen: dict[str, tuple] = {}
    used = set()
    for score, field, h, ev in cand:
        if field in chosen or h in used:
            continue
        runner = max((s for s, f2, h2, _ in cand if f2 == field and h2 != h), default=0)
        conf = score - (0.15 if score - runner < 0.1 else 0)
        chosen[field] = (h, round(max(conf, 0), 2), ev)
        used.add(h)

    columns: dict[str, ColumnMap] = {}
    for field in SYNONYMS:
        h, conf, ev = chosen[field]
        columns[field] = ColumnMap(source=h)
        proposals.append(Proposal(field=f"columns.{field}", value=h, confidence=conf, evidence=ev))
    scale, c, ev = detect_mass_scale(columns["mass_kg"].source, feats[columns["mass_kg"].source])
    columns["mass_kg"].scale = scale
    proposals.append(Proposal(field="columns.mass_kg.scale", value=scale, confidence=c, evidence=ev))

    # Claude for anything the heuristics are unsure about
    low = [p for p in proposals if p.field.startswith("columns.") and p.confidence < LOW_CONFIDENCE]
    if llm and low:
        sample = body.head(5).values.tolist()
        std = files["standards"].read_text(encoding="utf-8")[:1500] if files["standards"] else ""
        result = llm.map_columns(headers, sample, list(SYNONYMS), context=std)
        if result:
            by_field = {ch.field: ch for ch in result.choices}
            for p in low:
                fld = p.field.split(".")[1]
                ch = by_field.get(fld)
                if not ch:
                    continue
                if p.field == "columns.mass_kg.scale" and ch.scale_to_kg:
                    columns["mass_kg"].scale = ch.scale_to_kg
                    p.value = ch.scale_to_kg
                elif p.field != "columns.mass_kg.scale" and ch.column in headers:
                    columns[fld].source = ch.column
                    p.value = ch.column
                else:
                    continue
                p.method, p.confidence, p.evidence = "llm", round(ch.confidence, 2), f"Claude: {ch.reason}"

    spec = EquipmentListSpec(file=lpath.name, format=fmt, delimiter=delim, header_row=hrow, columns=columns)

    # tag convention, learned from the tag column
    tag_values = [v.strip() for v in body.iloc[:, headers.index(columns["tag"].source)].tolist() if v.strip()]
    convention, p = infer_tag_convention(tag_values)
    proposals.append(p)

    # where the tags live on the drawing
    drawing, p = infer_drawing(files["drawing"], set(tag_values), convention.pattern)
    proposals.append(p)

    # design rules from the standards note
    rules = []
    if files["standards"]:
        text = files["standards"].read_text(encoding="utf-8")
        spaces = sorted({v.strip() for v in body.iloc[:, headers.index(columns["space"].source)] if v.strip()})
        rules, rule_props, unparsed = parse_rules_heuristic(text, spaces)
        proposals.extend(rule_props)
        if llm and (unparsed or any(rp.confidence < LOW_CONFIDENCE for rp in rule_props)):
            result = llm.parse_rules(text, spaces)
            if result:
                from keel.profile import Rule
                rules = [Rule(id=r.id, limit_kg=r.limit_kg, space=r.space, source_text=r.source_text)
                         for r in result.rules]
                proposals = [q for q in proposals if not q.field.startswith("rules[")]
                proposals.extend(Proposal(field=f"rules[{r.id}]", value=f"max {r.limit_kg/1000:,.2f} t",
                                          confidence=0.8, evidence=f"Claude: \"{r.source_text}\"", method="llm")
                                 for r in result.rules)

    profile = CustomerProfile(customer=customer or customer_dir.name, equipment_list=spec,
                              tag_convention=convention, drawing=drawing, rules=rules)
    return profile, proposals
