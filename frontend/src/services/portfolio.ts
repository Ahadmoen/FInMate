import Constants from "expo-constants";

const metroHost = Constants.expoConfig?.hostUri?.split(":")[0];
const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  (metroHost ? `http://${metroHost}:3100/api/v1` : "http://localhost:3100/api/v1");

// ─── Types ────────────────────────────────────────────────────────────────────

/**
 * One item from GET /api/v1/core/stock-search/
 * `symbol_id` is the StockSymbol UUID used when POSTing a new holding.
 */
export type StockSearchResult = {
  symbol_id: string;
  symbol: string;
  name: string;
  industry: string;
  current_price: string | null;
  change_percent: number | null;
  last_close: number | null;
  price_updated_at: string | null;
};

/**
 * One item from GET /api/v1/portfolio/holdings/
 * Includes live price and computed P&L fields from the backend.
 */
export type PortfolioHolding = {
  id: string;
  symbol_id: string;
  ticker: string;
  name: string;
  industry: string;
  quantity: string;
  avg_buy_price: string;
  total_invested: number | null;
  current_price: number | null;
  current_value: number | null;
  change_percent: number | null;
  unrealized_pnl: number | null;
  return_pct: number | null;
  price_updated_at: string | null;
  added_at: string;
  updated_at: string;
};

/**
 * Body for POST /api/v1/portfolio/holdings/
 */
export type AddHoldingInput = {
  symbol_id: string;
  quantity: number;
  avg_buy_price: number;
};

export type UpdateHoldingInput = {
  quantity: number;
  avg_buy_price: number;
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

function unwrapList<T>(raw: unknown): T[] {
  if (Array.isArray(raw)) return raw as T[];
  if (raw && typeof raw === "object" && Array.isArray((raw as Record<string, unknown>).results)) {
    return (raw as Record<string, unknown>).results as T[];
  }
  return [];
}

// ─── Stock search ─────────────────────────────────────────────────────────────

/**
 * GET /api/v1/core/stock-search/
 * Fetch all active PSX stocks once on mount; filter client-side.
 */
export async function fetchAllStocks(token: string): Promise<StockSearchResult[]> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/core/stock-search/`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error("Network error. Check your connection or backend status.");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, `Server returned ${response.status}`));
  }

  return unwrapList<StockSearchResult>(await response.json());
}

// ─── Portfolio holdings ───────────────────────────────────────────────────────

/**
 * GET /api/v1/portfolio/holdings/
 * Returns the authenticated user's holdings enriched with live price data.
 */
export async function fetchHoldings(token: string): Promise<PortfolioHolding[]> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/portfolio/holdings/`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error("Network error. Check your connection or backend status.");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Failed to load portfolio."));
  }

  return unwrapList<PortfolioHolding>(await response.json());
}

/**
 * POST /api/v1/portfolio/holdings/
 * Add a new holding. Returns the created holding enriched with live data.
 *
 * Throws with a human-readable message for:
 *   - duplicate (stock already in portfolio)
 *   - invalid quantity / avg_buy_price
 *   - unknown symbol_id
 */
export async function addHolding(
  token: string,
  input: AddHoldingInput,
): Promise<PortfolioHolding> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/portfolio/holdings/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(input),
    });
  } catch {
    throw new Error("Network error. Check your connection or backend status.");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Failed to add holding."));
  }

  return response.json() as Promise<PortfolioHolding>;
}

/**
 * PATCH /api/v1/portfolio/holdings/<id>/
 * Update quantity and weighted-average buy price for an existing holding.
 */
export async function updateHolding(
  token: string,
  id: string,
  input: UpdateHoldingInput,
): Promise<PortfolioHolding> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/portfolio/holdings/${id}/`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(input),
    });
  } catch {
    throw new Error("Network error. Check your connection or backend status.");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Failed to update holding."));
  }

  return response.json() as Promise<PortfolioHolding>;
}

/**
 * DELETE /api/v1/portfolio/holdings/<id>/
 */
export async function deleteHolding(token: string, id: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/portfolio/holdings/${id}/`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error("Network error.");
  }

  if (!response.ok && response.status !== 204) {
    throw new Error("Failed to delete holding.");
  }
}

// ─── Portfolio analytics ──────────────────────────────────────────────────────

export type PortfolioAnalyticsSummary = {
  total_portfolio_value: number;
  total_cost_basis: number;
  total_unrealized_pnl: number;
  total_pnl_pct: number;
  todays_total_change: number;
  todays_total_pct: number;
  total_holdings: number;
  updated_at: string;
};

export type PortfolioHealth = {
  score: number;
  raw_score: number;
  label: string;
  primary_driver: string;
};

export type SectorAllocation = {
  industry: string;
  value: number;
  weight_pct: number;
  stock_count: number;
};

export type ConcentrationWarning = {
  type: string;
  message: string;
  severity: string;
};

export type PortfolioAllocation = {
  total_holdings: number;
  sectors: SectorAllocation[];
  concentration_warnings: ConcentrationWarning[];
};

export type AnalyticsHolding = {
  id: string;
  symbol_id: string;
  symbol: string;
  name: string;
  industry: string;
  quantity: number;
  avg_buy_price: number;
  current_price: number;
  current_value: number;
  cost_basis: number;
  unrealized_pnl: number;
  pnl_pct: number;
  todays_change_pct: number;
  position_weight: number;
  forecast_change_pct?: number;
  forecast_direction?: string | null;
  forecast_confidence?: number | null;
  health_label: string | null;
  health_score?: number;
  rsi14?: number;
  action: string | null;
  signal_confidence: string | null;
  blended_score?: number;
  reason: string | null;
  dominant_sentiment?: string | null;
  price_stale?: boolean;
};

export type PortfolioRecommendation = {
  symbol: string;
  name: string;
  label: string;
  severity: string;
  color: string;
  reason: string;
  pnl_pct: number;
  current_value: number;
  position_weight: number;
};

export type PortfolioAnalyticsNewsItem = {
  id: string;
  symbol: string;
  symbol_name: string;
  headline: string;
  source: string;
  link: string;
  sentiment: string;
  score: number;
  tone: "positive" | "neutral" | "negative";
  published_at: string;
  time_ago: string;
};

export type PortfolioAnalyticsResponse = {
  success: boolean;
  user_id: string;
  has_holdings: boolean;
  summary?: PortfolioAnalyticsSummary;
  health?: PortfolioHealth | null;
  allocation?: PortfolioAllocation | null;
  holdings?: {
    featured_holdings: AnalyticsHolding[];
    all_holdings: AnalyticsHolding[];
  };
  recommendations?: {
    recommendations: PortfolioRecommendation[];
  };
  risk?: {
    overall_risk: string;
    downside_exposure_pct: number;
    divergence_count: number;
    divergent_symbols?: string[];
    weighted_volatility: number;
  } | null;
  news?: {
    total: number;
    items: PortfolioAnalyticsNewsItem[];
  };
  generated_at?: string;
};

/**
 * GET /api/v1/portfolio/analytics/
 * Full portfolio analysis: summary, health, allocation, holdings, alerts, news.
 */
export async function fetchPortfolioAnalytics(
  token: string,
): Promise<PortfolioAnalyticsResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/portfolio/analytics/`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error("Network error. Check your connection or backend status.");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Failed to load portfolio analytics."));
  }

  return response.json() as Promise<PortfolioAnalyticsResponse>;
}
