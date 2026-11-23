# ⚓ AIkeel: onboard any shipyard's data without new code

> A prototype built for **Genesis T-Minus30** in St. John's, Newfoundland. All data is synthetic.

Software that checks ship designs has to read each customer's own files, and every shipyard keeps them differently: CSV or Excel, kg or tonnes or pounds, `P-101` or `721.01-PMP-02` or `ER-PU-0007`, tags stored as text or MTEXT or block attributes, and its own design standards. Usually every new customer means custom integration code.

**AIkeel turns onboarding into one reviewed config file:**

1. **Upload.** Send in the customer's equipment list, GA drawing (DXF) and standards note.
2. **Propose.** The Onboarding Autopilot infers the format, columns, units, tag convention, drawing layer and weight rules. Each decision comes with evidence and a confidence score.
3. **Approve.** An engineer reviews and approves one YAML profile.
4. **Review.** The same check engine runs for every customer. It finds equipment missing from the list or the drawing, duplicate tags, broken tag conventions and overweight spaces.

**Ask AIkeel** is a Claude copilot with tool access to the engine. It explains findings and drafts profile changes. Each change is shown with its effect on the findings, and nothing is applied until an engineer approves it.

## Architecture

```
web/  Next.js (Vercel)  ──fetch / SSE──►  backend/  FastAPI (Vercel Python)
  landing page                               server/   API, copilot agent loop
  /app workspace:                            keel/     the engine (unchanged per customer)
    onboard · design review (SVG GA)           infer.py   profile inference
    config-not-code · Ask AIkeel               checks.py  generic checks
                                               geometry.py  DXF → JSON for the browser
                                             data/     three synthetic customers
```

- **Stateless API.** Uploaded files travel with each request and are deleted afterwards. Approved profiles live in the browser.
- **Offline first.** Inference heuristics need no network. Claude is optional, both for the second opinion on low-confidence decisions and for the copilot.
- **Copilot tools:**
  - `list_findings`
  - `get_equipment`
  - `space_mass_report`
  - `explain_profile_decision`
  - `what_if` (a dry run)
  - `propose_profile_change` (returns a proposal and never applies it)

## Run locally

```bash
# API
cd backend
python -m venv .venv && .venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
set ANTHROPIC_API_KEY=...                             # optional, enables the copilot
uvicorn main:app --reload --port 8000
pytest -q                                             # 19 tests

# Web
cd web
npm install
npm run dev                                           # http://localhost:3000 (expects the API on :8000)
```

`NEXT_PUBLIC_API_URL` points the web app at a deployed API. On the API, `AIKEEL_WEB_ORIGINS` (comma-separated) or `AIKEEL_WEB_ORIGIN_REGEX` sets CORS, and `AIKEEL_MODEL` / `AIKEEL_EFFORT` tune the copilot.

The original Streamlit prototype still works offline: `cd backend && streamlit run streamlit_app.py`.

## What the tests prove
- For all three customers, the inferred profile matches ground truth.
- The same check code finds exactly the 5 planted errors for every customer, whether the files are bundled or uploaded.
- Onboarding a new customer changes **zero** engine files (checked by hashing `keel/`).
- The copilot's proposal round-trip resolves the expected finding without changing the approved profile (tested against a scripted fake Claude client, so no API credits are spent).

## Honest limits
- The data is synthetic (an 85 m OSV-like layout). Real GA drawings have xrefs, nested blocks and DWG files, and much of the information lives in 3D models.
- It covers one document pair (equipment list ↔ GA) and one rule type.
- It's an independent project and not affiliated with any company.
