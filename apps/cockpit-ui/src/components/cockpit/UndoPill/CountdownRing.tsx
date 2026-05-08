// CountdownRing — Story 7.5 / AC #5.
//
// SVG ring driven by ``remaining / total``. Stroke colour flips from
// amber to rose at the 30-second urgency threshold; the smoothing
// transition is suppressed under prefers-reduced-motion (Tailwind's
// ``motion-reduce:transition-none``).

import clsx from 'clsx';

export interface CountdownRingProps {
  remaining: number;
  total: number;
}

export function CountdownRing({ remaining, total }: CountdownRingProps) {
  const radius = 13;
  const circumference = 2 * Math.PI * radius;
  const safeTotal = total > 0 ? total : 1;
  const offset = circumference * (1 - Math.max(0, Math.min(1, remaining / safeTotal)));
  const isUrgent = remaining <= 30;
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 28 28"
      className="motion-reduce:transition-none"
      role="img"
      aria-label={`${Math.ceil(remaining)} seconds remaining`}
      data-testid="countdown-ring"
      data-urgent={isUrgent ? 'true' : 'false'}
    >
      <circle cx="14" cy="14" r={radius} className="fill-none stroke-zinc-200 stroke-2" />
      <circle
        cx="14"
        cy="14"
        r={radius}
        className={clsx(
          'fill-none stroke-2 transition-[stroke-dashoffset] duration-100 ease-linear',
          'motion-reduce:transition-none',
          isUrgent ? 'stroke-rose-500' : 'stroke-amber-500',
        )}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform="rotate(-90 14 14)"
      />
      <text
        x="14"
        y="14"
        textAnchor="middle"
        dominantBaseline="central"
        className="text-[10px] font-mono fill-zinc-900"
      >
        {Math.ceil(remaining)}
      </text>
    </svg>
  );
}
