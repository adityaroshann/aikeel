# AIkeel: Demo Night script (T-Minus30, Wed Nov 25)

- **Live site:** https://aikeel.vercel.app (the app is at `/app`)
- **Code:** https://github.com/adityaroshann/aikeel
- **When and where:** Wed Nov 25, 6:30–9:30 pm, The Breezeway, St. John's

## Before the doors open
- [ ] Open https://aikeel-api.vercel.app/api/health and check that it shows `"copilot": true`.
- [ ] Open https://aikeel.vercel.app in one tab and `/app` in another, full screen.
- [ ] Ask the copilot one question to warm it up.
- [ ] Have a backup ready if the Wi-Fi dies: run locally (see README), or use `cd backend && streamlit run streamlit_app.py` for the offline version.

## Before each visitor
- [ ] Click **Reset demo** at the top right. That clears Customer C and jumps to it.
- [ ] Click **Yard A** in the customer list.

## 15-second hook
"Hi, I'm Aditya, and this is AIkeel. Software that checks ship designs has a hidden problem: every shipyard keeps its data differently, so each new customer usually means custom code. AIkeel learns a new customer's files in about a second, an engineer approves it, and the same review engine runs for everyone. There's also an AI copilot you can talk to. Want to see it?"

## 2–3 minute walkthrough
1. **(20 s) Landing page.** Point at the hero: "That's a real drawing, reviewed live. Red circles are problems AIkeel found." Then the table: "Same pump, three customers, three completely different formats."
2. **(30 s) `/app`, Yard A, Design review.**
   - Point at the duplicate tag, the tag that breaks *their* convention, the pump that's listed but not drawn, the unit that's drawn but not listed, and the Engine Room over *their* weight limit.
   - Hover a tag to show its equipment-list row. Click a finding to highlight it.
3. **(45 s) Customer C, onboarded live.**
   - Go to the Onboard tab and click **Run Onboarding Autopilot**. "Ten decisions, each with its evidence."
   - Call out the semicolon delimiter, pounds converted to kg, and the tag format learned from the data.
   - Click **Approve profile**. The design review opens on its own, with Rev A in the revision block.
4. **(45 s) Ask AIkeel, the wow moment.** Back on Yard A, click the chip "The Engine Room limit is actually 32 t. Update it."
   - Watch it look things up and draft a **proposal card** with the YAML diff and "Findings 5 → 4".
   - Say: "It never changes anything itself. I'm the engineer, I decide." Click **Approve change**. The weight finding disappears and Rev B appears.
5. **(15 s) Config, not code tab.** "Two customers, two config files, one engine fingerprint. Zero lines of code per customer."

Then ask: "Have you ever dealt with data that's different for every customer?"

## Likely questions
- **"Is this real data?"** "No, it's synthetic: an 85 m offshore supply vessel described three different ways, with 5 errors planted per customer. 19 automated tests prove it finds exactly those."
- **"Which AI is it?"** "Claude, through tool use. The copilot can only call read-only tools on my engine, plus one tool that *drafts* a change. The engine itself runs without AI, which matters for defence yards that can't send data out."
- **"Did you train your own model?"** "No. Training a model from scratch costs millions. The value is the shipbuilding model, the check engine and the approval workflow around a strong foundation model."
- **"Who would pay?"** "Ship-design software vendors, which save weeks per new customer, and design offices that work with several yards."
- **"What's next?"** "A pilot with real anonymised drawings from a local design office, DWG support, and class-society rule packs."
- **"Are you a naval architect?"** "No, I'm a MUN CS grad. I learned enough of the domain to build this in the sprint."

## Bring
Laptop, charger, and a phone hotspot as a backup. A QR code to https://aikeel.vercel.app is optional so people can try it themselves.
