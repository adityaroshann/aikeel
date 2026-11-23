# ⚓ AIkeel: onboard any shipyard in an afternoon, not a quarter

> Built for **Genesis T-Minus30**. AIkeel is a mock startup and a working prototype, and it uses synthetic data.

**In one line:** AIkeel reads a new shipbuilding customer's messy files, proposes how that customer does things, has an engineer approve it, and then runs the same design-checking engine for every customer, with zero custom code.

**Problem.** Every yard and design office describes the same ship differently:
- different equipment-list spreadsheets, columns, units and header layouts
- different tagging conventions (`P-101` vs `721.01-PMP-02` vs `ER-PU-0007`)
- different CAD layer names and ways of storing tags (plain text, MTEXT, block attributes)
- different internal design standards

If each difference turns into custom code, every new customer costs engineering time and forks the codebase.

**Approach.**
1. **Canonical model** (`keel/ontology.py`). The checks only ever see this.
2. **Customer profile** (`profiles/<customer>.yaml`). The *only* per-customer artifact: plain, reviewable, versionable YAML that can live on-prem next to the customer's data.
3. **Onboarding Autopilot** (`keel/infer.py`, the AIkeel engine). Proposes the profile from sample files. Each decision comes with a confidence score and evidence. Heuristics run first, offline. Claude is optional and only sees low-confidence decisions. **An engineer approves every decision.**
4. **Generic checks** (`keel/checks.py`). They run unchanged for every customer:
   - list ↔ drawing consistency
   - duplicate tags
   - the customer's own tag convention
   - the customer's own weight limits, parsed from their standards note

```
customer files ──► Autopilot ──► proposed profile ──► engineer review ──► approved profile.yaml
                                                                              │
customer files ──► adapters (driven by profile) ──► canonical model ──► generic checks ──► findings
```

## Run it
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python scripts/make_sample_data.py      # 3 synthetic customers with planted errors
pytest -q                               # 11 tests: inference matches ground truth, checks find exactly the planted errors
streamlit run app.py
```
Optional: set `ANTHROPIC_API_KEY` (or paste a key in the sidebar) to send low-confidence decisions to Claude.

## What the tests prove
- For all three customers, the inferred profile matches ground truth: format, delimiter, header row, column mapping, unit conversion, tag pattern, drawing layer and storage type, weight rule.
- The same check code finds **exactly** the 5 planted errors for every customer.
- Onboarding a new customer produces one YAML file and changes **zero** engine files (checked by hashing `keel/`).

## Honest limits
- Data is synthetic (an 85 m OSV-like layout). Real GA drawings have xrefs, nested blocks and DWG files, and a lot of the information lives in 3D models.
- Covers one document pair (equipment list ↔ GA) and one rule type. The profile pattern extends to PLM metadata, class-rule packs and more check types.
- Not affiliated with any company. Independent project built for Genesis T-Minus30.
