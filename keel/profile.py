"""CustomerProfile: the ONLY per-customer artifact.

It maps a customer's files, column names, units, tag convention, drawing layers and
design rules onto the canonical model. It is plain YAML, so engineers can review and
version it, and it can live on-prem next to the customer's data.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field

CANONICAL_FIELDS = ("tag", "name", "space", "mass_kg")


class ColumnMap(BaseModel):
    source: str
    scale: float = 1.0  # multiply the source value by this to get canonical units (kg for mass)


class EquipmentListSpec(BaseModel):
    file: str
    format: Literal["csv", "xlsx"]
    delimiter: str = ","
    sheet: Optional[str] = None
    header_row: int = 0
    columns: dict[str, ColumnMap]


class TagConvention(BaseModel):
    pattern: str
    example: Optional[str] = None


class DrawingSpec(BaseModel):
    file: str
    layer: str
    source: Literal["text", "mtext", "attrib"]
    attribute: Optional[str] = None


class Rule(BaseModel):
    id: str
    type: Literal["max_total_mass_per_space"] = "max_total_mass_per_space"
    limit_kg: float
    space: Optional[str] = None  # None = applies to every space
    source_text: str = ""


class CustomerProfile(BaseModel):
    customer: str
    equipment_list: EquipmentListSpec
    tag_convention: TagConvention
    drawing: DrawingSpec
    rules: list[Rule] = Field(default_factory=list)

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.model_dump(mode="json"), sort_keys=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, text: str) -> "CustomerProfile":
        return cls.model_validate(yaml.safe_load(text))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_yaml(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "CustomerProfile":
        return cls.from_yaml(path.read_text(encoding="utf-8"))


class Proposal(BaseModel):
    """One inferred profile decision, shown to the engineer for approval."""

    field: str
    value: Any
    confidence: float
    evidence: str
    method: Literal["heuristic", "llm"] = "heuristic"
