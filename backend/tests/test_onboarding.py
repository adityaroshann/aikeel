"""The claims the demo makes, as tests.

1. Inferred profiles match ground truth for every customer (offline, no LLM).
2. The same generic checks find exactly the planted errors for every customer.
3. Onboarding a new customer produces a profile file and changes no engine code.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import pytest

from keel.engine import run
from keel.infer import infer_profile
from keel.profile import CustomerProfile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "customers"
CUSTOMERS = ["yard_a", "office_b", "hidden_c"]


def truth(c):
    return json.loads((DATA / c / "_truth.json").read_text())


@pytest.mark.parametrize("customer", CUSTOMERS)
def test_inferred_profile_matches_truth(customer):
    t = truth(customer)["profile"]
    prof, _ = infer_profile(DATA / customer)
    spec = prof.equipment_list
    assert spec.format == t["format"]
    assert spec.delimiter == t["delimiter"]
    assert spec.header_row == t["header_row"]
    for field, (source, scale) in t["columns"].items():
        assert spec.columns[field].source == source, field
        assert math.isclose(spec.columns[field].scale, scale), field
    assert prof.tag_convention.pattern == t["tag_pattern"]
    assert (prof.drawing.layer, prof.drawing.source, prof.drawing.attribute) == (t["layer"], t["source"], t["attribute"])


@pytest.mark.parametrize("customer", CUSTOMERS)
def test_rule_extracted(customer):
    t = truth(customer)["rule"]
    prof, _ = infer_profile(DATA / customer)
    assert len(prof.rules) == 1
    assert math.isclose(prof.rules[0].limit_kg, t["limit_kg"], rel_tol=1e-3)
    assert prof.rules[0].space == t["space"]


@pytest.mark.parametrize("customer", CUSTOMERS)
def test_checks_find_exactly_the_planted_errors(customer):
    prof, _ = infer_profile(DATA / customer)
    found = sorted([f.check, f.tag] for f in run(DATA / customer, prof).findings)
    assert found == truth(customer)["findings"]


def test_profile_yaml_roundtrip():
    prof, _ = infer_profile(DATA / "office_b")
    again = CustomerProfile.from_yaml(prof.to_yaml())
    assert again == prof
    assert re.compile(again.tag_convention.pattern)


def _engine_hash():
    h = hashlib.sha256()
    for p in sorted((ROOT / "keel").rglob("*.py")):
        h.update(p.read_bytes())
    return h.hexdigest()


def test_onboarding_new_customer_changes_no_code(tmp_path):
    before = _engine_hash()
    prof, _ = infer_profile(DATA / "hidden_c")
    prof.save(tmp_path / "hidden_c.yaml")
    result = run(DATA / "hidden_c", CustomerProfile.load(tmp_path / "hidden_c.yaml"))
    assert len(result.findings) == 5
    assert _engine_hash() == before
