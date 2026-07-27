// Pure display formatting for marketing figures (unit-tested; no Next
// dependencies so node --test can load it).

// "$4.1B" / "$630M" / "$85,000" from a CAD amount. Never fabricates
// precision: one decimal for billions, whole numbers below.
export function formatCadCompact(amount: number): string {
  if (amount >= 1e9) return `$${(amount / 1e9).toFixed(1)}B`;
  if (amount >= 1e6) return `$${Math.round(amount / 1e6)}M`;
  return `$${Math.round(amount).toLocaleString("en-CA")}`;
}

// "2,900+" style display counts: round DOWN to a clean step so the claim is
// always an undercount, never an overstatement.
export function formatCountFloor(n: number): string {
  if (n >= 1000) return `${(Math.floor(n / 100) * 100).toLocaleString("en-CA")}+`;
  if (n >= 100) return `${Math.floor(n / 10) * 10}+`;
  return String(n);
}
