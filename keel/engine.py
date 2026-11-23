"""One entry point, identical for every customer: profile in, findings out."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from keel.adapters.dxf import load_tags
from keel.adapters.tabular import load_equipment
from keel.checks import run_checks
from keel.ontology import DrawingTag, Equipment, Finding
from keel.profile import CustomerProfile


@dataclass
class RunResult:
    equipment: list[Equipment]
    tags: list[DrawingTag]
    findings: list[Finding]


def run(customer_dir: Path, profile: CustomerProfile) -> RunResult:
    equipment = load_equipment(customer_dir, profile.equipment_list)
    tags = load_tags(customer_dir, profile.drawing)
    return RunResult(equipment, tags, run_checks(profile, equipment, tags))
