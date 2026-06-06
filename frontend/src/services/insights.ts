import Constants from "expo-constants";

const metroHost = Constants.expoConfig?.hostUri?.split(":")[0];
const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  (metroHost ? `http://${metroHost}:3100/api/v1` : "http://localhost:3100/api/v1");

// ─── Types ────────────────────────────────────────────────────────────────────

export type InsightsFilterOption = { id: string; label: string };

export type InsightsFiltersResponse = {
  sectors: InsightsFilterOption[];
  trends: InsightsFilterOption[];
  sort_options: InsightsFilterOption[];
};

export type InsightStockCard = {
  symbol_id: string;
  ticker: string;
  company_name: string;
  sector: string;
  close: number | null;
  change_pct: number | null;
  price_updated_at: string | null;
  signal: string | null;
  signal_label: string | null;
  health_label: string | null;
  health_display: string | null;
  suggestion_confidence: string | null;
  confidence_display: string | null;
  rsi14: number | null;
  signal_strength_dots: number;
};

export type InsightsListResponse = {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: InsightStockCard[];
};

export type InsightLiveData = {
  close: number;
  change_pct: number | null;
  open_price: number;
  high: number;
  low: number;
  volume: number;
  rsi14: number | null;
  ma20: number | null;
  ma50: number | null;
  ma200: number | null;
  volatility20d: number | null;
  volume_ratio: number | null;
  eps: number | null;
  as_of: string | null;
};

export type InsightSignalData = {
  action: string;
  signal_label: string | null;
  health_label: string | null;
  health_display: string | null;
  suggestion_confidence: string | null;
  confidence_display: string | null;
  confidence: number;
  blended_score: number | null;
  forecast_score: number;
  sentiment_score: number;
  dominant_sentiment: string | null;
  horizon: number | null;
  reason: string;
  contributions: Record<string, number>;
  signal_strength_dots: number;
  valid_until: string | null;
  generated_at: string | null;
};

export type InsightForecastData = {
  direction: string;
  predicted_price: number;
  expected_change_pct: number | null;
  confidence: number;
  mape: number | null;
  model_used: string;
  forecast_date: string | null;
};

export type InsightStockDetail = {
  symbol_id: string;
  ticker: string;
  company_name: string;
  sector: string;
  live: InsightLiveData | null;
  signal: InsightSignalData | null;
  forecast: InsightForecastData | null;
};

export type InsightNewsItem = {
  id: string;
  headline: string;
  source: string;
  link: string;
  sentiment: string;
  score: number;
  tone: "positive" | "negative" | "neutral";
  published_at: string | null;
  time_ago: string;
};

export type InsightNewsResponse = {
  ticker: string;
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
  items: InsightNewsItem[];
};

/** Params passed from list card → detail screen (instant render). */
export type InsightCardParams = {
  symbol_id: string;
  ticker: string;
  company_name: string;
  sector: string;
  close: string;
  change_pct: string;
  signal: string;
  signal_label: string;
  health_display: string;
  confidence_display: string;
  rsi14: string;
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function extractError(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const d = data as Record<string, unknown>;
  if (typeof d.detail === "string") return d.detail;
  const firstVal = Object.values(d)[0];
  if (Array.isArray(firstVal) && firstVal.length > 0) return String(firstVal[0]);
  return fallback;
}

async function authGet(path: string, token: string): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  });
  const s = qs.toString();
  return s ? `?${s}` : "";
}

// ─── API ──────────────────────────────────────────────────────────────────────

export async function fetchInsightsFilters(token: string): Promise<InsightsFiltersResponse> {
  const response = await authGet("/insights/filters/", token);
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Failed to load filters."));
  }
  return response.json();
}

export async function fetchInsightsStocks(
  token: string,
  opts: {
    q?: string;
    sector?: string;
    trend?: string;
    sort?: string;
    page?: number;
  } = {},
): Promise<InsightsListResponse> {
  const query = buildQuery({
    q: opts.q,
    sector: opts.sector,
    trend: opts.trend,
    sort: opts.sort,
    page: opts.page ?? 1,
    page_size: 10,
  });

  let response: Response;
  try {
    response = await authGet(`/insights/stocks/${query}`, token);
  } catch {
    throw new Error("Network error. Check your connection.");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Failed to load stocks."));
  }

  return response.json();
}

export async function fetchInsightDetail(
  token: string,
  ticker: string,
): Promise<InsightStockDetail> {
  const response = await authGet(`/insights/stocks/${encodeURIComponent(ticker)}/`, token);
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Failed to load stock detail."));
  }
  return response.json();
}

export async function fetchInsightNews(
  token: string,
  ticker: string,
  offset = 0,
  limit = 5,
): Promise<InsightNewsResponse> {
  const query = buildQuery({ offset, limit });
  const response = await authGet(
    `/insights/stocks/${encodeURIComponent(ticker)}/news/${query.startsWith("?") ? query : `?${query}`}`,
    token,
  );
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Failed to load news."));
  }
  return response.json();
}
