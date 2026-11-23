"use client";

import { useMemo, useRef, useState } from "react";
import type { CheckResult, Finding } from "@/lib/api";

const PAD = 2;

export function findingId(f: Finding) {
  return `${f.check}:${f.tag ?? ""}`;
}

export function checkLabel(check: string) {
  const map: Record<string, string> = {
    duplicate_tag: "Duplicate tag",
    tag_convention: "Breaks tag convention",
    missing_on_drawing: "Listed, not drawn",
    missing_from_list: "Drawn, not listed",
    "rule:max_total_mass_per_space": "Over weight limit",
  };
  return map[check] ?? check.replace(/_/g, " ");
}

type Props = {
  data: CheckResult;
  focus?: string | null;
  onFocus?: (id: string | null) => void;
  interactive?: boolean;
  className?: string;
};

export default function Drawing({ data, focus, onFocus, interactive = true, className = "" }: Props) {
  const { geometry: g, findings, equipment, tags } = data;
  const W = g.bbox.maxx - g.bbox.minx + PAD * 2;
  const H = g.bbox.maxy - g.bbox.miny + PAD * 2;
  const X = (x: number) => x - g.bbox.minx + PAD;
  const Y = (y: number) => g.bbox.maxy - y + PAD;

  const [view, setView] = useState({ x: 0, y: 0, w: W, h: H });
  const [hover, setHover] = useState<string | null>(null);
  const drag = useRef<{ sx: number; sy: number; vx: number; vy: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const tagSet = useMemo(() => new Set(tags.map((t) => t.tag)), [tags]);
  const eqByTag = useMemo(() => new Map(equipment.map((e) => [e.tag, e])), [equipment]);
  const pos = useMemo(() => new Map(tags.map((t) => [t.tag, t])), [tags]);

  // where each space sits (spread of its drawn equipment), for rule + missing findings
  const spaceSpan = useMemo(() => {
    const m = new Map<string, { min: number; max: number }>();
    for (const e of equipment) {
      const p = pos.get(e.tag);
      if (!p) continue;
      const s = m.get(e.space) ?? { min: p.x, max: p.x };
      s.min = Math.min(s.min, p.x);
      s.max = Math.max(s.max, p.x);
      m.set(e.space, s);
    }
    return m;
  }, [equipment, pos]);

  const markers = findings.map((f) => {
    const id = findingId(f);
    const color = f.severity === "error" ? "var(--red)" : "var(--amber)";
    if (f.x != null && f.y != null) return { id, f, color, kind: "point" as const, x: f.x, y: f.y };
    if (f.check.startsWith("rule:") && f.tag && spaceSpan.get(f.tag)) {
      const s = spaceSpan.get(f.tag)!;
      return { id, f, color, kind: "band" as const, x: s.min - 3, w: s.max - s.min + 6 };
    }
    if (f.check === "missing_on_drawing" && f.tag) {
      const e = eqByTag.get(f.tag);
      const s = e && spaceSpan.get(e.space);
      if (s) return { id, f, color, kind: "ghost" as const, x: (s.min + s.max) / 2 };
    }
    return null;
  });

  function zoom(factor: number, cx?: number, cy?: number) {
    setView((v) => {
      const nw = Math.min(W, Math.max(W / 8, v.w * factor));
      const nh = (nw / W) * H;
      const px = cx ?? v.x + v.w / 2;
      const py = cy ?? v.y + v.h / 2;
      const nx = Math.min(Math.max(0, px - ((px - v.x) * nw) / v.w), W - nw);
      const ny = Math.min(Math.max(0, py - ((py - v.y) * nh) / v.h), H - nh);
      return { x: nx, y: ny, w: nw, h: nh };
    });
  }

  function toSvg(e: React.PointerEvent | React.WheelEvent) {
    const r = svgRef.current!.getBoundingClientRect();
    return { x: view.x + ((e.clientX - r.left) / r.width) * view.w, y: view.y + ((e.clientY - r.top) / r.height) * view.h };
  }

  const hoverEq = hover ? eqByTag.get(hover) : undefined;
  const hoverPos = hover ? pos.get(hover) : undefined;
  const stroke = 0.09;

  return (
    <div className={`relative film-grid border border-ink/80 ${className}`}>
      <svg
        ref={svgRef}
        viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
        className={`block w-full h-auto select-none ${interactive ? "cursor-grab active:cursor-grabbing" : ""}`}
        role="img"
        aria-label="General arrangement drawing with design-review findings marked"
        onWheel={
          interactive
            ? (e) => {
                const p = toSvg(e);
                zoom(e.deltaY > 0 ? 1.15 : 0.87, p.x, p.y);
              }
            : undefined
        }
        onPointerDown={
          interactive
            ? (e) => {
                drag.current = { sx: e.clientX, sy: e.clientY, vx: view.x, vy: view.y };
                (e.target as Element).setPointerCapture?.(e.pointerId);
              }
            : undefined
        }
        onPointerMove={
          interactive
            ? (e) => {
                if (!drag.current) return;
                const r = svgRef.current!.getBoundingClientRect();
                const dx = ((e.clientX - drag.current.sx) / r.width) * view.w;
                const dy = ((e.clientY - drag.current.sy) / r.height) * view.h;
                setView((v) => ({
                  ...v,
                  x: Math.min(Math.max(0, drag.current!.vx - dx), W - v.w),
                  y: Math.min(Math.max(0, drag.current!.vy - dy), H - v.h),
                }));
              }
            : undefined
        }
        onPointerUp={() => (drag.current = null)}
        onPointerLeave={() => (drag.current = null)}
      >
        {/* weight-limit bands sit under the linework */}
        {markers.map((m) =>
          m && m.kind === "band" ? (
            <rect
              key={m.id}
              x={X(m.x)}
              y={Y(7.6)}
              width={m.w}
              height={15.2}
              fill={m.color}
              opacity={focus === m.id ? 0.18 : 0.08}
              onClick={() => onFocus?.(m.id)}
            />
          ) : null,
        )}
        <g stroke="var(--ink)" strokeWidth={stroke} fill="none" strokeLinecap="round">
          {g.lines.map((l, i) => (
            <line key={i} x1={X(l.x1)} y1={Y(l.y1)} x2={X(l.x2)} y2={Y(l.y2)} />
          ))}
          {g.polylines.map((p, i) => (
            <polyline
              key={i}
              points={(p.closed ? [...p.points, p.points[0]] : p.points).map(([x, y]) => `${X(x)},${Y(y)}`).join(" ")}
            />
          ))}
          {g.circles.map((c, i) => (
            <circle key={i} cx={X(c.cx)} cy={Y(c.cy)} r={c.r} />
          ))}
        </g>
        <g fill="var(--ink)" style={{ fontFamily: "var(--font-plex-mono)" }}>
          {g.texts.map((t, i) => {
            const isTag = tagSet.has(t.text);
            return (
              <text
                key={i}
                x={X(t.x)}
                y={Y(t.y)}
                fontSize={Math.max(t.h, 0.36)}
                fill={isTag && hover === t.text ? "var(--sea)" : isTag ? "var(--ink)" : "var(--steel)"}
                fontWeight={isTag ? 500 : 400}
                onPointerEnter={isTag ? () => setHover(t.text) : undefined}
                onPointerLeave={isTag ? () => setHover(null) : undefined}
                style={{ cursor: isTag ? "help" : undefined }}
              >
                {t.text}
              </text>
            );
          })}
        </g>
        {markers.map((m) => {
          if (!m) return null;
          const active = focus === m.id;
          if (m.kind === "point")
            return (
              <g key={m.id} onClick={() => onFocus?.(m.id)} style={{ cursor: "pointer" }}>
                <circle cx={X(m.x)} cy={Y(m.y)} r={1.4} fill="none" stroke={m.color} strokeWidth={0.16} className="finding-ping" />
                <circle cx={X(m.x)} cy={Y(m.y)} r={active ? 2 : 1.5} fill="none" stroke={m.color} strokeWidth={active ? 0.32 : 0.22} />
                <text x={X(m.x)} y={Y(m.y) - 1.9} fontSize={0.62} textAnchor="middle" fill={m.color} fontWeight={700}>
                  {checkLabel(m.f.check)}
                </text>
              </g>
            );
          if (m.kind === "band")
            return (
              <text key={m.id + "l"} x={X(m.x) + m.w / 2} y={Y(9.1)} fontSize={0.72} textAnchor="middle" fill={m.color} fontWeight={700}>
                Over weight limit
              </text>
            );
          return (
            <g key={m.id} onClick={() => onFocus?.(m.id)} style={{ cursor: "pointer" }}>
              <rect x={X(m.x) - 4.2} y={Y(-9.4)} width={8.4} height={2.3} rx={0.4} fill="var(--sheet)" stroke={m.color} strokeWidth={active ? 0.2 : 0.12} strokeDasharray="0.5 0.35" />
              <text x={X(m.x)} y={Y(-9.4) + 1.5} fontSize={0.62} textAnchor="middle" fill={m.color} fontWeight={700}>
                {m.f.tag} not drawn
              </text>
            </g>
          );
        })}
      </svg>

      {hoverEq && hoverPos && (
        <div
          className="pointer-events-none absolute z-10 border border-ink bg-sheet px-3 py-2 text-xs shadow-[3px_3px_0_var(--ink)]"
          style={{ left: `${((X(hoverPos.x) - view.x) / view.w) * 100}%`, top: `${((Y(hoverPos.y) - view.y) / view.h) * 100}%`, transform: "translate(-50%, calc(-100% - 10px))" }}
        >
          <div className="font-mono font-medium">{hoverEq.tag}</div>
          <div>{hoverEq.name}</div>
          <div className="text-steel">
            {hoverEq.space}
            {hoverEq.mass_kg != null && <> · {(hoverEq.mass_kg / 1000).toFixed(2)} t</>} · row {hoverEq.row}
          </div>
        </div>
      )}

      {interactive && (
        <div className="absolute right-2 top-2 flex gap-1">
          {[
            ["Zoom in", "+", () => zoom(0.75)],
            ["Zoom out", "−", () => zoom(1.33)],
            ["Fit drawing", "Fit", () => setView({ x: 0, y: 0, w: W, h: H })],
          ].map(([label, glyph, fn]) => (
            <button
              key={label as string}
              aria-label={label as string}
              onClick={fn as () => void}
              className="min-w-8 border border-ink bg-sheet px-2 py-1 text-xs font-semibold hover:bg-film-deep"
            >
              {glyph as string}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
