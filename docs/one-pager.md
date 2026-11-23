# ⚓ AIkeel: one-pager

**Onboard any shipyard in an afternoon, not a quarter.**

## Problem
Software that checks ship designs for errors has to read each customer's own data. Every shipyard and design office keeps that data differently:
- **Equipment lists:** CSV or Excel, with title blocks, and in kg, tonnes or pounds.
- **Tag formats:** for example `P-101`, SFI-style `721.01-PMP-02`, or `ER-PU-0007`.
- **CAD drawings:** different layer names, and tags stored as plain text, MTEXT or block attributes.
- **Standards:** each yard has its own, such as weight limits per compartment.

The usual fix is custom integration code for each customer. Onboarding then takes weeks of engineering, and the codebase forks into one version per customer.

## Solution
AIkeel turns onboarding into **one reviewed configuration file**:
1. **Upload** the customer's sample files: equipment list, GA drawing (DXF) and standards note.
2. **Propose.** The Onboarding Autopilot infers the customer's format, delimiter, header row, column mapping, units, tag convention, drawing layer and tag storage, and weight rules. Each decision comes with a confidence score and its evidence.
3. **Approve.** An engineer reviews and edits the proposed YAML profile.
4. **Check.** One shared engine runs on every customer. It finds equipment missing from the list or the drawing, duplicate tags, tags that break the customer's own convention, and compartments over the customer's own weight limit.

Clear cases are handled offline by heuristics. Low-confidence decisions can optionally go to Claude for a second opinion. **The AI explains. The engineer decides.**

## Proof (the working demo)
- **Three synthetic customers:** the same 85 m offshore-supply-vessel layout, described three different ways.
- **Inference:** the inferred profile matches ground truth for all three customers.
- **Planted errors:** the same check code finds exactly the 5 planted errors for each customer.
- **Zero code changes:** onboarding a new customer produces one YAML file and changes no engine code. A test verifies this by hashing the engine before and after.
- **Speed:** a new customer is proposed in about a second.

## Who it's for
- Ship-design and design-review software vendors that onboard yards and design offices.
- Naval-architecture and design offices working with several yards.
- Shipyards doing defence and coast-guard programs, where data often has to stay on-prem.

## Business model (sketch)
- A per-onboarding fee for each new customer profile, plus a SaaS or on-prem seat licence for the check engine.
- Alternatively, license the onboarding layer to existing ship-design software vendors.

## Honest limits
- Synthetic data only. Real drawings have xrefs, nested blocks, DWG files and 3D models.
- It covers one document pair (equipment list ↔ GA drawing) and one rule type.
- It's a prototype built for Genesis T-Minus30.

## Next steps
- Pilot with real (anonymised) drawings from a local design office.
- Add DWG support, class-society rule packs and more check types.
- Test the Claude second-opinion path on real ambiguous cases.
