export const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type Workspace = {
  id: string;
  name: string;
  kind: string;
  blurb: string;
  files: string[];
  seed_profile: string | null;
};
export type Engine = { hash: string; files: number; lines: number };
export type Proposal = {
  field: string;
  value: unknown;
  confidence: number;
  evidence: string;
  method: "heuristic" | "llm";
};
export type OnboardResult = {
  profile_yaml: string;
  proposals: Proposal[];
  low_confidence_threshold: number;
  elapsed_s: number;
  claude_used: boolean;
  claude_error: string | null;
};
export type Finding = {
  check: string;
  severity: "error" | "warning";
  tag: string | null;
  message: string;
  evidence: string;
  x: number | null;
  y: number | null;
};
export type Equipment = { tag: string; name: string; space: string; mass_kg: number | null; row: number };
export type DrawingTag = { tag: string; x: number; y: number; layer: string };
export type Geometry = {
  lines: { x1: number; y1: number; x2: number; y2: number; layer: string }[];
  polylines: { points: [number, number][]; closed: boolean; layer: string }[];
  circles: { cx: number; cy: number; r: number; layer: string }[];
  texts: { x: number; y: number; text: string; h: number; layer: string }[];
  bbox: { minx: number; miny: number; maxx: number; maxy: number };
  layers: string[];
};
export type CheckResult = {
  summary: { equipment: number; tags: number; errors: number; warnings: number };
  findings: Finding[];
  equipment: Equipment[];
  tags: DrawingTag[];
  geometry: Geometry;
};
export type UploadedFile = { name: string; b64: string };
export type Source = { workspace?: string; files?: UploadedFile[] };

export type CopilotProposal = {
  summary: string;
  reason: string;
  changes: { path: string; value: unknown }[];
  profile_yaml: string;
  diff: { op: "+" | "-" | " "; text: string }[];
  effect: { resolved: Finding[]; new: Finding[]; before: number; after: number };
};
export type CopilotEvent =
  | { type: "text"; text: string }
  | { type: "tool"; name: string; label: string }
  | ({ type: "proposal" } & CopilotProposal)
  | { type: "error"; message: string }
  | { type: "done" };

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail: unknown = `The AIkeel API returned ${r.status}.`;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {}
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return r.json();
}

export async function getWorkspaces(): Promise<{ workspaces: Workspace[]; engine: Engine }> {
  const r = await fetch(`${API}/api/workspaces`);
  if (!r.ok) throw new Error(`The AIkeel API returned ${r.status}.`);
  return r.json();
}

export async function getHealth(): Promise<{ ok: boolean; copilot: boolean; model: string }> {
  const r = await fetch(`${API}/api/health`);
  return r.json();
}

export const onboard = (src: Source, use_claude = false) =>
  post<OnboardResult>("/api/onboard", { ...src, use_claude });

export const check = (src: Source, profile_yaml: string) =>
  post<CheckResult>("/api/check", { ...src, profile_yaml });

export async function* copilot(
  src: Source,
  profile_yaml: string,
  messages: { role: string; content: string }[],
  signal?: AbortSignal,
): AsyncGenerator<CopilotEvent> {
  const r = await fetch(`${API}/api/copilot`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    signal,
    body: JSON.stringify({ ...src, profile_yaml, messages }),
  });
  if (!r.ok || !r.body) {
    let detail = `Copilot unavailable (${r.status}).`;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {}
    yield { type: "error", message: detail };
    return;
  }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (line) {
        try {
          yield JSON.parse(line.slice(6)) as CopilotEvent;
        } catch {}
      }
    }
  }
}

export async function fileToUpload(f: File): Promise<UploadedFile> {
  const buf = new Uint8Array(await f.arrayBuffer());
  let bin = "";
  for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  return { name: f.name, b64: btoa(bin) };
}
