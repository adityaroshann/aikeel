"""Thin wrappers that turn engine results into JSON for the web app and the copilot."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from keel.engine import RunResult, run
from keel.geometry import drawing_geometry
from keel.infer import LOW_CONFIDENCE, infer_profile
from keel.llm import LLM
from keel.profile import CustomerProfile


def onboard(cdir: Path, customer: str, use_claude: bool = False) -> dict:
    llm = LLM() if (use_claude and LLM.env_available()) else None
    t0 = time.perf_counter()
    profile, proposals = infer_profile(cdir, customer, llm=llm)
    elapsed = time.perf_counter() - t0
    return {
        "profile_yaml": profile.to_yaml(),
        "proposals": [p.model_dump(mode="json") for p in proposals],
        "low_confidence_threshold": LOW_CONFIDENCE,
        "elapsed_s": round(elapsed, 3),
        "claude_used": bool(llm),
        "claude_error": llm.last_error if llm else None,
    }


def parse_profile(text: str) -> CustomerProfile:
    return CustomerProfile.from_yaml(text)


def summarize(result: RunResult) -> dict:
    errs = sum(f.severity == "error" for f in result.findings)
    return {"equipment": len(result.equipment), "tags": len(result.tags),
            "errors": errs, "warnings": len(result.findings) - errs}


def check(cdir: Path, profile: CustomerProfile, with_geometry: bool = True) -> dict:
    result = run(cdir, profile)
    out = {
        "summary": summarize(result),
        "findings": [f.model_dump(mode="json") for f in result.findings],
        "equipment": [e.model_dump(mode="json") for e in result.equipment],
        "tags": [t.model_dump(mode="json") for t in result.tags],
    }
    if with_geometry:
        out["geometry"] = drawing_geometry(cdir / profile.drawing.file)
    return out


def finding_key(f: dict) -> tuple:
    return (f["check"], f.get("tag"))


def diff_findings(before: list[dict], after: list[dict]) -> dict:
    b, a = {finding_key(f): f for f in before}, {finding_key(f): f for f in after}
    return {"resolved": [b[k] for k in b if k not in a], "new": [a[k] for k in a if k not in b],
            "before": len(before), "after": len(after)}


def equipment_detail(result: RunResult, tag: str) -> Optional[dict]:
    rows = [e.model_dump(mode="json") for e in result.equipment if e.tag.lower() == tag.lower()]
    pos = [t.model_dump(mode="json") for t in result.tags if t.tag.lower() == tag.lower()]
    if not rows and not pos:
        return None
    return {"list_rows": rows, "drawing": pos}
