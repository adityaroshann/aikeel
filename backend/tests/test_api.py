"""API tests. The copilot runs against a scripted fake Claude client (no credits spent)."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from keel.profile import CustomerProfile
from main import app
from server.copilot import Change, Copilot, apply_changes, clean_history

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "customers"
client = TestClient(app)


def truth(c):
    return json.loads((DATA / c / "_truth.json").read_text(encoding="utf-8"))


def test_workspaces_and_health():
    ws = client.get("/api/workspaces").json()
    assert {w["id"] for w in ws["workspaces"]} == {"yard_a", "office_b", "hidden_c"}
    assert all("_truth.json" not in w["files"] for w in ws["workspaces"])
    assert client.get("/api/health").json()["ok"]


@pytest.mark.parametrize("c", ["yard_a", "office_b", "hidden_c"])
def test_onboard_then_check(c):
    r = client.post("/api/onboard", json={"workspace": c}).json()
    prof = CustomerProfile.from_yaml(r["profile_yaml"])
    t = truth(c)["profile"]
    assert prof.equipment_list.format == t["format"] and prof.drawing.layer == t["layer"]
    assert len(r["proposals"]) >= 8
    chk = client.post("/api/check", json={"workspace": c, "profile_yaml": r["profile_yaml"]}).json()
    assert len(chk["findings"]) == 5
    g = chk["geometry"]
    assert g["texts"] and (g["lines"] or g["polylines"]) and g["bbox"]["maxx"] > g["bbox"]["minx"]


def test_upload_path_matches_bundled():
    files = [{"name": p.name, "b64": base64.b64encode(p.read_bytes()).decode()}
             for p in (DATA / "hidden_c").iterdir() if not p.name.startswith("_")]
    r = client.post("/api/onboard", json={"files": files}).json()
    chk = client.post("/api/check", json={"files": files, "profile_yaml": r["profile_yaml"]}).json()
    assert len(chk["findings"]) == 5


def test_rejects_bad_input():
    assert client.post("/api/onboard", json={"workspace": "../etc"}).status_code == 400
    bad = [{"name": "evil.exe", "b64": base64.b64encode(b"x").decode()}]
    assert client.post("/api/onboard", json={"files": bad}).status_code == 400
    assert client.post("/api/check", json={"workspace": "yard_a", "profile_yaml": "nope: ["}).status_code == 422


def test_apply_changes_and_history():
    prof = CustomerProfile.load(ROOT / "profiles" / "yard_a.yaml")
    new = apply_changes(prof, [Change(path="rules[0].limit_kg", value=999999)])
    assert new.rules[0].limit_kg == 999999 and prof.rules[0].limit_kg != 999999
    with pytest.raises(ValueError):
        apply_changes(prof, [Change(path="rules[9].limit_kg", value=1)])
    h = clean_history([{"role": "assistant", "content": "hi"}, {"role": "user", "content": "q"}])
    assert h == [{"role": "user", "content": "q"}]


# ---------------------------------------------------------------- fake Claude
class FakeStream:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        for b in self.msg.content:
            if b.type == "text":
                yield NS(type="text", text=b.text)

    def get_final_message(self):
        return self.msg


class FakeClient:
    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.beta = NS(messages=NS(stream=self._stream))

    def _stream(self, **kw):
        self.calls.append(kw)
        return FakeStream(self.script.pop(0))


def test_copilot_proposal_round_trip():
    prof = CustomerProfile.load(ROOT / "profiles" / "yard_a.yaml")
    script = [
        NS(stop_reason="tool_use", content=[
            NS(type="text", text="Checking."),
            NS(type="tool_use", id="t1", name="space_mass_report", input={})]),
        NS(stop_reason="tool_use", content=[
            NS(type="tool_use", id="t2", name="propose_profile_change",
               input={"summary": "Raise limit", "reason": "engineer said so",
                      "changes": [{"path": "rules[0].limit_kg", "value": 10_000_000}]})]),
        NS(stop_reason="end_turn", content=[NS(type="text", text="Proposed; waiting for approval.")]),
    ]
    fake = FakeClient(script)
    bot = Copilot(DATA / "yard_a", "yard_a", prof, client=fake)
    events = list(bot.stream([{"role": "user", "content": "Raise the engine room limit"}]))
    types = [e["type"] for e in events]
    assert types[-1] == "done" and "proposal" in types and types.count("tool") == 2
    p = next(e for e in events if e["type"] == "proposal")
    assert p["effect"]["after"] == p["effect"]["before"] - 1  # the weight finding resolves
    assert any(f["check"].startswith("rule:") for f in p["effect"]["resolved"])
    assert CustomerProfile.from_yaml(p["profile_yaml"]).rules[0].limit_kg == 10_000_000
    assert prof.rules[0].limit_kg != 10_000_000  # never applied
    # tool results were sent back to the model
    last = fake.calls[-1]["messages"]
    assert last[-1]["role"] == "user" and last[-1]["content"][0]["type"] == "tool_result"
