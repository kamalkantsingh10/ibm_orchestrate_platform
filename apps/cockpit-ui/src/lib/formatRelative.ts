// Tiny English-only relative-time formatter (Story 2.3 AC #3, #10).
// Four bands:
//   - "just now"          (< 60s, including future skew)
//   - "N minutes ago"     (< 60min)
//   - "N hours ago"       (< 24h)
//   - "Apr 28"            (else; current locale's short month + day-of-month)

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function formatRelative(value: Date | string, now: Date = new Date()): string {
  const date = typeof value === 'string' ? new Date(value) : value;
  const deltaSec = Math.round((now.getTime() - date.getTime()) / 1_000);

  if (deltaSec < 60) {
    // Includes negative deltas (clock skew → treat as "just now").
    return 'just now';
  }

  const minutes = Math.floor(deltaSec / 60);
  if (minutes < 60) {
    return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  }

  return `${MONTHS[date.getMonth()]} ${date.getDate()}`;
}
