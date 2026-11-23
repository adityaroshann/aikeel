"""Generic QA/QC checks over canonical data.

Nothing in this file knows which customer it is running for. Customer-specific
behaviour (tag convention, weight limits) arrives as data from the profile.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from keel.ontology import DrawingTag, Equipment, Finding
from keel.profile import CustomerProfile


def run_checks(profile: CustomerProfile, equipment: list[Equipment], tags: list[DrawingTag]) -> list[Finding]:
    findings: list[Finding] = []
    pos = {t.tag: t for t in tags}
    listed = {e.tag for e in equipment}

    # 1. duplicate tags in the equipment list
    counts = Counter(e.tag for e in equipment)
    for tag, n in counts.items():
        if n > 1:
            rows = [str(e.row) for e in equipment if e.tag == tag]
            p = pos.get(tag)
            findings.append(Finding(
                check="duplicate_tag", severity="error", tag=tag,
                message=f"Tag {tag} is used {n} times in the equipment list. Each item needs a unique tag.",
                evidence=f"rows {', '.join(rows)}", x=p.x if p else None, y=p.y if p else None))

    # 2. tag naming convention (customer's own, from the profile)
    rx = re.compile(profile.tag_convention.pattern)
    for e in equipment:
        if not rx.match(e.tag):
            p = pos.get(e.tag)
            ex = f" (e.g. {profile.tag_convention.example})" if profile.tag_convention.example else ""
            findings.append(Finding(
                check="tag_convention", severity="warning", tag=e.tag,
                message=f"{e.tag} ({e.name}) does not follow this customer's tagging convention{ex}.",
                evidence=f"row {e.row}; expected pattern {profile.tag_convention.pattern}",
                x=p.x if p else None, y=p.y if p else None))

    # 3. listed but not on the drawing
    for tag in sorted(listed - set(pos)):
        e = next(x for x in equipment if x.tag == tag)
        findings.append(Finding(
            check="missing_on_drawing", severity="error", tag=tag,
            message=f"{tag} ({e.name}, {e.space}) is in the equipment list but not shown on the GA drawing.",
            evidence=f"row {e.row}; searched layer '{profile.drawing.layer}'"))

    # 4. on the drawing but not listed
    for tag in sorted(set(pos) - listed):
        p = pos[tag]
        findings.append(Finding(
            check="missing_from_list", severity="error", tag=tag,
            message=f"{tag} appears on the GA drawing but is not in the equipment list.",
            evidence=f"layer '{p.layer}' at ({p.x:.1f}, {p.y:.1f})", x=p.x, y=p.y))

    # 5. customer design rules (parametric, from the profile)
    mass_by_space: dict[str, list[Equipment]] = defaultdict(list)
    for e in equipment:
        if e.mass_kg is not None:
            mass_by_space[e.space].append(e)
    for rule in profile.rules:
        if rule.type == "max_total_mass_per_space":
            spaces = [s for s in mass_by_space if rule.space is None or s.lower() == rule.space.lower()]
            for s in spaces:
                total = sum(e.mass_kg for e in mass_by_space[s])
                if total > rule.limit_kg:
                    top = sorted(mass_by_space[s], key=lambda e: -e.mass_kg)[:3]
                    findings.append(Finding(
                        check=f"rule:{rule.type}", severity="error", tag=s,
                        message=(f"{s}: total equipment mass {total/1000:,.1f} t exceeds the limit of "
                                 f"{rule.limit_kg/1000:,.1f} t ({rule.id})."),
                        evidence=(f"\"{rule.source_text}\" | heaviest: "
                                  + ", ".join(f"{e.tag} {e.mass_kg/1000:.1f} t" for e in top))))
    return findings
