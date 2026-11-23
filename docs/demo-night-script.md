# AIkeel: Demo Night script (T-Minus30, Wed Nov 25)

**When and where:** Wed Nov 25, 6:30–9:30 pm, The Breezeway, St. John's.

**Setup:** run `streamlit run app.py` and maximise the browser window. The app runs fully offline, so the venue Wi-Fi doesn't matter.

## Before each visitor
- [ ] Click **↺ Reset demo** in the sidebar, which clears `hidden_c`.
- [ ] Select `yard_a` in the sidebar and open tab **⓪ Why AIkeel**.

## 15-second hook
"Hi, I'm Aditya, and this is AIkeel. Software that checks ship designs for mistakes has a hidden problem: every shipyard keeps its data differently. Usually that means custom code for each new customer. AIkeel learns a new customer's format in about a second, an engineer approves it, and the same checks run with zero new code. Want to see it?"

## 2-minute walkthrough
1. **(20 s) Tab ⓪, the problem.** Point at the four examples: units, tag formats, CAD layers and standards. "Same ship, completely different files."
2. **(30 s) Tab ②, two existing customers.**
   - With `yard_a` selected, show the drawing with red circles: a duplicate tag, a tag that breaks *their* convention, equipment that's listed but not drawn, equipment that's drawn but not listed, and the Engine Room over *their* weight limit.
   - Switch to `office_b`. Its files are Excel instead of CSV, in tonnes instead of kg, with different tags and layers. "Same checks, same errors caught."
3. **(45 s) Tab ①, a new customer, live.**
   - Select `hidden_c` and click **🚀 Run Onboarding Autopilot**. "About a second for ten decisions, and each one shows why."
   - Point at the semicolon delimiter, "Weight (lbs)" converted ×0.4536 to kg, and the tag convention learned from the data with the malformed outlier flagged.
   - "Anything below 60% confidence gets flagged for the engineer and can go to Claude for a second opinion. The AI explains, the engineer decides."
   - Click **✅ Approve**.
4. **(25 s) Tab ③, config, not code.** Show the two YAML files side by side and the single engine fingerprint. "Each new customer costs one reviewed file. Zero lines of code."

Then stop talking and ask: "Have you ever dealt with data that's different for every customer?"

## Likely questions
- **"Is this real data?"** "No, it's synthetic: an 85 m offshore supply vessel described three different ways, with 5 errors planted per customer. The tests prove it finds exactly those."
- **"Where's the AI?"** "Two layers. Fast heuristics handle the clear cases offline, which matters for defence yards that can't send data out. Claude handles the ambiguous ones. Every decision is a proposal with evidence, and a human approves it."
- **"Why not just use ChatGPT for everything?"** "Cost, repeatability and auditability. Engineers need to know *why* the system decided something, and yards often need it to run on-prem."
- **"Who would pay for this?"** "Ship-design software vendors, which save weeks per new customer, and design offices that work with several yards."
- **"What's next?"** "A pilot with real anonymised drawings from a local design office, DWG support, and class-society rule packs."
- **"Are you a naval architect?"** "No, I'm a MUN CS grad. I learned enough of the domain to build this in the sprint, and that's the point: the pattern isn't specific to ships."

## Bring
Laptop, charger, and a phone hotspot as a backup. Printed copies of `docs/one-pager.md` are optional.
