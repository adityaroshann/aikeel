"""Design-standard note -> parametric rules (proposals the engineer approves)."""
from __future__ import annotations

import re
from typing import Optional

from keel.profile import Proposal, Rule

UNIT_TO_KG = {"t": 1000.0, "tonne": 1000.0, "tonnes": 1000.0, "ton": 1000.0, "tons": 1000.0,
              "kg": 1.0, "kgs": 1.0, "lb": 0.45359237, "lbs": 0.45359237,
              "pound": 0.45359237, "pounds": 0.45359237}
QTY = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(tonnes|tonne|tons|ton|t|kgs|kg|lbs|lb|pounds|pound)\b", re.I)
LIMIT_WORDS = re.compile(r"exceed|more than|limit|max(imum)?|not be greater|at most", re.I)
ALL_SPACES = re.compile(r"\b(any|no single|each|every|per)\b", re.I)
RULE_ID = re.compile(r"^\s*([A-Z]{1,4}-[\d.]*\d|Rule\s+\d+)", re.I)


def parse_rules_heuristic(text: str, spaces: list[str]) -> tuple[list[Rule], list[Proposal], list[str]]:
    rules, proposals, unparsed = [], [], []
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if not line:
            continue
        q = QTY.search(line)
        if not q:
            if re.search(r"\b(mass|weight)\b", line, re.I) and re.search(r"\d", line):
                unparsed.append(line)
            continue
        if not LIMIT_WORDS.search(line):
            continue
        value = float(q.group(1).replace(",", ""))
        unit = q.group(2).lower()
        limit_kg = value * UNIT_TO_KG[unit]
        space: Optional[str] = next((s for s in sorted(spaces, key=len, reverse=True)
                                     if re.search(rf"\b{re.escape(s)}\b", line, re.I)), None)
        if space:
            conf, scope = 0.9, f"applies to '{space}' (named in the sentence)"
        elif ALL_SPACES.search(line):
            conf, scope = 0.85, "applies to every space ('" + ALL_SPACES.search(line).group(0) + "')"
        else:
            conf, scope = 0.55, "no space named; assumed to apply to every space"
        m = RULE_ID.match(line)
        rid = m.group(1) if m else f"R{len(rules) + 1}"
        rule = Rule(id=rid, limit_kg=round(limit_kg, 3), space=space, source_text=line)
        rules.append(rule)
        proposals.append(Proposal(
            field=f"rules[{rid}]", value=f"max {limit_kg/1000:,.2f} t per space"
                                         + (f" in {space}" if space else " (all spaces)"),
            confidence=conf,
            evidence=f"\"{line}\" -> {value:,g} {unit} = {limit_kg:,.0f} kg; {scope}"))
    return rules, proposals, unparsed
