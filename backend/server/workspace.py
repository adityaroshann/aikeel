"""Resolve a request to a customer directory: a bundled sample, or uploaded files in a temp dir.

The API is stateless. Uploaded files travel with every request (base64) and live in a
per-request temp directory that is deleted afterwards.
"""
from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Iterator, Optional

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "customers"
ENGINE = ROOT / "keel"

ALLOWED = {".csv", ".xlsx", ".dxf", ".md", ".txt"}
MAX_TOTAL_BYTES = 5 * 1024 * 1024
MAX_FILES = 6

META = {
    "yard_a": {"name": "Yard A", "kind": "Shipyard",
               "blurb": "CSV register in kg, tags like P-101, plain text tags on layer EQ-MECH."},
    "office_b": {"name": "Design Office B", "kind": "Design office",
                 "blurb": "Excel register with a title block, tonnes, SFI-style tags, block attributes."},
    "hidden_c": {"name": "Customer C", "kind": "New customer",
                 "blurb": "Semicolon CSV in pounds, ER-PU-0007 style tags, MTEXT on layer Machinery."},
}


class UploadedFile(BaseModel):
    name: str
    b64: str


class Source(BaseModel):
    workspace: Optional[str] = None
    files: list[UploadedFile] = Field(default_factory=list)


class SourceError(ValueError):
    pass


def list_workspaces() -> list[dict]:
    out = []
    for d in sorted(p for p in DATA.iterdir() if p.is_dir()):
        meta = META.get(d.name, {"name": d.name, "kind": "Customer", "blurb": ""})
        files = sorted(p.name for p in d.iterdir() if p.is_file() and not p.name.startswith("_"))
        seed = ROOT / "profiles" / f"{d.name}.yaml"
        out.append({"id": d.name, **meta, "files": files,
                    "seed_profile": seed.read_text(encoding="utf-8") if seed.exists() else None})
    return out


def _safe_name(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._ -]+", "_", base).strip(" .")
    if not base or base.startswith("_"):
        raise SourceError(f"invalid file name: {name!r}")
    if Path(base).suffix.lower() not in ALLOWED:
        raise SourceError(f"{base}: only {', '.join(sorted(ALLOWED))} files are accepted")
    return base


@contextlib.contextmanager
def customer_dir(src: Source) -> Iterator[tuple[Path, str]]:
    """Yield (directory, customer id) for the request."""
    if src.workspace and not src.files:
        if not re.fullmatch(r"[a-z0-9_]+", src.workspace) or not (DATA / src.workspace).is_dir():
            raise SourceError(f"unknown workspace {src.workspace!r}")
        yield DATA / src.workspace, src.workspace
        return
    if not src.files:
        raise SourceError("send a workspace id or upload files")
    if len(src.files) > MAX_FILES:
        raise SourceError(f"at most {MAX_FILES} files")
    total = 0
    with tempfile.TemporaryDirectory(prefix="aikeel_") as tmp:
        for f in src.files:
            name = _safe_name(f.name)
            try:
                data = base64.b64decode(f.b64, validate=True)
            except (binascii.Error, ValueError):
                raise SourceError(f"{name}: not valid base64") from None
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise SourceError("upload is larger than 5 MB")
            (Path(tmp) / name).write_bytes(data)
        yield Path(tmp), "uploaded"


def engine_fingerprint() -> dict:
    h, lines, files = hashlib.sha256(), 0, 0
    for p in sorted(ENGINE.rglob("*.py")):
        b = p.read_bytes()
        h.update(b)
        lines += b.count(b"\n")
        files += 1
    return {"hash": h.hexdigest()[:12], "files": files, "lines": lines}


def truth(workspace: str) -> Optional[dict]:
    p = DATA / workspace / "_truth.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
