"""Generate three SYNTHETIC customers that describe the same vessel in deliberately different ways.

Each customer gets:
  equipment_list.(csv|xlsx)   their own columns, units, header layout and tag convention
  ga_drawing.dxf              General Arrangement plan with their own layers and tag storage
  standards.md                an internal design-standard note containing one weight rule
  _truth.json                 ground truth (expected profile + planted findings), used by the tests

Planted errors (same kinds for every customer, so the same generic checks must find them):
  1. equipment in the list but missing from the drawing
  2. a tag on the drawing that is not in the list
  3. a duplicate tag in the list
  4. a tag that breaks the customer's own naming convention
  5. Engine Room equipment mass over the customer's limit

Run:  python scripts/make_sample_data.py
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import ezdxf
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "customers"

# key, name, type, mass_kg, space_key, sfi
LIBRARY = [
    ("ME", "Main Engine", "ENG", 18000, "ER", "601"),
    ("DG1", "Diesel Generator No.1", "GEN", 4500, "ER", "611"),
    ("DG2", "Diesel Generator No.2", "GEN", 4500, "ER", "611"),
    ("FOP", "Fuel Oil Purifier", "SEP", 900, "ER", "721"),
    ("LOP", "Lube Oil Purifier", "SEP", 850, "ER", "722"),
    ("AC1", "Starting Air Compressor No.1", "CMP", 350, "ER", "751"),
    ("AC2", "Starting Air Compressor No.2", "CMP", 350, "ER", "751"),
    ("FTP", "Fuel Oil Transfer Pump", "PMP", 220, "ER", "721"),
    ("LTP", "Lube Oil Transfer Pump", "PMP", 180, "ER", "722"),
    ("SF", "ER Supply Fan", "FAN", 300, "ER", "781"),
    ("EF", "ER Exhaust Fan", "FAN", 300, "ER", "781"),
    ("BP", "Bilge Pump", "PMP", 260, "PR", "801"),
    ("FP", "Fire Pump", "PMP", 410, "PR", "811"),
    ("BLP", "Ballast Pump", "PMP", 520, "PR", "802"),
    ("OWS", "Oily Water Separator", "SEP", 650, "PR", "803"),
    ("FWG", "Fresh Water Generator", "UNT", 1200, "PR", "731"),
    ("SG", "Steering Gear Hydraulic Unit", "UNT", 2800, "SG", "571"),
    ("EG", "Emergency Generator", "GEN", 2200, "EG", "612"),
    ("HV", "HVAC Unit", "UNT", 1500, "AC", "871"),
    ("STP", "Sewage Treatment Plant", "UNT", 1100, "AC", "806"),
]
EXTRA_ON_DRAWING = ("HWC", "Hot Water Calorifier", "UNT", 400, "PR", "872")

IDX_NOT_DRAWN = 12      # Fire Pump
IDX_MALFORMED = 5       # Starting Air Compressor No.1
IDX_DUPLICATED = 8      # Lube Oil Transfer Pump

# x-ranges of compartments along the ship (aft -> fwd)
SPACE_X = {"SG": (0, 12), "ER": (12, 42), "PR": (42, 58), "EG": (58, 71), "AC": (71, 86)}

TYPE_LETTER = {"ENG": "E", "GEN": "G", "SEP": "S", "CMP": "C", "PMP": "P", "FAN": "F", "UNT": "U"}


class Customer:
    key: str
    title: str
    space_names: dict[str, str]
    malformed: str = ""

    def tag(self, item, counters) -> str:  # pragma: no cover - overridden
        raise NotImplementedError


class YardA(Customer):
    key = "yard_a"
    title = "Yard A (shipyard)"
    space_names = {"SG": "Steering Gear Room", "ER": "Engine Room", "PR": "Pump Room",
                   "EG": "Emergency Generator Room", "AC": "Accommodation"}

    def tag(self, item, counters):
        letter = TYPE_LETTER[item[2]]
        counters[letter] = counters.get(letter, 100) + 1
        return f"{letter}-{counters[letter]}"

    def malform(self, tag):  # C-101 -> C101
        return tag.replace("-", "")


class OfficeB(Customer):
    key = "office_b"
    title = "Office B (design office)"
    space_names = {"SG": "STEER RM", "ER": "ENG RM", "PR": "PUMP RM", "EG": "EM GEN RM", "AC": "ACCOM"}

    def tag(self, item, counters):
        sfi, typ = item[5], item[2]
        counters[sfi] = counters.get(sfi, 0) + 1
        counters[typ] = counters.get(typ, 0) + 1
        return f"{sfi}.{counters[sfi]:02d}-{typ}-{counters[typ]:02d}"

    def malform(self, tag):  # 751.01-CMP-01 -> 751.1-CMP-01
        head, rest = tag.split(".", 1)
        return f"{head}.{rest[1:]}" if rest.startswith("0") else tag + "X"


class HiddenC(Customer):
    key = "hidden_c"
    title = "Customer C (onboarded live in the demo)"
    space_names = {"SG": "Steering Gear Room", "ER": "Engine Room", "PR": "Pump Room",
                   "EG": "Emergency Generator Room", "AC": "Accommodation"}

    def tag(self, item, counters):
        counters["n"] = counters.get("n", 0) + 1
        return f"{item[4]}-{item[2][:2]}-{counters['n']:04d}"

    def malform(self, tag):  # ER-CM-0006 -> ER-CM-06
        a, b, n = tag.split("-")
        return f"{a}-{b}-{n[-2:]}"


def build_rows(cust: Customer):
    counters: dict = {}
    rows = []
    for i, item in enumerate(LIBRARY):
        tag = cust.tag(item, counters)
        if i == IDX_MALFORMED:
            tag = cust.malform(tag)
        rows.append({"tag": tag, "name": item[1], "space": cust.space_names[item[4]],
                     "space_key": item[4], "mass_kg": item[3], "drawn": i != IDX_NOT_DRAWN})
    dup = rows[IDX_DUPLICATED]
    rows.append({**dup, "name": dup["name"] + " (standby)", "drawn": False})
    extra = EXTRA_ON_DRAWING
    extra_row = {"tag": cust.tag(extra, counters), "name": extra[1], "space": cust.space_names[extra[4]],
                 "space_key": extra[4], "mass_kg": extra[3], "drawn": True}
    return rows, extra_row


# ---------------------------------------------------------------- equipment lists

def write_list_a(path: Path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Tag", "Desc", "Room", "Weight_kg"])
        for r in rows:
            w.writerow([r["tag"], r["name"], r["space"], r["mass_kg"]])


def write_list_b(path: Path, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Equipment Register"
    ws.append(["Project: 85 m Offshore Supply Vessel (SYNTHETIC) - Equipment Register"])
    ws.append(["Rev C", "Issued for review"])
    ws.append([])
    ws.append(["Item No.", "Description", "Location", "Mass (t)", "Supplier"])
    for r in rows:
        ws.append([r["tag"], r["name"], r["space"], round(r["mass_kg"] / 1000, 3), "TBD"])
    wb.save(path)


def write_list_c(path: Path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Equipment ID", "Name", "Compartment", "Weight (lbs)", "Remarks"])
        for r in rows:
            w.writerow([r["tag"], r["name"], r["space"], f"{r['mass_kg'] / 0.45359237:,.0f}", ""])


# ---------------------------------------------------------------- drawings

def layout_positions(rows):
    """Place drawn equipment in a grid inside its compartment."""
    by_space: dict[str, list] = {}
    for r in rows:
        if r["drawn"]:
            by_space.setdefault(r["space_key"], []).append(r)
    pos = {}
    for sk, items in by_space.items():
        x0, x1 = SPACE_X[sk]
        ys = [4.0, 0.0, -4.0] if len(items) > 2 else [2.5, -2.5]
        cols = math.ceil(len(items) / len(ys))
        for k, r in enumerate(items):
            c, rr = divmod(k, len(ys))
            pos[r["tag"]] = (x0 + (x1 - x0) * (c + 0.5) / cols, ys[rr])
    return pos


def draw_common(msp, layers, cust: Customer):
    hull, bhd, notes, title = layers
    msp.add_lwpolyline([(0, -8), (86, -8), (100, 0), (86, 8), (0, 8)], close=True, dxfattribs={"layer": hull})
    for sk, (x0, _) in SPACE_X.items():
        if x0 > 0:
            msp.add_line((x0, -8), (x0, 8), dxfattribs={"layer": bhd})
        msp.add_text(cust.space_names[sk].upper(), height=0.42,
                     dxfattribs={"layer": notes}).set_placement((x0 + 0.5, 6.6))
    msp.add_lwpolyline([(0, -15), (34, -15), (34, -10), (0, -10)], close=True, dxfattribs={"layer": title})


def write_dxf(path: Path, cust: Customer, rows):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    pos = layout_positions(rows)

    if cust.key == "yard_a":
        for name, color in [("HULL", 7), ("BHD", 8), ("EQ-OUTLINE", 4), ("EQ-MECH", 1), ("NOTES", 3), ("TITLE", 7)]:
            doc.layers.add(name, color=color)
        draw_common(msp, ("HULL", "BHD", "NOTES", "TITLE"), cust)
        for tag, (x, y) in pos.items():
            msp.add_lwpolyline([(x - 1.5, y - 0.8), (x + 1.5, y - 0.8), (x + 1.5, y + 0.8), (x - 1.5, y + 0.8)],
                               close=True, dxfattribs={"layer": "EQ-OUTLINE"})
            msp.add_text(tag, height=0.5, dxfattribs={"layer": "EQ-MECH"}).set_placement(
                (x, y - 1.5), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        for i, t in enumerate(["VESSEL: 85 m OSV (SYNTHETIC)", "DWG: GA-100  REV C", "YARD A"]):
            msp.add_text(t, height=0.7, dxfattribs={"layer": "TITLE"}).set_placement((1, -11.2 - i * 1.2))

    elif cust.key == "office_b":
        for name, color in [("S_HULL", 7), ("S_BHD", 8), ("M_EQUIP", 5), ("A_ROOMS", 3), ("A_TITLE", 7)]:
            doc.layers.add(name, color=color)
        draw_common(msp, ("S_HULL", "S_BHD", "A_ROOMS", "A_TITLE"), cust)
        blk = doc.blocks.new("EQUIP")
        blk.add_lwpolyline([(-1.5, -0.8), (1.5, -0.8), (1.5, 0.8), (-1.5, 0.8)], close=True)
        blk.add_attdef("TAG", (0, -1.5), dxfattribs={"height": 0.45})
        blk.add_attdef("DESC", (0, 0), dxfattribs={"height": 0.3})
        tb = doc.blocks.new("TITLEBLOCK")
        tb.add_attdef("DWG_NO", (1, 3.5), dxfattribs={"height": 0.7})
        tb.add_attdef("REV", (1, 2.3), dxfattribs={"height": 0.7})
        tb.add_attdef("CLIENT", (1, 1.1), dxfattribs={"height": 0.7})
        names = {r["tag"]: r["name"] for r in rows}
        for tag, (x, y) in pos.items():
            ins = msp.add_blockref("EQUIP", (x, y), dxfattribs={"layer": "M_EQUIP"})
            ins.add_auto_attribs({"TAG": tag, "DESC": names[tag][:14]})
        msp.add_blockref("TITLEBLOCK", (0, -15), dxfattribs={"layer": "A_TITLE"}).add_auto_attribs(
            {"DWG_NO": "GA-B-0100", "REV": "C", "CLIENT": "SYNTHETIC OSV"})

    else:  # hidden_c
        for name, color in [("Structure", 7), ("Machinery", 2), ("Annotations", 3), ("Border", 7)]:
            doc.layers.add(name, color=color)
        draw_common(msp, ("Structure", "Structure", "Annotations", "Border"), cust)
        for tag, (x, y) in pos.items():
            msp.add_circle((x, y), 1.0, dxfattribs={"layer": "Machinery"})
            msp.add_mtext(tag, dxfattribs={"layer": "Machinery", "char_height": 0.45}).set_location(
                (x, y - 1.4), attachment_point=ezdxf.enums.MTextEntityAlignment.TOP_CENTER)
        msp.add_mtext("GENERAL ARRANGEMENT\\PCustomer C - SYNTHETIC",
                      dxfattribs={"layer": "Border", "char_height": 0.7}).set_location((1, -10.5))
    doc.saveas(path)


# ---------------------------------------------------------------- standards notes

STANDARDS = {
    "yard_a": """# Yard A - Internal Outfitting Standard YS-4 (synthetic)

YS-4.1  All equipment shall carry a unique tag of the form <type letter>-<3 digits>.
YS-4.2  Total installed equipment mass in the Engine Room shall not exceed 28 t.
YS-4.3  Seats for rotating machinery require vibration isolation.
""",
    "office_b": """# Office B - Design Standard DS (synthetic)

DS-10: Item numbers follow SFI group, sequence, equipment type and running number.
DS-11: No single room may carry more than 25,000 kg of equipment.
DS-12: All drawings are issued in DXF and PDF.
""",
    "hidden_c": """# Customer C - Machinery Arrangement Rules (synthetic)

Rule 6 - Equipment IDs begin with the compartment code.
Rule 7 - Engine Room equipment weight limit: 60,000 lbs.
""",
}
RULE_TRUTH = {
    "yard_a": {"limit_kg": 28000, "space": "Engine Room"},
    "office_b": {"limit_kg": 25000, "space": None},
    "hidden_c": {"limit_kg": 60000 * 0.45359237, "space": "Engine Room"},
}

TRUTH_PROFILE = {
    "yard_a": {"format": "csv", "delimiter": ",", "header_row": 0,
               "columns": {"tag": ["Tag", 1.0], "name": ["Desc", 1.0], "space": ["Room", 1.0],
                           "mass_kg": ["Weight_kg", 1.0]},
               "tag_pattern": r"^[A-Z]-\d{3}$", "layer": "EQ-MECH", "source": "text", "attribute": None},
    "office_b": {"format": "xlsx", "delimiter": ",", "header_row": 3,
                 "columns": {"tag": ["Item No.", 1.0], "name": ["Description", 1.0], "space": ["Location", 1.0],
                             "mass_kg": ["Mass (t)", 1000.0]},
                 "tag_pattern": r"^\d{3}\.\d{2}-[A-Z]{3}-\d{2}$", "layer": "M_EQUIP", "source": "attrib",
                 "attribute": "TAG"},
    "hidden_c": {"format": "csv", "delimiter": ";", "header_row": 0,
                 "columns": {"tag": ["Equipment ID", 1.0], "name": ["Name", 1.0], "space": ["Compartment", 1.0],
                             "mass_kg": ["Weight (lbs)", 0.45359237]},
                 "tag_pattern": r"^[A-Z]{2}-[A-Z]{2}-\d{4}$", "layer": "Machinery", "source": "mtext",
                 "attribute": None},
}


def main():
    for cust in (YardA(), OfficeB(), HiddenC()):
        d = OUT / cust.key
        d.mkdir(parents=True, exist_ok=True)
        for old in d.iterdir():  # clear files, keep the folder (OneDrive locks folder deletes)
            if old.is_file():
                old.unlink()
        rows, extra = build_rows(cust)
        if cust.key == "yard_a":
            write_list_a(d / "equipment_list.csv", rows)
        elif cust.key == "office_b":
            write_list_b(d / "equipment_list.xlsx", rows)
        else:
            write_list_c(d / "equipment_list.csv", rows)
        write_dxf(d / "ga_drawing.dxf", cust, rows + [extra])
        (d / "standards.md").write_text(STANDARDS[cust.key], encoding="utf-8")

        er = cust.space_names["ER"]
        truth = {
            "title": cust.title,
            "profile": TRUTH_PROFILE[cust.key],
            "rule": RULE_TRUTH[cust.key],
            "findings": sorted([
                ["missing_on_drawing", rows[IDX_NOT_DRAWN]["tag"]],
                ["missing_from_list", extra["tag"]],
                ["duplicate_tag", rows[IDX_DUPLICATED]["tag"]],
                ["tag_convention", rows[IDX_MALFORMED]["tag"]],
                ["rule:max_total_mass_per_space", er],
            ]),
        }
        (d / "_truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
        print(f"wrote {d.relative_to(ROOT)}  ({len(rows)} list rows)")


if __name__ == "__main__":
    main()
