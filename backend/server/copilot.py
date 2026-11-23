"""Ask AIkeel: a Claude agent that reads the workspace through engine tools.

Design rules:
- Every tool is read-only. The one "write" tool, propose_profile_change, only *returns a
  proposal* (new profile + effect on findings). The engineer approves it in the UI.
- Streams Server-Sent-Event-style dicts: text deltas, tool status lines, proposals, done.
"""
from __future__ import annotations

import copy
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator, Optional

import anthropic
from pydantic import BaseModel, Field, ValidationError

from keel.engine import RunResult, run
from keel.infer import infer_profile
from keel.profile import CustomerProfile
from server.core import diff_findings, equipment_detail, summarize

MODEL = os.environ.get("AIKEEL_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("AIKEEL_EFFORT", "low")  # chat at a booth: keep it snappy
MAX_TOOL_ROUNDS = 6
MAX_HISTORY = 12

SYSTEM = """You are AIkeel, a design-review copilot for shipbuilding engineers.

You work inside ONE customer workspace: their equipment list, their general-arrangement (GA) drawing, their \
design-standards note, and the approved customer profile (YAML) that maps their data onto AIkeel's canonical \
model. A generic check engine runs on that data and produces findings.

How you work:
- Use the tools to look things up. Never invent tags, masses, rows or limits.
- Be brief and concrete: 2-6 sentences or a short list. Quote tags in backticks. Give masses in tonnes.
- You can never change anything yourself. To change the profile (a limit, a column mapping, a unit scale, \
the tag pattern, a drawing layer), call propose_profile_change. The engineer sees your proposal with its \
effect on the findings and decides. After proposing, say what you proposed and that it is waiting for approval.
- Fix the data mapping, not the facts: if the drawing or list is genuinely wrong (a missing pump, a duplicate \
tag), say what the engineer should correct in their source files.
- Stay on this workspace and ship design review. Politely decline anything unrelated.
- This is a prototype on synthetic data; say so if asked whether it is real."""


# ------------------------------------------------------------------ tool schemas
class Change(BaseModel):
    path: str = Field(description="Dotted path into the profile, e.g. 'rules[0].limit_kg', "
                                  "'tag_convention.pattern', 'equipment_list.columns.mass_kg.scale', 'drawing.layer'")
    value: Any


class ProposeInput(BaseModel):
    summary: str
    reason: str
    changes: list[Change]


class WhatIfInput(BaseModel):
    changes: list[Change]


class TagInput(BaseModel):
    tag: str


class FieldInput(BaseModel):
    field: Optional[str] = None


CHANGE_SCHEMA = {
    "type": "array", "minItems": 1, "maxItems": 5,
    "items": {"type": "object", "additionalProperties": False, "required": ["path", "value"],
              "properties": {"path": {"type": "string", "description": Change.model_fields["path"].description},
                             "value": {"description": "New value (number, string, or null)"}}},
}

TOOLS = [
    {"name": "list_findings", "eager_input_streaming": True,
     "description": "Current design-review findings for this workspace, with evidence.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "get_equipment", "eager_input_streaming": True,
     "description": "Look up one equipment tag: its equipment-list row(s) and where it is drawn on the GA.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["tag"],
                      "properties": {"tag": {"type": "string"}}}},
    {"name": "space_mass_report", "eager_input_streaming": True,
     "description": "Total equipment mass per space versus the customer's weight-limit rules, heaviest items first.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "explain_profile_decision", "eager_input_streaming": True,
     "description": "Why the Onboarding Autopilot proposed each profile decision (confidence + evidence). "
                    "Optionally filter by field name, e.g. 'columns.mass_kg' or 'rules'.",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "properties": {"field": {"type": "string"}}}},
    {"name": "what_if", "eager_input_streaming": True,
     "description": "Dry run: apply profile changes to a COPY and report how the findings would change. Changes nothing.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["changes"],
                      "properties": {"changes": CHANGE_SCHEMA}}},
    {"name": "propose_profile_change", "eager_input_streaming": True,
     "description": "Propose a profile change for the engineer to approve or reject. Does NOT apply it.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["summary", "reason", "changes"],
                      "properties": {"summary": {"type": "string", "description": "One line, e.g. 'Raise Engine Room limit to 30 t'"},
                                     "reason": {"type": "string"},
                                     "changes": CHANGE_SCHEMA}}},
]

LABELS = {"list_findings": "Reading the findings", "get_equipment": "Looking up {tag}",
          "space_mass_report": "Adding up mass per space", "explain_profile_decision": "Checking onboarding evidence",
          "what_if": "Running a what-if check", "propose_profile_change": "Drafting a proposal"}

INPUT_MODELS = {"get_equipment": TagInput, "explain_profile_decision": FieldInput, "what_if": WhatIfInput,
                "propose_profile_change": ProposeInput}


# ------------------------------------------------------------------ profile edits
_SEG = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?")


def apply_changes(profile: CustomerProfile, changes: list[Change]) -> CustomerProfile:
    data = copy.deepcopy(profile.model_dump(mode="json"))
    for ch in changes:
        parts = ch.path.strip().split(".")
        if parts and parts[0] == "columns":  # forgiving alias
            parts = ["equipment_list"] + parts
        node: Any = data
        for i, part in enumerate(parts):
            m = _SEG.fullmatch(part)
            if not m:
                raise ValueError(f"bad path segment {part!r} in {ch.path!r}")
            key, idx = m.group(1), m.group(2)
            last = i == len(parts) - 1
            if not isinstance(node, dict) or key not in node:
                raise ValueError(f"{ch.path!r}: no field {key!r}")
            if idx is None:
                if last:
                    node[key] = ch.value
                else:
                    node = node[key]
            else:
                seq = node[key]
                j = int(idx)
                if not isinstance(seq, list) or j >= len(seq):
                    raise ValueError(f"{ch.path!r}: index {j} out of range")
                if last:
                    seq[j] = ch.value
                else:
                    node = seq[j]
    return CustomerProfile.model_validate(data)


def yaml_diff(old: str, new: str) -> list[dict]:
    a, b = old.splitlines(), new.splitlines()
    import difflib
    out = []
    for line in difflib.unified_diff(a, b, lineterm="", n=1):
        if line.startswith(("---", "+++", "@@")):
            continue
        out.append({"op": line[0] if line[0] in "+-" else " ", "text": line[1:]})
    return out


# ------------------------------------------------------------------ the agent
class Copilot:
    def __init__(self, cdir: Path, customer: str, profile: CustomerProfile,
                 client: Optional[anthropic.Anthropic] = None) -> None:
        self.cdir, self.customer, self.profile = cdir, customer, profile
        self.client = client or anthropic.Anthropic()
        self._result: Optional[RunResult] = None

    @property
    def result(self) -> RunResult:
        if self._result is None:
            self._result = run(self.cdir, self.profile)
        return self._result

    # -- tools
    def _findings(self, result: RunResult) -> list[dict]:
        return [f.model_dump(mode="json", exclude={"x", "y"}) for f in result.findings]

    def tool(self, name: str, args: dict) -> tuple[str, Optional[dict]]:
        """Returns (tool_result_text, proposal_or_None)."""
        model = INPUT_MODELS.get(name)
        parsed = model.model_validate(args) if model else None
        if name == "list_findings":
            return json.dumps({"summary": summarize(self.result), "findings": self._findings(self.result)}), None
        if name == "get_equipment":
            d = equipment_detail(self.result, parsed.tag)
            return json.dumps(d or {"error": f"no tag {parsed.tag!r} in the list or on the drawing"}), None
        if name == "space_mass_report":
            by: dict[str, list] = defaultdict(list)
            for e in self.result.equipment:
                if e.mass_kg is not None:
                    by[e.space].append(e)
            rows = []
            for s, items in sorted(by.items()):
                limits = [r for r in self.profile.rules if r.space is None or r.space.lower() == s.lower()]
                total = sum(e.mass_kg for e in items)
                rows.append({"space": s, "total_t": round(total / 1000, 2),
                             "limits": [{"rule": r.id, "limit_t": round(r.limit_kg / 1000, 2),
                                         "rule_index": self.profile.rules.index(r), "text": r.source_text,
                                         "over": total > r.limit_kg} for r in limits],
                             "heaviest": [{"tag": e.tag, "name": e.name, "t": round(e.mass_kg / 1000, 2)}
                                          for e in sorted(items, key=lambda e: -e.mass_kg)[:4]]})
            return json.dumps(rows), None
        if name == "explain_profile_decision":
            _, props = infer_profile(self.cdir, self.customer)
            sel = [p.model_dump(mode="json") for p in props
                   if not parsed.field or parsed.field.lower() in p.field.lower()]
            return json.dumps({"approved_profile": self.profile.model_dump(mode="json"),
                               "autopilot_proposals": sel}), None
        if name in ("what_if", "propose_profile_change"):
            new_profile = apply_changes(self.profile, parsed.changes)
            new_result = run(self.cdir, new_profile)
            effect = diff_findings(self._findings(self.result), self._findings(new_result))
            if name == "what_if":
                return json.dumps({"effect": effect}), None
            old_yaml, new_yaml = self.profile.to_yaml(), new_profile.to_yaml()
            proposal = {"summary": parsed.summary, "reason": parsed.reason,
                        "changes": [c.model_dump(mode="json") for c in parsed.changes],
                        "profile_yaml": new_yaml, "diff": yaml_diff(old_yaml, new_yaml), "effect": effect}
            return json.dumps({"status": "proposal shown to the engineer; NOT applied", "effect": effect}), proposal
        raise ValueError(f"unknown tool {name}")

    # -- loop
    def context_block(self) -> str:
        s = summarize(self.result)
        return (f"<workspace customer=\"{self.customer}\" files=\"{', '.join(sorted(p.name for p in self.cdir.iterdir() if p.is_file() and not p.name.startswith('_')))}\">\n"
                f"summary: {json.dumps(s)}\n<profile_yaml>\n{self.profile.to_yaml()}</profile_yaml>\n</workspace>")

    def stream(self, history: list[dict]) -> Iterator[dict]:
        messages = clean_history(history)
        if not messages:
            yield {"type": "error", "message": "Ask a question to start."}
            return
        messages[-1] = {"role": "user", "content": f"{self.context_block()}\n\n{messages[-1]['content']}"}
        json_retries = 0
        rounds = 0
        while True:
            try:
                with self.client.beta.messages.stream(
                    model=MODEL, max_tokens=16000, system=SYSTEM, tools=TOOLS, messages=messages,
                    output_config={"effort": EFFORT},
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                ) as stream:
                    for event in stream:
                        if event.type == "text":
                            yield {"type": "text", "text": event.text}
                    response = stream.get_final_message()
                json_retries = 0
            except ValueError:
                json_retries += 1
                if json_retries > 2:
                    yield {"type": "error", "message": "The copilot sent malformed tool input. Try again."}
                    return
                continue
            except anthropic.AuthenticationError:
                yield {"type": "error", "message": "Copilot is offline (API key not accepted)."}
                return
            except anthropic.RateLimitError:
                yield {"type": "error", "message": "Copilot is busy (rate limited). Try again in a moment."}
                return
            except anthropic.APIStatusError as e:
                yield {"type": "error", "message": f"Copilot error ({e.status_code})."}
                return
            except anthropic.APIConnectionError:
                yield {"type": "error", "message": "Copilot could not reach Claude."}
                return

            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
                continue
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason == "refusal":
                yield {"type": "text", "text": "\n\nI can't help with that one."}
                break
            if not tool_uses:
                break
            if response.stop_reason == "max_tokens":
                yield {"type": "error", "message": "Answer was cut off. Try a narrower question."}
                return
            rounds += 1
            if rounds > MAX_TOOL_ROUNDS:
                yield {"type": "text", "text": "\n\n(Stopping here: too many lookups for one question.)"}
                break

            results = []
            for b in tool_uses:
                args = b.input if isinstance(b.input, dict) else {}
                yield {"type": "tool", "name": b.name,
                       "label": LABELS.get(b.name, b.name).format(tag=args.get("tag", "a tag"))}
                try:
                    text, proposal = self.tool(b.name, args)
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": text})
                    if proposal:
                        yield {"type": "proposal", **proposal}
                except (ValidationError, ValueError) as e:
                    results.append({"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                                    "content": f"Error: {e}"})
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": results})
        yield {"type": "done"}


def clean_history(history: list[dict]) -> list[dict]:
    """Plain-text turns only, alternating, starting with user, last MAX_HISTORY turns."""
    turns = []
    for m in history:
        role, content = m.get("role"), m.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str) or not content.strip():
            continue
        content = content[:4000]
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n\n" + content
        else:
            turns.append({"role": role, "content": content})
    turns = turns[-MAX_HISTORY:]
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    if turns and turns[-1]["role"] != "user":
        return []
    return turns


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
