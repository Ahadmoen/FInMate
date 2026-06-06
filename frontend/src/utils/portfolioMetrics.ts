/** Portfolio health / risk labels as returned by portfolio analytics (same source as dashboard). */

/** Old dashboard copy → analytics health.label */
const LEGACY_HEALTH_LABEL: Record<string, string> = {
  steady: "NEUTRAL",
  healthy: "BULLISH",
  weak: "BEARISH",
};

export function formatHealthLabel(label: string | null | undefined): string {
  if (!label?.trim()) return "—";
  const key = label.trim().toLowerCase();
  const canonical = LEGACY_HEALTH_LABEL[key] ?? label.trim();
  return canonical.toUpperCase();
}

export function formatOverallRisk(risk: string | null | undefined): string {
  if (!risk?.trim()) return "—";
  return risk.trim().toUpperCase();
}
