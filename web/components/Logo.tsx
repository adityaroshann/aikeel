// Wordmark: a hull section with its keel, followed by condensed lettering.
export default function Logo({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 132 32" className={className} role="img" aria-label="AIkeel">
      <path d="M2 9 H28 L24 19 Q15 23 6 19 Z" fill="none" stroke="var(--ink)" strokeWidth="2.2" strokeLinejoin="round" />
      <path d="M15 21.5 V29" stroke="var(--red)" strokeWidth="3" strokeLinecap="square" />
      <text
        x="36"
        y="24"
        fill="var(--ink)"
        style={{ fontFamily: "var(--font-archivo)", fontVariationSettings: '"wdth" 66', fontWeight: 800, fontSize: 25 }}
      >
        A
      </text>
      {/* serifed I so the mark never reads as "Al" */}
      <path d="M52 6.5 H62 M57 6.5 V23.5 M52 23.5 H62" stroke="var(--ink)" strokeWidth="3.6" />
      <text
        x="64"
        y="24"
        fill="var(--ink)"
        style={{ fontFamily: "var(--font-archivo)", fontVariationSettings: '"wdth" 66', fontWeight: 800, fontSize: 25 }}
      >
        keel
      </text>
    </svg>
  );
}
