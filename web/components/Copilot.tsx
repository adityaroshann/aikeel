"use client";

import { useEffect, useRef, useState } from "react";
import { copilot, type CopilotProposal, type Source } from "@/lib/api";
import { checkLabel } from "./Drawing";

type Item =
  | { kind: "user"; text: string }
  | { kind: "bot"; text: string; steps: string[]; streaming: boolean }
  | { kind: "proposal"; p: CopilotProposal; state: "pending" | "approved" | "rejected" }
  | { kind: "error"; text: string };

const STARTERS = [
  "Why is this workspace failing review?",
  "Which items are missing from the drawing?",
  "The Engine Room limit is actually 32 t. Update it.",
  "Write a short review summary for the client.",
];

type Props = {
  source: Source | null;
  profileYaml: string | null;
  workspaceName: string;
  available: boolean | null;
  onApprove: (yaml: string, summary: string) => Promise<void>;
};

export default function Copilot({ source, profileYaml, workspaceName, available, onApprove }: Props) {
  const [items, setItems] = useState<Item[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    abort.current?.abort();
    setItems([]);
    setBusy(false);
  }, [workspaceName]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [items]);

  const ready = !!source && !!profileYaml && available !== false;

  async function ask(q: string) {
    if (!ready || busy || !q.trim()) return;
    const history = items
      .filter((i): i is Extract<Item, { kind: "user" | "bot" }> => i.kind === "user" || i.kind === "bot")
      .map((i) => ({ role: i.kind === "user" ? "user" : "assistant", content: i.text }));
    history.push({ role: "user", content: q.trim() });
    setItems((it) => [...it, { kind: "user", text: q.trim() }, { kind: "bot", text: "", steps: [], streaming: true }]);
    setDraft("");
    setBusy(true);
    const ctl = new AbortController();
    abort.current = ctl;
    const patchBot = (fn: (b: Extract<Item, { kind: "bot" }>) => Extract<Item, { kind: "bot" }>) =>
      setItems((it) => {
        const idx = it.map((x) => x.kind).lastIndexOf("bot");
        if (idx < 0) return it;
        const copy = [...it];
        copy[idx] = fn(copy[idx] as Extract<Item, { kind: "bot" }>);
        return copy;
      });
    try {
      for await (const ev of copilot(source!, profileYaml!, history, ctl.signal)) {
        if (ev.type === "text") patchBot((b) => ({ ...b, text: b.text + ev.text }));
        else if (ev.type === "tool") patchBot((b) => ({ ...b, steps: [...b.steps, ev.label] }));
        else if (ev.type === "proposal") {
          const { type: _t, ...p } = ev;
          void _t;
          setItems((it) => [...it, { kind: "proposal", p, state: "pending" }]);
        } else if (ev.type === "error") setItems((it) => [...it, { kind: "error", text: ev.message }]);
      }
    } catch (e) {
      if (!ctl.signal.aborted) setItems((it) => [...it, { kind: "error", text: (e as Error).message }]);
    } finally {
      patchBot((b) => ({ ...b, streaming: false }));
      setBusy(false);
    }
  }

  async function decide(idx: number, ok: boolean) {
    const item = items[idx];
    if (item.kind !== "proposal" || item.state !== "pending") return;
    if (ok) await onApprove(item.p.profile_yaml, item.p.summary);
    setItems((it) => it.map((x, i) => (i === idx && x.kind === "proposal" ? { ...x, state: ok ? "approved" : "rejected" } : x)));
  }

  return (
    <section className="flex h-full min-h-0 flex-col border-l border-ink/80 bg-sheet" aria-label="Ask AIkeel">
      <header className="border-b border-ink/80 px-4 py-3">
        <h2 className="lettering text-2xl">Ask AIkeel</h2>
        <p className="text-sm text-steel">
          Reads {workspaceName}&apos;s list, drawing and profile. It proposes changes; you approve them.
        </p>
      </header>

      <div ref={scroller} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4" aria-live="polite">
        {available === false && (
          <p className="border border-amber bg-amber/10 px-3 py-2 text-sm">
            The copilot is offline because no Claude API key is configured on the server. Onboarding and design
            review still work.
          </p>
        )}
        {items.length === 0 && available !== false && (
          <div className="space-y-2">
            <p className="text-sm text-steel">Try one of these:</p>
            {STARTERS.map((s) => (
              <button
                key={s}
                disabled={!ready}
                onClick={() => ask(s)}
                className="block w-full border border-ink/30 bg-film px-3 py-2 text-left text-sm hover:border-ink disabled:opacity-50"
              >
                {s}
              </button>
            ))}
            {!profileYaml && <p className="text-sm text-steel">Approve a profile for this customer first.</p>}
          </div>
        )}

        {items.map((it, i) => {
          if (it.kind === "user")
            return (
              <p key={i} className="ml-8 border-l-2 border-ink pl-3 text-sm font-semibold">
                {it.text}
              </p>
            );
          if (it.kind === "bot")
            return (
              <div key={i} className="text-sm leading-relaxed">
                {it.steps.length > 0 && (
                  <ul className="mb-2 space-y-0.5 text-xs text-steel">
                    {it.steps.map((s, j) => (
                      <li key={j}>
                        <span aria-hidden className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-sea align-middle" />
                        {s}
                      </li>
                    ))}
                  </ul>
                )}
                <div className={`whitespace-pre-wrap ${it.streaming ? "caret" : ""}`}>
                  <RichText text={it.text} />
                </div>
              </div>
            );
          if (it.kind === "error")
            return (
              <p key={i} className="border border-red/60 bg-red/5 px-3 py-2 text-sm text-red">
                {it.text}
              </p>
            );
          return <ProposalCard key={i} item={it} onDecide={(ok) => decide(i, ok)} />;
        })}
      </div>

      <form
        className="flex gap-2 border-t border-ink/80 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          ask(draft);
        }}
      >
        <label htmlFor="ask" className="sr-only">
          Ask AIkeel about this workspace
        </label>
        <input
          id="ask"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={!ready}
          placeholder={ready ? "Ask about a finding, a tag, a limit…" : "Copilot unavailable"}
          className="min-w-0 flex-1 border border-ink/40 bg-film px-3 py-2 text-sm placeholder:text-steel focus:border-ink focus:outline-none"
        />
        <button
          type="submit"
          disabled={!ready || busy || !draft.trim()}
          className="bg-ink px-4 py-2 text-sm font-semibold text-sheet disabled:opacity-40"
        >
          {busy ? "Working" : "Ask"}
        </button>
      </form>
    </section>
  );
}

function RichText({ text }: { text: string }) {
  // minimal formatting: `code` and **bold**
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("`") && p.endsWith("`") ? (
          <code key={i} className="bg-film-deep px-1 font-mono text-[0.85em]">
            {p.slice(1, -1)}
          </code>
        ) : p.startsWith("**") && p.endsWith("**") ? (
          <strong key={i}>{p.slice(2, -2)}</strong>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

function ProposalCard({
  item,
  onDecide,
}: {
  item: Extract<Item, { kind: "proposal" }>;
  onDecide: (ok: boolean) => void;
}) {
  const { p, state } = item;
  const delta = p.effect.after - p.effect.before;
  return (
    <div className="rise border-2 border-ink bg-film">
      <div className="flex items-baseline justify-between gap-2 border-b border-ink px-3 py-2">
        <h3 className="lettering-soft text-base">Proposed change</h3>
        <span className="text-xs text-steel">
          {state === "pending" ? "Waiting for your approval" : state === "approved" ? "Approved and applied" : "Rejected"}
        </span>
      </div>
      <div className="space-y-2 px-3 py-2 text-sm">
        <p className="font-semibold">{p.summary}</p>
        <p className="text-steel">{p.reason}</p>
        <pre className="max-h-40 overflow-auto bg-sheet p-2 font-mono text-xs leading-5">
          {p.diff.map((d, i) => (
            <div key={i} className={d.op === "+" ? "bg-sea/10 text-sea" : d.op === "-" ? "bg-red/10 text-red line-through decoration-red/40" : "text-steel"}>
              {d.op === " " ? "  " : d.op + " "}
              {d.text}
            </div>
          ))}
        </pre>
        <p>
          Findings {p.effect.before} → {p.effect.after}
          {delta !== 0 && <span className={delta < 0 ? "text-sea" : "text-red"}> ({delta > 0 ? "+" : ""}{delta})</span>}
          {p.effect.resolved.length > 0 && (
            <span className="text-steel"> · resolves {p.effect.resolved.map((f) => checkLabel(f.check)).join(", ")}</span>
          )}
        </p>
      </div>
      {state === "pending" && (
        <div className="flex gap-2 border-t border-ink px-3 py-2">
          <button onClick={() => onDecide(true)} className="bg-sea px-3 py-1.5 text-sm font-semibold text-sheet">
            Approve change
          </button>
          <button onClick={() => onDecide(false)} className="border border-ink px-3 py-1.5 text-sm font-semibold">
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
