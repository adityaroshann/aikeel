"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import Copilot from "@/components/Copilot";
import Drawing, { checkLabel, findingId } from "@/components/Drawing";
import Logo from "@/components/Logo";
import {
  check,
  fileToUpload,
  getHealth,
  getWorkspaces,
  onboard,
  type CheckResult,
  type Engine,
  type OnboardResult,
  type Source,
  type UploadedFile,
  type Workspace,
} from "@/lib/api";
import { DEMO_CUSTOMER, profiles } from "@/lib/store";

type Tab = "onboard" | "review" | "config";
type Rev = { rev: string; note: string; at: string };
const UPLOAD = "__upload";

const FIELD_LABELS: Record<string, string> = {
  "equipment_list.delimiter": "Delimiter",
  "equipment_list.header_row": "Header row",
  "columns.tag": "Tag column",
  "columns.name": "Name column",
  "columns.space": "Space column",
  "columns.mass_kg": "Mass column",
  "columns.mass_kg.scale": "Mass unit → kg",
  tag_convention: "Tag convention",
  drawing: "Where tags live on the drawing",
};

function fieldLabel(f: string) {
  if (FIELD_LABELS[f]) return FIELD_LABELS[f];
  if (f.startsWith("rules[")) return `Design rule ${f.slice(6, -1)}`;
  return f;
}

function show(v: unknown) {
  if (typeof v === "string") return v === ";" ? "; (semicolon)" : v === "," ? ", (comma)" : v;
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(4).replace(/0+$/, "");
  return JSON.stringify(v);
}

export default function AppPage() {
  const [ws, setWs] = useState<Workspace[]>([]);
  const [engine, setEngine] = useState<Engine | null>(null);
  const [copilotOn, setCopilotOn] = useState<boolean | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [sel, setSel] = useState<string>("yard_a");
  const [uploads, setUploads] = useState<UploadedFile[]>([]);
  const [approved, setApproved] = useState<Record<string, string>>({});
  const [revs, setRevs] = useState<Record<string, Rev[]>>({});
  const [tab, setTab] = useState<Tab>("review");
  const [ob, setOb] = useState<OnboardResult | null>(null);
  const [draftYaml, setDraftYaml] = useState("");
  const [result, setResult] = useState<CheckResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [cmp, setCmp] = useState<[string, string]>(["yard_a", "office_b"]);

  // --- boot
  useEffect(() => {
    getWorkspaces()
      .then(({ workspaces, engine }) => {
        setWs(workspaces);
        setEngine(engine);
        const stored = profiles.all();
        const seeded: Record<string, string> = {};
        for (const w of workspaces) {
          const s = w.seed_profile;
          if (s && w.id !== DEMO_CUSTOMER) seeded[w.id] = s;
        }
        const merged = { ...seeded, ...stored };
        setApproved(merged);
        const r: Record<string, Rev[]> = {};
        for (const id of Object.keys(merged)) r[id] = [{ rev: "A", note: "Onboarded by Autopilot, approved by engineer", at: "earlier" }];
        setRevs(r);
      })
      .catch(() => setLoadErr("The AIkeel API is not reachable. It may be waking up; reload in a few seconds."));
    getHealth().then((h) => setCopilotOn(h.copilot)).catch(() => setCopilotOn(false));
  }, []);

  const current = ws.find((w) => w.id === sel);
  const name = sel === UPLOAD ? "Your files" : current?.name ?? sel;
  const source: Source | null = useMemo(
    () => (sel === UPLOAD ? (uploads.length ? { files: uploads } : null) : { workspace: sel }),
    [sel, uploads],
  );
  const approvedYaml = approved[sel] ?? null;

  const runCheck = useCallback(
    async (yaml: string) => {
      if (!source) return;
      setBusy("Running design review");
      setErr(null);
      try {
        setResult(await check(source, yaml));
      } catch (e) {
        setErr((e as Error).message);
        setResult(null);
      } finally {
        setBusy(null);
      }
    },
    [source],
  );

  // --- switching workspace
  useEffect(() => {
    setOb(null);
    setResult(null);
    setFocus(null);
    setErr(null);
    const y = approved[sel];
    setDraftYaml(y ?? "");
    setTab(y ? "review" : "onboard");
    if (y) runCheck(y);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel, source, ws.length]);

  function flash(msg: string) {
    setToast(msg);
    window.setTimeout(() => setToast(null), 3200);
  }

  function addRev(id: string, note: string) {
    setRevs((r) => {
      const list = r[id] ?? [];
      const rev = String.fromCharCode(65 + list.length);
      return { ...r, [id]: [...list, { rev, note, at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }] };
    });
  }

  async function runAutopilot() {
    if (!source) return;
    setBusy("Reading the customer's files");
    setErr(null);
    try {
      const r = await onboard(source, copilotOn === true);
      setOb(r);
      setDraftYaml(r.profile_yaml);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function approveProfile(yaml: string, note: string) {
    setApproved((a) => ({ ...a, [sel]: yaml }));
    if (sel !== UPLOAD) profiles.set(sel, yaml);
    addRev(sel, note);
    await runCheck(yaml);
    setTab("review");
    flash("Profile approved. No code was written.");
  }

  function resetDemo() {
    profiles.remove(DEMO_CUSTOMER);
    setApproved((a) => {
      const c = { ...a };
      delete c[DEMO_CUSTOMER];
      return c;
    });
    setRevs((r) => ({ ...r, [DEMO_CUSTOMER]: [] }));
    if (sel === DEMO_CUSTOMER) {
      setOb(null);
      setResult(null);
      setDraftYaml("");
      setTab("onboard");
    } else setSel(DEMO_CUSTOMER);
    flash("Customer C reset. Ready to onboard live.");
  }

  async function onFiles(list: FileList | null) {
    if (!list?.length) return;
    try {
      const ups = await Promise.all(Array.from(list).map(fileToUpload));
      setUploads(ups);
      setApproved((a) => {
        const c = { ...a };
        delete c[UPLOAD];
        return c;
      });
      setSel(UPLOAD);
    } catch {
      setErr("Those files could not be read.");
    }
  }

  const onboarded = ws.filter((w) => approved[w.id]);
  const findings = result?.findings ?? [];

  return (
    <div className="flex h-dvh flex-col">
      {/* top bar */}
      <header className="flex items-center gap-4 border-b border-ink/80 bg-sheet px-4 py-2">
        <Link href="/" className="flex items-center gap-2" aria-label="AIkeel home">
          <Logo className="h-6 w-auto" />
        </Link>
        <span className="hidden text-sm text-steel sm:inline">Design review workspace</span>
        <div className="ml-auto flex items-center gap-2">
          {engine && (
            <span className="hidden font-mono text-xs text-steel md:inline" title="Same engine for every customer">
              engine {engine.hash}
            </span>
          )}
          <button onClick={resetDemo} className="border border-ink/50 px-2.5 py-1 text-xs font-semibold hover:border-ink">
            Reset demo
          </button>
          <button
            onClick={() => setChatOpen((o) => !o)}
            className="bg-ink px-3 py-1 text-xs font-semibold text-sheet lg:hidden"
            aria-expanded={chatOpen}
          >
            Ask AIkeel
          </button>
        </div>
      </header>

      {loadErr && <p className="border-b border-amber bg-amber/10 px-4 py-2 text-sm">{loadErr}</p>}

      <div className="grid min-h-0 flex-1 grid-cols-1 grid-rows-[auto_minmax(0,1fr)] md:grid-cols-[220px_1fr] md:grid-rows-1 lg:grid-cols-[220px_1fr_380px]">
        {/* workspaces */}
        <nav aria-label="Customers" className="border-b border-ink/80 bg-film md:border-b-0 md:border-r">
          <h2 className="px-4 pb-1 pt-4 text-sm font-semibold text-steel">Customers</h2>
          <ul className="flex gap-1 overflow-x-auto px-2 pb-2 md:block md:space-y-0.5 md:overflow-visible">
            {ws.map((w) => (
              <li key={w.id} className="shrink-0">
                <button
                  onClick={() => setSel(w.id)}
                  aria-current={sel === w.id}
                  className={`w-full px-2 py-2 text-left ${sel === w.id ? "bg-ink text-sheet" : "hover:bg-film-deep"}`}
                >
                  <span className="block text-sm font-semibold">{w.name}</span>
                  <span className={`block text-xs ${sel === w.id ? "text-sheet/70" : "text-steel"}`}>
                    {approved[w.id] ? "Onboarded" : "New: not onboarded"}
                  </span>
                </button>
              </li>
            ))}
            {uploads.length > 0 && (
              <li className="shrink-0">
                <button
                  onClick={() => setSel(UPLOAD)}
                  aria-current={sel === UPLOAD}
                  className={`w-full px-2 py-2 text-left ${sel === UPLOAD ? "bg-ink text-sheet" : "hover:bg-film-deep"}`}
                >
                  <span className="block text-sm font-semibold">Your files</span>
                  <span className="block text-xs opacity-70">{uploads.length} files, this session only</span>
                </button>
              </li>
            )}
          </ul>
          <div className="hidden px-4 pt-3 md:block">
            <label className="block cursor-pointer border border-dashed border-ink/50 px-3 py-3 text-xs hover:border-ink">
              <span className="font-semibold">Try your own files</span>
              <span className="mt-1 block text-steel">Equipment list (.csv/.xlsx), GA drawing (.dxf), standards (.md/.txt). Up to 5 MB. Not stored.</span>
              <input type="file" multiple accept=".csv,.xlsx,.dxf,.md,.txt" className="sr-only" onChange={(e) => onFiles(e.target.files)} />
            </label>
          </div>
        </nav>

        {/* main */}
        <main className="min-h-0 overflow-y-auto">
          <div className="border-b border-ink/80 px-5 pt-4">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h1 className="lettering text-4xl">{name}</h1>
                <p className="mt-1 text-sm text-steel">{sel === UPLOAD ? uploads.map((u) => u.name).join(", ") : current?.blurb}</p>
              </div>
              {busy && <p className="text-sm text-steel">{busy}…</p>}
            </div>
            <div role="tablist" className="mt-4 flex gap-0">
              {(
                [
                  ["onboard", "1. Onboard"],
                  ["review", "2. Design review"],
                  ["config", "3. Config, not code"],
                ] as [Tab, string][]
              ).map(([t, label]) => (
                <button
                  key={t}
                  role="tab"
                  aria-selected={tab === t}
                  onClick={() => setTab(t)}
                  className={`-mb-px border border-b-0 px-4 py-2 text-sm font-semibold ${tab === t ? "border-ink/80 bg-film" : "border-transparent text-steel hover:text-ink"}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {err && <p className="mx-5 mt-4 border border-red/60 bg-red/5 px-3 py-2 text-sm text-red">{err}</p>}

          <div className="px-5 py-5">
            {tab === "onboard" && (
              <OnboardTab
                files={sel === UPLOAD ? uploads.map((u) => u.name) : current?.files ?? []}
                ob={ob}
                approvedYaml={approvedYaml}
                draftYaml={draftYaml}
                setDraftYaml={setDraftYaml}
                busy={!!busy}
                onRun={runAutopilot}
                onApprove={() => approveProfile(draftYaml, ob ? "Onboarded by Autopilot, approved by engineer" : "Profile edited and approved")}
              />
            )}

            {tab === "review" &&
              (!approvedYaml ? (
                <Empty action="Onboard this customer first" onClick={() => setTab("onboard")}>
                  There is no approved profile for {name} yet, so AIkeel can&apos;t read their files.
                </Empty>
              ) : !result ? (
                <p className="text-sm text-steel">Running design review…</p>
              ) : (
                <div className="space-y-5">
                  <dl className="grid grid-cols-2 border border-ink/80 bg-sheet sm:grid-cols-4">
                    {[
                      ["Items in equipment list", result.summary.equipment, ""],
                      ["Tags found on drawing", result.summary.tags, ""],
                      ["Errors", result.summary.errors, "text-red"],
                      ["Warnings", result.summary.warnings, "text-amber"],
                    ].map(([k, v, c], i) => (
                      <div key={k as string} className={`px-4 py-3 ${i ? "border-l border-ink/30" : ""}`}>
                        <dt className="text-xs text-steel">{k}</dt>
                        <dd className={`lettering text-3xl ${c}`}>{v}</dd>
                      </div>
                    ))}
                  </dl>
                  <Drawing data={result} focus={focus} onFocus={setFocus} />
                  <table className="w-full border-collapse text-sm">
                    <caption className="pb-2 text-left text-sm font-semibold">Findings ({findings.length})</caption>
                    <thead className="text-left text-xs text-steel">
                      <tr className="border-b border-ink/80">
                        <th className="py-1.5 pr-3 font-normal">Check</th>
                        <th className="py-1.5 pr-3 font-normal">Item or space</th>
                        <th className="py-1.5 font-normal">What AIkeel found</th>
                      </tr>
                    </thead>
                    <tbody>
                      {findings.map((f) => {
                        const id = findingId(f);
                        return (
                          <tr
                            key={id}
                            onClick={() => setFocus(id)}
                            className={`cursor-pointer border-b border-ink/15 align-top ${focus === id ? "bg-film-deep" : "hover:bg-film-deep/60"}`}
                          >
                            <td className="py-2 pr-3">
                              <span className={`font-semibold ${f.severity === "error" ? "text-red" : "text-amber"}`}>{checkLabel(f.check)}</span>
                            </td>
                            <td className="py-2 pr-3 font-mono text-xs">{f.tag}</td>
                            <td className="py-2">
                              {f.message}
                              <div className="text-xs text-steel">{f.evidence}</div>
                            </td>
                          </tr>
                        );
                      })}
                      {findings.length === 0 && (
                        <tr>
                          <td colSpan={3} className="py-3 text-sea">No findings. The list, drawing and rules agree.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                  <Revisions revs={revs[sel] ?? []} />
                </div>
              ))}

            {tab === "config" && (
              <ConfigTab engine={engine} onboarded={onboarded} approved={approved} cmp={cmp} setCmp={setCmp} />
            )}
          </div>
        </main>

        {/* copilot */}
        <div
          className={`${chatOpen ? "fixed inset-x-0 bottom-0 top-12 z-30" : "hidden"} min-h-0 lg:static lg:block`}
        >
          <Copilot
            source={source}
            profileYaml={approvedYaml}
            workspaceName={name}
            available={copilotOn}
            onApprove={(yaml, summary) => approveProfile(yaml, `${summary} (copilot proposal, approved)`)}
          />
        </div>
      </div>

      {toast && (
        <div role="status" className="rise fixed bottom-4 left-1/2 z-40 -translate-x-1/2 bg-ink px-4 py-2 text-sm text-sheet shadow-[3px_3px_0_var(--sea)]">
          {toast}
        </div>
      )}
    </div>
  );
}

function Empty({ children, action, onClick }: { children: React.ReactNode; action: string; onClick: () => void }) {
  return (
    <div className="border border-dashed border-ink/50 px-5 py-8">
      <p className="text-sm">{children}</p>
      <button onClick={onClick} className="mt-3 bg-ink px-4 py-2 text-sm font-semibold text-sheet">
        {action}
      </button>
    </div>
  );
}

function OnboardTab(props: {
  files: string[];
  ob: OnboardResult | null;
  approvedYaml: string | null;
  draftYaml: string;
  setDraftYaml: (s: string) => void;
  busy: boolean;
  onRun: () => void;
  onApprove: () => void;
}) {
  const { files, ob, approvedYaml, draftYaml, setDraftYaml, busy, onRun, onApprove } = props;
  const low = ob ? ob.proposals.filter((p) => p.confidence < ob.low_confidence_threshold).length : 0;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-4">
        <div className="text-sm">
          <span className="text-steel">Files received: </span>
          {files.map((f) => (
            <span key={f} className="mr-2 font-mono text-xs">{f}</span>
          ))}
        </div>
        <button onClick={onRun} disabled={busy || !files.length} className="ml-auto bg-ink px-4 py-2 text-sm font-semibold text-sheet disabled:opacity-40">
          {ob ? "Run Onboarding Autopilot again" : "Run Onboarding Autopilot"}
        </button>
      </div>

      {!ob && (
        <p className="max-w-prose text-sm text-steel">
          {approvedYaml
            ? "This customer already has an approved profile. Run the Autopilot to see how AIkeel would propose it from scratch."
            : "AIkeel will read these files and propose how this customer works: which column is which, their units, their tag format, where tags sit on the drawing, and their weight limits. You review every decision before anything is saved."}
        </p>
      )}

      {ob && (
        <>
          <p className="text-sm">
            <strong>{ob.proposals.length} decisions</strong> proposed in {ob.elapsed_s < 0.1 ? "under 0.1" : ob.elapsed_s.toFixed(2)} s.{" "}
            {low ? <span className="text-amber">{low} need your attention.</span> : <span className="text-sea">None below {Math.round(ob.low_confidence_threshold * 100)}% confidence.</span>}
            {ob.claude_error && <span className="text-steel"> Claude was unavailable, so heuristics decided alone.</span>}
          </p>
          <ol className="divide-y divide-ink/15 border-y border-ink/80">
            {ob.proposals.map((p, i) => (
              <li key={i} className="rise grid gap-1 py-3 sm:grid-cols-[180px_1fr_120px] sm:gap-4" style={{ animationDelay: `${i * 45}ms` }}>
                <div className="text-sm font-semibold">{fieldLabel(p.field)}</div>
                <div className="min-w-0">
                  <div className="break-all font-mono text-sm">{show(p.value)}</div>
                  <div className="text-xs text-steel">{p.evidence}</div>
                </div>
                <div className="text-xs">
                  <div className="h-1.5 w-full bg-film-deep" aria-hidden>
                    <div
                      className={`h-full ${p.confidence < ob.low_confidence_threshold ? "bg-amber" : "bg-sea"}`}
                      style={{ width: `${Math.round(p.confidence * 100)}%` }}
                    />
                  </div>
                  <div className="mt-1 text-steel">
                    {Math.round(p.confidence * 100)}% · {p.method === "llm" ? "Claude" : "heuristic"}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </>
      )}

      {(ob || approvedYaml) && (
        <div>
          <label htmlFor="yaml" className="text-sm font-semibold">
            Customer profile <span className="font-normal text-steel">(the only per-customer file; edit before approving)</span>
          </label>
          <textarea
            id="yaml"
            value={draftYaml}
            onChange={(e) => setDraftYaml(e.target.value)}
            spellCheck={false}
            rows={18}
            className="mt-2 w-full border border-ink/80 bg-sheet p-3 font-mono text-xs leading-5 focus:outline-none"
          />
          <button onClick={onApprove} disabled={busy || !draftYaml.trim()} className="mt-2 bg-sea px-4 py-2 text-sm font-semibold text-sheet disabled:opacity-40">
            Approve profile
          </button>
        </div>
      )}
    </div>
  );
}

function Revisions({ revs }: { revs: Rev[] }) {
  if (!revs.length) return null;
  return (
    <table className="ml-auto w-full max-w-lg border border-ink/80 bg-sheet text-xs">
      <caption className="sr-only">Profile revisions</caption>
      <thead>
        <tr className="border-b border-ink/80 text-left">
          <th className="w-10 px-2 py-1 font-semibold">Rev</th>
          <th className="px-2 py-1 font-semibold">Profile change</th>
          <th className="w-20 px-2 py-1 font-semibold">Time</th>
        </tr>
      </thead>
      <tbody>
        {revs.map((r) => (
          <tr key={r.rev} className="border-b border-ink/15 last:border-0">
            <td className="px-2 py-1 font-mono">{r.rev}</td>
            <td className="px-2 py-1">{r.note}</td>
            <td className="px-2 py-1 text-steel">{r.at}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ConfigTab({
  engine,
  onboarded,
  approved,
  cmp,
  setCmp,
}: {
  engine: Engine | null;
  onboarded: Workspace[];
  approved: Record<string, string>;
  cmp: [string, string];
  setCmp: (c: [string, string]) => void;
}) {
  const ids = onboarded.map((w) => w.id);
  const pair: [string, string] = [ids.includes(cmp[0]) ? cmp[0] : ids[0], ids.includes(cmp[1]) ? cmp[1] : ids[1]];
  return (
    <div className="space-y-5">
      <p className="max-w-prose text-sm">
        One engine reads every customer. It is{" "}
        {engine && (
          <>
            <span className="font-mono">{engine.files}</span> files, <span className="font-mono">{engine.lines}</span> lines, fingerprint{" "}
            <span className="font-mono">{engine.hash}</span>,{" "}
          </>
        )}
        identical for all {onboarded.length} onboarded customers. What changes between customers is one reviewed YAML file.
      </p>
      {ids.length < 2 ? (
        <p className="text-sm text-steel">Approve at least two customer profiles to compare them.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {[0, 1].map((side) => (
            <div key={side}>
              <label className="text-sm font-semibold">
                Profile
                <select
                  value={pair[side]}
                  onChange={(e) => setCmp(side === 0 ? [e.target.value, pair[1]] : [pair[0], e.target.value])}
                  className="ml-2 border border-ink/50 bg-sheet px-2 py-1 text-sm"
                >
                  {onboarded.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name}
                    </option>
                  ))}
                </select>
              </label>
              <pre className="mt-2 max-h-[28rem] overflow-auto border border-ink/80 bg-sheet p-3 font-mono text-xs leading-5">{approved[pair[side]]}</pre>
              <p className="mt-1 text-xs text-steel">{approved[pair[side]]?.split("\n").length ?? 0} lines of configuration</p>
            </div>
          ))}
        </div>
      )}
      <p className="lettering-soft text-xl">Code changed per customer: 0 lines.</p>
    </div>
  );
}
