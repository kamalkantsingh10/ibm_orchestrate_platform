// SealIcon — Story 7.6 / AC #3.
//
// Decorative wax-seal-style SVG. Aria-hidden + pointer-events-none —
// not a button (the SealedIndicator that replaces it carries the
// click-to-trace affordance).

export function SealIcon() {
  return (
    <svg
      viewBox="0 0 40 40"
      width="40"
      height="40"
      aria-hidden="true"
      className="pointer-events-none"
    >
      <circle cx="20" cy="20" r="18" className="fill-amber-700/90 stroke-amber-900 stroke-1" />
      <circle cx="20" cy="20" r="12" className="fill-none stroke-amber-100/40 stroke-1" />
      <text
        x="20"
        y="20"
        textAnchor="middle"
        dominantBaseline="central"
        className="fill-amber-100 text-[10px] font-serif font-semibold"
      >
        SEAL
      </text>
    </svg>
  );
}
