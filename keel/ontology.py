"""Canonical data model. Every customer's data is translated INTO this shape.

The checks only ever see these types, which is why they never need per-customer code.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class Equipment(BaseModel):
    tag: str
    name: str
    space: str
    mass_kg: Optional[float] = None
    row: int  # source row in the customer's file, for traceability


class DrawingTag(BaseModel):
    tag: str
    x: float
    y: float
    layer: str


Severity = Literal["error", "warning"]


class Finding(BaseModel):
    check: str
    severity: Severity
    tag: Optional[str] = None
    message: str
    evidence: str = ""
    x: Optional[float] = None
    y: Optional[float] = None
