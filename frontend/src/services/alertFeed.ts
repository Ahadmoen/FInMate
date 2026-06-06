import Constants from "expo-constants";

const metroHost = Constants.expoConfig?.hostUri?.split(":")[0];
const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  (metroHost ? `http://${metroHost}:3100/api/v1` : "http://localhost:3100/api/v1");

export type NotificationType = "TOP_PICK" | "DIGEST" | "POSITION_ALERT";
export type NotificationCategory = "stock" | "digest";

export type FeedNotification = {
  id: string;
  type: NotificationType;
  category: NotificationCategory;
  read_at: string | null;
  created_at: string;
  title: string;
  body: string;
  ticker: string;
  signal: string;
  alert_window: string;
  reason: string;
};

const WINDOW_LABELS: Record<string, string> = {
  PRE_MARKET: "Pre-Market",
  MID_SESSION: "Mid-Session",
  POST_MARKET: "Post-Market",
};

const TYPE_LABELS: Record<NotificationType, string> = {
  TOP_PICK: "Top Pick",
  DIGEST: "Market Digest",
  POSITION_ALERT: "Position Alert",
};

const FEED_BODY_MAX_WORDS = 120;

function truncateWords(text: string, maxWords = FEED_BODY_MAX_WORDS): string {
  const trimmed = text.trim();
  if (!trimmed) return "";
  const words = trimmed.split(/\s+/);
  if (words.length <= maxWords) return trimmed;
  return `${words.slice(0, maxWords).join(" ")}…`;
}

function windowLabel(alertWindow: string): string {
  return WINDOW_LABELS[alertWindow] ?? alertWindow.replace(/_/g, " ");
}

/** Build card title when API omits `title` (older backend). */
export function buildNotificationTitle(
  type: NotificationType,
  ticker: string,
  alertWindow: string,
): string {
  const window = windowLabel(alertWindow);
  if (type === "DIGEST") return `${TYPE_LABELS.DIGEST} — ${window}`;
  const displayTicker = ticker && ticker !== "DIGEST" ? ticker : "PSX";
  return `${TYPE_LABELS[type] ?? type}: ${displayTicker} — ${window}`;
}

/** Map one API row (flat or nested `alert`) into a feed card shape. */
export function normalizeFeedNotification(raw: unknown): FeedNotification | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const nested =
    row.alert && typeof row.alert === "object" ? (row.alert as Record<string, unknown>) : null;

  const id = row.id != null ? String(row.id) : "";
  if (!id) return null;

  const type = (row.type ?? nested?.type ?? "TOP_PICK") as NotificationType;
  const category = (row.category ?? nested?.category ?? "stock") as NotificationCategory;
  const ticker = String(row.ticker ?? nested?.ticker ?? "");
  const signal = String(row.signal ?? nested?.signal ?? "");
  const alert_window = String(row.alert_window ?? nested?.alert_window ?? "");
  const reason = String(row.reason ?? nested?.reason ?? "").trim();
  const created_at = String(row.created_at ?? nested?.created_at ?? "");
  const read_at =
    row.read_at === undefined && nested?.read_at === undefined
      ? null
      : ((row.read_at ?? nested?.read_at ?? null) as string | null);

  const titleRaw = String(row.title ?? "").trim();
  const bodyRaw = String(row.body ?? "").trim();
  const title = titleRaw || buildNotificationTitle(type, ticker, alert_window);
  const body =
    bodyRaw ||
    truncateWords(reason) ||
    "Tap to read the full alert.";

  return {
    id,
    type,
    category,
    read_at,
    created_at,
    title,
    body,
    ticker,
    signal,
    alert_window,
    reason,
  };
}

export type NewsPayloadItem = {
  headline?: string;
  link?: string;
  source?: string;
  sentiment?: string;
};

export type DigestTickerRow = {
  ticker: string;
  close?: number;
  change_pct?: number;
  rsi14?: number;
  summary?: string;
};

export type NotificationPayload = {
  ticker?: string;
  signal?: string;
  confidence?: string;
  close?: number;
  change_pct?: number;
  rsi14?: number;
  ma50?: number;
  ma200?: number;
  volatility20d?: number;
  news?: NewsPayloadItem[];
  summary?: string;
  window_label?: string;
  type?: NotificationType;
  tickers?: DigestTickerRow[];
  count?: number;
  qty?: number;
  avg_buy?: number;
  current?: number;
  pnl_pct?: number;
  pnl_pkr?: number;
};

export type NotificationDetail = {
  id: string;
  type: NotificationType;
  category: NotificationCategory;
  read_at: string | null;
  created_at: string;
  title: string;
  body: string;
  window_label: string;
  alert: {
    id: string;
    ticker: string;
    symbols: string[];
    signal: string;
    alert_window: string;
    reason: string;
    created_at: string;
  };
  payload: NotificationPayload | null;
};

function extractError(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const d = data as Record<string, unknown>;
  if (typeof d.detail === "string") return d.detail;
  const firstVal = Object.values(d)[0];
  if (Array.isArray(firstVal) && firstVal.length > 0) return String(firstVal[0]);
  return fallback;
}

function authFetch(path: string, token: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
}

/** DRF default pagination wraps lists as `{ count, next, previous, results }`. */
function unwrapList<T>(raw: unknown): T[] {
  if (Array.isArray(raw)) return raw as T[];
  if (raw && typeof raw === "object" && Array.isArray((raw as Record<string, unknown>).results)) {
    return (raw as Record<string, unknown>).results as T[];
  }
  return [];
}

export async function fetchNotifications(
  token: string,
  days = 10,
): Promise<FeedNotification[]> {
  const response = await authFetch(`/alerts/notifications/?days=${days}`, token);
  if (!response.ok) {
    const json = await response.json().catch(() => null);
    throw new Error(extractError(json, "Failed to load notifications."));
  }
  const raw = await response.json();
  return unwrapList(raw)
    .map((item) => normalizeFeedNotification(item))
    .filter((item): item is FeedNotification => item != null);
}

export async function fetchNotificationDetail(
  token: string,
  id: string,
): Promise<NotificationDetail> {
  const response = await authFetch(`/alerts/notifications/${id}/detail/`, token);
  if (!response.ok) {
    const json = await response.json().catch(() => null);
    throw new Error(extractError(json, "Failed to load notification detail."));
  }
  return response.json();
}

export async function markNotificationRead(
  token: string,
  id: string,
): Promise<FeedNotification> {
  const response = await authFetch(`/alerts/notifications/${id}/read/`, token, {
    method: "PATCH",
  });
  if (!response.ok) {
    const json = await response.json().catch(() => null);
    throw new Error(extractError(json, "Failed to mark notification as read."));
  }
  return response.json();
}

export async function fetchUnreadNotificationCount(token: string): Promise<number> {
  const response = await authFetch("/alerts/notifications/unread-count/", token);
  if (!response.ok) {
    return 0;
  }
  const data = (await response.json()) as { count?: number };
  const count = data.count;
  return typeof count === "number" && count >= 0 ? count : 0;
}

export async function markAllNotificationsRead(token: string): Promise<number> {
  const response = await authFetch(`/alerts/notifications/mark-all-read/`, token, {
    method: "POST",
  });
  if (!response.ok) {
    const json = await response.json().catch(() => null);
    throw new Error(extractError(json, "Failed to clear notifications."));
  }
  const data = (await response.json()) as { marked?: number };
  return data.marked ?? 0;
}

export function formatNotificationTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return "";
  const diffMs = Date.now() - then;
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-PK", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
