import Link from "next/link";
import HeroDrawing from "@/components/HeroDrawing";
import Logo from "@/components/Logo";

const CUSTOMERS = [
  { who: "Yard A", file: "CSV, comma separated", unit: "kilograms", tag: "P-101", where: "Plain text on layer EQ-MECH" },
  { who: "Design Office B", file: "Excel with a title block", unit: "tonnes", tag: "721.01-PMP-02", where: "Block attribute TAG on layer M_EQUIP" },
  { who: "Customer C", file: "CSV, semicolon separated", unit: "pounds", tag: "ER-PU-0007", where: "MTEXT on layer Machinery" },
];

const STEPS = [
  ["Upload", "Send AIkeel a new customer's equipment list, general-arrangement drawing (DXF) and design-standards note."],
  ["Propose", "The Onboarding Autopilot works out their columns, units, tag format, drawing layers and weight limits. Each decision shows its evidence and a confidence score."],
  ["Approve", "An engineer reviews one plain YAML profile and approves it. That file is the only thing that is specific to the customer."],
  ["Review", "The same check engine runs for every customer: equipment missing from the list or the drawing, duplicate tags, broken tag conventions, overweight spaces."],
];

export default function Home() {
  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-4 sm:px-6">
        <Logo className="h-7 w-auto" />
        <nav className="ml-auto flex items-center gap-5 text-sm whitespace-nowrap">
          <a href="#how" className="hidden hover:underline sm:inline">How it works</a>
          <a href="#copilot" className="hidden hover:underline sm:inline">Copilot</a>
          <Link href="/app" className="bg-ink px-3 py-1.5 font-semibold text-sheet">
            Open the live demo
          </Link>
        </nav>
      </header>

      <main>
        {/* hero: the drawing sheet */}
        <section className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="border-2 border-ink bg-sheet">
            <div className="grid gap-6 px-5 pb-6 pt-8 sm:px-8 md:grid-cols-[1.3fr_1fr] md:items-end [&>*]:min-w-0">
              <h1 className="lettering text-[clamp(2.6rem,7vw,5.4rem)]">
                Every shipyard draws the same ship differently.
              </h1>
              <div className="space-y-4 md:pb-2">
                <p className="text-lg leading-snug">
                  AIkeel learns how a new customer keeps their data in seconds, so one design-review engine can check
                  every customer&apos;s drawings. No custom code per customer. Engineers approve every change.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Link href="/app" className="bg-ink px-4 py-2.5 font-semibold text-sheet">
                    Open the live demo
                  </Link>
                  <a href="#how" className="border border-ink px-4 py-2.5 font-semibold">
                    See how it works
                  </a>
                </div>
              </div>
            </div>
            <HeroDrawing />
            {/* title block */}
            <div className="grid border-t-2 border-ink text-sm sm:grid-cols-[1fr_auto]">
              <p className="px-5 py-3 text-steel sm:px-8">
                Above: Yard A&apos;s general arrangement of an 85 m offshore supply vessel, reviewed live by AIkeel. Hover a
                tag to see its equipment-list row. Synthetic data.
              </p>
              <dl className="grid grid-cols-3 border-t-2 border-ink sm:border-l-2 sm:border-t-0">
                {[
                  ["Project", "AIkeel"],
                  ["Built in", "St. John's, NL"],
                  ["Status", "Prototype"],
                ].map(([k, v], i) => (
                  <div key={k} className={`px-4 py-2 ${i ? "border-l border-ink/40" : ""}`}>
                    <dt className="text-xs text-steel">{k}</dt>
                    <dd className="lettering-soft">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>

        {/* the problem */}
        <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="grid gap-10 md:grid-cols-[1fr_2fr] [&>*]:min-w-0">
            <div>
              <h2 className="lettering text-4xl">The same pump, three ways</h2>
              <p className="mt-4 max-w-prose leading-relaxed">
                Software that checks ship designs has to read each customer&apos;s files first. Usually every new yard
                means weeks of custom integration code, and the product splits into one version per customer.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] border-collapse text-sm">
                <thead>
                  <tr className="border-b-2 border-ink text-left">
                    <th className="py-2 pr-4 font-semibold">Customer</th>
                    <th className="py-2 pr-4 font-semibold">Equipment list</th>
                    <th className="py-2 pr-4 font-semibold">Mass in</th>
                    <th className="py-2 pr-4 font-semibold">Pump tag</th>
                    <th className="py-2 font-semibold">Tags on the drawing</th>
                  </tr>
                </thead>
                <tbody>
                  {CUSTOMERS.map((c) => (
                    <tr key={c.who} className="border-b border-ink/20 align-top">
                      <td className="py-3 pr-4 font-semibold">{c.who}</td>
                      <td className="py-3 pr-4">{c.file}</td>
                      <td className="py-3 pr-4">{c.unit}</td>
                      <td className="py-3 pr-4 font-mono">{c.tag}</td>
                      <td className="py-3">{c.where}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 text-sm text-steel">
                AIkeel reads all three with the same engine. Each customer adds one reviewed config file and zero lines of
                code.
              </p>
            </div>
          </div>
        </section>

        {/* how it works: a real sequence */}
        <section id="how" className="border-y-2 border-ink bg-sheet">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
            <h2 className="lettering text-4xl">How onboarding works</h2>
            <ol className="mt-8 grid gap-px bg-ink/80 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map(([t, d], i) => (
                <li key={t} className="bg-sheet p-5">
                  <span className="lettering text-5xl text-ink/25">{i + 1}</span>
                  <h3 className="lettering-soft mt-2 text-xl">{t}</h3>
                  <p className="mt-2 text-sm leading-relaxed">{d}</p>
                </li>
              ))}
            </ol>
            <p className="mt-6 max-w-prose text-sm text-steel">
              Clear decisions are made by fast, offline heuristics, which matters for defence yards that can&apos;t send
              data out. Uncertain ones can go to Claude for a second opinion.
            </p>
          </div>
        </section>

        {/* copilot */}
        <section id="copilot" className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="grid gap-10 md:grid-cols-2 md:items-center [&>*]:min-w-0">
            <div>
              <h2 className="lettering text-4xl">Ask AIkeel. It proposes, you decide.</h2>
              <p className="mt-4 max-w-prose leading-relaxed">
                The copilot reads the customer&apos;s list, drawing and profile through the same engine. Ask why a space is
                flagged or what is missing. When something should change, it drafts a proposal and shows exactly how the
                findings would move. Nothing changes until an engineer approves it.
              </p>
              <Link href="/app" className="mt-6 inline-block bg-ink px-4 py-2.5 font-semibold text-sheet">
                Try the copilot
              </Link>
            </div>
            <figure className="border-2 border-ink bg-sheet text-sm" aria-label="Example copilot exchange">
              <p className="border-b border-ink/30 px-4 py-3 font-semibold">The Engine Room limit is actually 32 t. Update it.</p>
              <div className="space-y-1 px-4 pt-3 text-xs text-steel">
                <p>Adding up mass per space</p>
                <p>Drafting a proposal</p>
              </div>
              <p className="px-4 py-3 leading-relaxed">
                The Engine Room carries 30.6 t against the 28 t limit in rule <code className="bg-film-deep px-1 font-mono">YS-4.2</code>.
                I&apos;ve proposed raising the limit to 32 t. That clears the weight finding.
              </p>
              <div className="mx-4 mb-4 border-2 border-ink bg-film">
                <div className="flex justify-between border-b border-ink px-3 py-2">
                  <span className="lettering-soft">Proposed change</span>
                  <span className="text-xs text-steel">Waiting for your approval</span>
                </div>
                <pre className="px-3 py-2 font-mono text-xs leading-5">
                  <div className="bg-red/10 text-red line-through decoration-red/40">- limit_kg: 28000.0</div>
                  <div className="bg-sea/10 text-sea">+ limit_kg: 32000</div>
                </pre>
                <div className="flex gap-2 border-t border-ink px-3 py-2">
                  <span className="bg-sea px-3 py-1 text-xs font-semibold text-sheet">Approve change</span>
                  <span className="border border-ink px-3 py-1 text-xs font-semibold">Reject</span>
                </div>
              </div>
              <figcaption className="sr-only">Illustration of the copilot proposing a profile change</figcaption>
            </figure>
          </div>
        </section>

        <section className="border-t-2 border-ink">
          <div className="mx-auto grid max-w-6xl gap-8 px-4 py-14 sm:px-6 md:grid-cols-3">
            <div>
              <h2 className="lettering-soft text-xl">What is real</h2>
              <p className="mt-2 text-sm leading-relaxed">
                A working engine and web app: profile inference, DXF drawing parsing, five generic checks, and a Claude
                copilot with tool use. Nineteen automated tests check it against planted errors.
              </p>
            </div>
            <div>
              <h2 className="lettering-soft text-xl">What is not yet</h2>
              <p className="mt-2 text-sm leading-relaxed">
                The data is synthetic. Real drawings have xrefs, nested blocks, DWG files and 3D models, and class-society
                rules go far beyond weight limits.
              </p>
            </div>
            <div>
              <h2 className="lettering-soft text-xl">Next</h2>
              <p className="mt-2 text-sm leading-relaxed">
                A pilot with real, anonymised drawings from a design office, DWG support, and rule packs from
                classification societies.
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t-2 border-ink bg-sheet">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-6 text-sm sm:px-6">
          <Logo className="h-5 w-auto" />
          <span className="text-steel">An independent prototype built for Genesis T-Minus30 in St. John&apos;s, Newfoundland.</span>
          <Link href="/app" className="ml-auto font-semibold underline">
            Open the live demo
          </Link>
        </div>
      </footer>
    </div>
  );
}
