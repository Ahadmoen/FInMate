import Constants from "expo-constants";

const metroHost = Constants.expoConfig?.hostUri?.split(":")[0];
const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  (metroHost ? `http://${metroHost}:3100/api/v1` : "http://localhost:3100/api/v1");

export type NewsFilterOption = { id: string; label: string };

export type NewsFiltersResponse = {
  sentiments: NewsFilterOption[];
  industries: NewsFilterOption[];
  stocks: NewsFilterOption[];
};

export type MarketSentimentIndex = {
  value: number;
  change_pct: number;
  progress: number;
  phase: string;
  message: string;
  window_days: number;
};

export type NewsArticle = {
  id: string;
  ticker: string;
  headline: string;
  source: string;
  link: string;
  status_badge: string;
  sentiment_label: string;
  sentiment_tone: "positive" | "neutral" | "negative";
  score: number;
  published_at: string | null;
  time_ago: string;
};

export type NewsFeedResponse = {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: NewsArticle[];
};

export type NewsSearchResponse = NewsFeedResponse & {
  q: string;
};

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

export async function fetchNewsFilters(token: string): Promise<NewsFiltersResponse> {
  const response = await authGet("/news/filters/", token);
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Failed to load news filters."));
  }
  return response.json();
}

export async function fetchMarketSentimentIndex(token: string): Promise<MarketSentimentIndex> {
  const response = await authGet("/news/sentiment-index/", token);
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Failed to load market sentiment."));
  }
  return response.json();
}

export async function fetchNewsFeed(
  token: string,
  opts: {
    sentiment?: string;
    industry?: string;
    stock?: string;
    page?: number;
  } = {},
): Promise<NewsFeedResponse> {
  const query = buildQuery({
    sentiment: opts.sentiment ?? "all",
    industry: opts.industry ?? "all",
    stock: opts.stock ?? "all",
    page: opts.page ?? 1,
  });

  let response: Response;
  try {
    response = await authGet(`/news/feed/${query}`, token);
  } catch {
    throw new Error("Network error. Check your connection.");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Failed to load news feed."));
  }

  return response.json();
}

export async function fetchNewsSearch(
  token: string,
  opts: {
    q: string;
    sentiment?: string;
    industry?: string;
    stock?: string;
    page?: number;
  },
): Promise<NewsSearchResponse> {
  const query = buildQuery({
    q: opts.q,
    sentiment: opts.sentiment ?? "all",
    industry: opts.industry ?? "all",
    stock: opts.stock ?? "all",
    page: opts.page ?? 1,
  });

  let response: Response;
  try {
    response = await authGet(`/news/search/${query}`, token);
  } catch {
    throw new Error("Network error. Check your connection.");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Failed to search news."));
  }

  return response.json();
}
