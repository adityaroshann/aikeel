"""Equipment list (CSV / XLSX) -> canonical Equipment. Driven entirely by the profile."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from keel.ontology import Equipment
from keel.profile import EquipmentListSpec


def read_raw(path: Path, fmt: str, delimiter: str = ",", sheet: Optional[str] = None) -> pd.DataFrame:
    """Read a sheet with NO header interpretation (header detection is the inferencer's job)."""
    if fmt == "xlsx":
        return pd.read_excel(path, sheet_name=sheet or 0, header=None, dtype=str)
    return pd.read_csv(path, sep=delimiter, header=None, dtype=str, keep_default_na=False)


def to_number(value) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip().replace(",", "").replace(" ", "")
    if s in ("", "nan", "None", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_equipment(customer_dir: Path, spec: EquipmentListSpec) -> list[Equipment]:
    raw = read_raw(customer_dir / spec.file, spec.format, spec.delimiter, spec.sheet)
    header = [str(h).strip() for h in raw.iloc[spec.header_row].tolist()]
    body = raw.iloc[spec.header_row + 1:]

    def col(field: str) -> Optional[int]:
        cmap = spec.columns.get(field)
        return header.index(cmap.source) if cmap and cmap.source in header else None

    idx = {f: col(f) for f in ("tag", "name", "space", "mass_kg")}
    if idx["tag"] is None:
        raise ValueError(f"tag column {spec.columns.get('tag')} not found in header {header}")

    out = []
    for offset, (_, r) in enumerate(body.iterrows()):
        vals = r.tolist()
        tag = str(vals[idx["tag"]]).strip()
        if not tag or tag.lower() == "nan":
            continue
        get = lambda f: "" if idx[f] is None else str(vals[idx[f]]).strip()  # noqa: E731
        mass = to_number(vals[idx["mass_kg"]]) if idx["mass_kg"] is not None else None
        if mass is not None:
            mass *= spec.columns["mass_kg"].scale
        out.append(Equipment(tag=tag, name=get("name"), space=get("space"), mass_kg=mass,
                             row=spec.header_row + 2 + offset))
    return out
