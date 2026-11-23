"""Optional Claude layer. Only used for profile decisions the heuristics are unsure about.

Design choice: the demo must work fully offline (no key, no network). When a key is
present, low-confidence mappings are sent to Claude, which returns a structured,
schema-validated answer with a reason. The engineer still approves every decision.
"""
from __future__ import annotations

import json
import os
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5-5"


class ColumnChoice(BaseModel):
    field: Literal["tag", "name", "space", "mass_kg"]
    column: Optional[str]
    scale_to_kg: Optional[float]
    confidence: float
    reason: str


class ColumnMapping(BaseModel):
    choices: list[ColumnChoice]


class RuleChoice(BaseModel):
    id: str
    limit_kg: float
    space: Optional[str]
    source_text: str


class RuleList(BaseModel):
    rules: list[RuleChoice]


SYSTEM = (
    "You help onboard a new shipbuilding customer onto a design-review platform by mapping "
    "their data onto a canonical model. Be conservative: if the evidence is weak, say so with "
    "a low confidence. An engineer reviews every answer you give."
)


class LLM:
    def __init__(self, api_key: Optional[str] = None, model: str = MODEL) -> None:
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model
        self.last_error: Optional[str] = None

    @staticmethod
    def env_available() -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))

    def _parse(self, user: str, schema: type[BaseModel]):
        try:
            resp = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=8000,
                system=SYSTEM,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as e:
            self.last_error = f"authentication failed: {e.message}"
            return None
        except anthropic.RateLimitError:
            self.last_error = "rate limited"
            return None
        except anthropic.APIStatusError as e:
            self.last_error = f"API error {e.status_code}: {e.message}"
            return None
        except anthropic.APIConnectionError:
            self.last_error = "could not reach the API"
            return None
        if resp.stop_reason == "refusal":
            self.last_error = "request declined"
            return None
        return resp.parsed_output

    def map_columns(self, headers: list[str], sample_rows: list[list[str]], fields: list[str],
                    context: str = "") -> Optional[ColumnMapping]:
        user = (
            "A customer's equipment list has these columns:\n"
            f"{json.dumps(headers)}\n\nSample rows:\n{json.dumps(sample_rows, ensure_ascii=False)}\n\n"
            f"{('Other customer documents mention: ' + context) if context else ''}\n\n"
            "Map these canonical fields to a column (or null if none fits): "
            f"{', '.join(fields)}.\n"
            "Canonical meanings: tag = unique equipment identifier; name = human description; "
            "space = compartment/room/location; mass_kg = equipment mass. For mass_kg also give "
            "scale_to_kg, the factor that converts the column's unit to kilograms (e.g. tonnes -> 1000, "
            "lbs -> 0.45359237). Give confidence 0-1 and a one-sentence reason citing the evidence."
        )
        return self._parse(user, ColumnMapping)

    def parse_rules(self, text: str, spaces: list[str]) -> Optional[RuleList]:
        user = (
            "Extract every equipment MASS/WEIGHT LIMIT rule from this design-standard note. "
            "Convert limits to kilograms. If the rule names one space, set space to the matching name "
            f"from this list exactly: {json.dumps(spaces)}; if it applies to every space set space to null. "
            "Ignore rules that are not mass limits. Copy the rule sentence into source_text.\n\n"
            f"---\n{text}\n---"
        )
        return self._parse(user, RuleList)
