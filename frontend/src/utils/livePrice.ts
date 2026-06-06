type LiveChangeInput = {
  change_pct?: number | null;
  open_price?: number | null;
  close?: number | null;
};

/**
 * Resolve today's % change for display.
 * Uses stored change_pct when non-zero; otherwise open→close on the live bar,
 * then optional navigation fallback (insights list → detail).
 */
export function resolveLiveChangePct(
  live: LiveChangeInput | null | undefined,
  fallback?: number | null,
): number | null {
  const stored = live?.change_pct;

  if (stored != null && stored !== 0) {
    return stored;
  }

  const open = live?.open_price;
  const close = live?.close;
  if (open != null && close != null && open > 0) {
    const computed = ((close - open) / open) * 100;
    if (Math.abs(computed) >= 1e-9) {
      return computed;
    }
  }

  if (fallback != null && fallback !== 0) {
    return fallback;
  }

  if (stored != null) {
    return stored;
  }

  return fallback ?? null;
}

/** Format today's % change for stock cards (null → "—"). */
export function formatDayChangePct(
  change: number | null | undefined,
  opts?: { suffix?: string; decimals?: number },
): string {
  if (change == null || !Number.isFinite(change)) return "—";
  const decimals = opts?.decimals ?? 1;
  const pos = change >= 0;
  const core = `${pos ? "+" : ""}${change.toFixed(decimals)}%`;
  return opts?.suffix ? `${core} ${opts.suffix}` : core;
}

const PKT = "Asia/Karachi";

function pktCalendarDay(d: Date): string {
  return d.toLocaleDateString("en-CA", { timeZone: PKT });
}

function formatPktClock(d: Date): string {
  return `${d.toLocaleTimeString("en-US", {
    timeZone: PKT,
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  })} PKT`;
}

/**
 * Format live price refresh time for UI ("Updated …").
 * Backend sends ISO UTC from live_market_data.updated_at (last ingest), not bar `date`.
 */
export function formatLivePriceUpdated(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return null;

    const timePkt = formatPktClock(date);
    const now = new Date();

    if (pktCalendarDay(date) === pktCalendarDay(now)) {
      return `Updated today, ${timePkt}`;
    }

    const monthDay = date.toLocaleDateString("en-US", {
      timeZone: PKT,
      month: "short",
      day: "numeric",
    });
    return `Updated ${monthDay}, ${timePkt}`;
  } catch {
    return null;
  }
}
