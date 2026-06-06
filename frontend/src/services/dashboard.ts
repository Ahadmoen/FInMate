import Constants from "expo-constants";

const metroHost = Constants.expoConfig?.hostUri?.split(":")[0];
const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  (metroHost ? `http://${metroHost}:3100/api/v1` : "http://localhost:3100/api/v1");

// ─── Types ────────────────────────────────────────────────────────────────────

export type PortfolioHealth = {
  /** BULLISH | NEUTRAL | BEARISH — from portfolio analytics health.label */
  status: string;
  score: number;
  rawScore?: number;
  primaryDriver?: string;
  totalValue: number;
  changePercent: number;
  /** LOW | MODERATE | HIGH — from portfolio analytics risk.overall_risk */
  riskLevel: string;
  downsideExposurePct?: number;
  riskLabel: string;
  diversificationScore: number;
  diversificationLabel: string;
  totalHoldings: number;
};

export type AIPickStock = {
  ticker: string;
  /** Display name shown below the ticker icon */
  companyName: string;
  /** e.g. "Commercial Banking" */
  sector: string;
  price: number;
  priceUpdatedAt?: string | null;
  changePercent: number | null;
  currency?: string;
  /** Analyst forecast % */
  forecast?: number;
  signal?: SignalType;
  rsi?: number;
  /** Italic analyst quote shown at the bottom of the card */
  description?: string;
  /** Top-right badge label, e.g. "TOP PICK" */
  badge?: string;
};

export type NewsSentiment = "POSITIVE" | "NEUTRAL" | "NEGATIVE";

export type NewsItem = {
  id: string;
  sentiment: NewsSentiment;
  title: string;
  source: string;
  timeAgo: string;
};

export type MarketIntelligence = {
  news: NewsItem[];
};

export type SignalType = "BULLISH" | "NEUTRAL" | "BEARISH";

export type TopPerformer = {
  ticker: string;
  company: string;
  sector: string;
  price: number;
  priceUpdatedAt?: string | null;
  /** today's % change shown on compact rows */
  changePercent: number | null;
  currency?: string;
  signal: SignalType;
  rsi: number;
  /** Featured card only — analyst forecast % */
  forecast?: number;
  /** Featured card only — e.g. "STRONG BUY" */
  signalLabel?: string;
  /** Featured card only — e.g. "GOOD" */
  sentiment?: string;
};

export type RisingStar = {
  ticker: string;
  company: string;
  sector: string;
  price: number;
  priceUpdatedAt?: string | null;
  /** today's % change */
  changePercent: number | null;
  currency?: string;
  signal: SignalType;
  /** e.g. "BUY SIGNAL", "ACCUMULATE", "STRONG BUY" */
  signalLabel: string;
  /** filled dots count out of 3 */
  signalStrength: 1 | 2 | 3;
  /** 90-day analyst forecast % */
  forecast90d: number;
  /** e.g. "EXCELLENT", "GOOD", "FAIR" */
  sentimentLabel: string;
  /** e.g. "LOW RISK", "MED RISK" */
  riskLabel: string;
};

export type MarketMoodSentiment = "Optimistic" | "Pessimistic" | "Neutral" | "Volatile";
export type NewsSentimentType   = "Positive" | "Negative" | "Neutral";

export type MarketMood = {
  sentiment: MarketMoodSentiment;
  /** bullish stock count (also used as the headline score) */
  score: number;
  /** total stocks tracked, e.g. 180 */
  totalStocks: number;
  /** one-line market caption */
  caption: string;
  bullCount: number;
  bearCount: number;
  neutralCount: number;
  /** signal breakdown */
  buySignals: number;
  holdSignals: number;
  sellSignals: number;
  /** news sentiment */
  newsSentiment: NewsSentimentType;
  /** % of stocks with this news sentiment */
  newsSentimentPercent: number;
  /** 0–100 confidence index */
  confidenceIndex: number;
  hottestSector: string;
  updatedAt: string;
};

export type SectorLabel    = "Strong" | "Neutral" | "Caution" | "Weak";
export type SectorSentiment = "Bullish" | "Neutral" | "Bearish";

export type SectorItem = {
  id: string;
  name: string;
  changePercent: number;
  label: SectorLabel;
  stockCount: number;
  /** average 90d forecast % — shown as "+X.X% avg forecast" */
  avgForecast: number;
  buyCount: number;
  holdCount: number;
  sellCount: number;
  sentiment: SectorSentiment;
  isHottest?: boolean;
  /** lucide icon key: "monitor" | "landmark" | "building" | "zap" | "shopping-bag" */
  iconKey: string;
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function authGet(path: string, token: string): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });
}

// ─── Dashboard Stocks API ─────────────────────────────────────────────────────
// Raw API shape for GET /dashboard/stocks

export type ApiTopPerformerStock = {
  name: string;
  rsi14: number;
  symbol: string;
  industry: string;
  health_label: string;
  health_score: number;
  blended_score: number;
  current_price: number;
  price_updated_at?: string | null;
  signal_action: string;
  signal_strength: string;
  change_pct_today: number | null;
  signal_confidence: string;
  dominant_sentiment: string;
  forecast_direction: string;
  forecast_change_pct: number;
};

export type ApiRisingStarStock = {
  name: string;
  rsi14: number;
  action: string;
  reason: string;
  symbol: string;
  industry: string;
  is_top_pick: boolean;
  health_label: string;
  volume_ratio: number;
  blended_score: number;
  current_price: number;
  price_updated_at?: string | null;
  change_pct_today: number | null;
  dominant_sentiment: string;
  forecast_change_pct: number;
  forecast_confidence: number;
};

export type ApiSectorData = {
  trend: "up" | "neutral" | "down";
  sector: string;
  buy_count: number;
  hold_count: number;
  is_hottest: boolean;
  sell_count: number;
  stock_count: number;
  health_label: string;
  avg_forecast_pct: number;
  avg_health_score: number;
};

export type ApiAIPickData = {
  name: string;
  rsi14: number;
  reason: string;
  symbol: string;
  industry: string;
  picked_at: string;
  health_label: string;
  blended_score: number;
  current_price: number;
  price_updated_at?: string | null;
  signal_action: string;
  change_pct_today: number | null;
  signal_confidence: string;
  dominant_sentiment: string;
  forecast_change_pct: number;
  forecast_confidence: number;
};

export type ApiMarketMoodData = {
  total: number;
  buy_count: number;
  hold_count: number;
  mood_label: string;
  sell_count: number;
  weak_count: number;
  steady_count: number;
  strong_count: number;
  hottest_sector: string;
  news_sentiment: string;
  confidence_index: number;
  avg_sentiment_score: number;
};

export type ApiPortfolioHealth = {
  /** BULLISH | NEUTRAL | BEARISH */
  health_label?: string;
  label: string;
  score: number;
  raw_score?: number;
  primary_driver?: string;
  /** LOW | MODERATE | HIGH */
  overall_risk?: string;
  risk_level: string;
  downside_exposure_pct?: number;
  total_value: number;
  risk_sublabel: string;
  total_holdings: number;
  todays_change_pct: number;
  diversification_label: string;
  diversification_score: number;
};

export type DashboardStocksResponse = {
  market_summary: { buy: number; hold: number; sell: number; total: number };
  market_mood: ApiMarketMoodData;
  ai_pick: ApiAIPickData;
  rising_stars: {
    total: number;
    stocks: ApiRisingStarStock[];
    sector_filter: string;
  };
  sector_performance: { sectors: ApiSectorData[] };
  top_performers: {
    list: ApiTopPerformerStock[];
    featured: ApiTopPerformerStock;
  };
  portfolio_health: ApiPortfolioHealth | null;
  generated_at: string;
};

export type ApiDashboardNewsItem = {
  id: string;
  link: string;
  tone: "positive" | "negative" | "neutral";
  score: number;
  source: string;
  symbol: string;
  headline: string;
  time_ago: string;
  sentiment: string;
  symbol_name: string;
  published_at: string;
};

export type DashboardNewsResponse = {
  total: number;
  items: ApiDashboardNewsItem[];
};

// ─── Internal Mapping Helpers ─────────────────────────────────────────────────

function _mapSignal(action: string): SignalType {
  const a = action.toUpperCase();
  if (a.includes("BUY")) return "BULLISH";
  if (a.includes("SELL")) return "BEARISH";
  return "NEUTRAL";
}

function _formatSignalLabel(action: string): string {
  return action.replace(/_/g, " ");
}

function _mapSignalStrength(action: string): 1 | 2 | 3 {
  const a = action.toUpperCase();
  if (a === "STRONG_BUY") return 3;
  if (a === "BUY") return 2;
  return 1;
}

function _mapConfidence(confidence: string): string {
  if (confidence === "HIGH") return "GOOD";
  if (confidence === "MEDIUM") return "FAIR";
  return "WEAK";
}

function _mapHealthToSectorLabel(health: string): SectorLabel {
  if (health === "Strong") return "Strong";
  if (health === "Weak") return "Weak";
  return "Neutral";
}

function _mapHealthToSentiment(health: string): SectorSentiment {
  if (health === "Strong") return "Bullish";
  if (health === "Weak") return "Bearish";
  return "Neutral";
}

function _mapMoodLabel(moodLabel: string): MarketMoodSentiment {
  const m = moodLabel.toLowerCase();
  if (m.includes("risk on") || m.includes("bullish") || m.includes("optimistic")) return "Optimistic";
  if (m.includes("risk off") || m.includes("bearish") || m.includes("pessimistic")) return "Pessimistic";
  if (m.includes("volatile")) return "Volatile";
  return "Neutral";
}

function _sectorIconKey(sector: string): string {
  const s = sector.toLowerCase();
  if (s.includes("tech") || s.includes("comm") || s.includes("bpo") || s.includes("it")) return "monitor";
  if (
    s.includes("bank") || s.includes("inv.") || s.includes("securities") ||
    s.includes("modaraba") || s.includes("leasing") || s.includes("insurance") ||
    s.includes("reit") || s.includes("real estate") || s.includes("mutual fund")
  ) return "landmark";
  if (
    s.includes("oil") || s.includes("gas") || s.includes("refinery") ||
    s.includes("energy") || s.includes("power") || s.includes("fuel")
  ) return "zap";
  if (s.includes("food") || s.includes("pharma") || s.includes("fmcg") || s.includes("retail")) return "shopping";
  return "building";
}

function _formatPKTTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    const pktHours = (date.getUTCHours() + 5) % 24;
    const pktMinutes = date.getUTCMinutes();
    const ampm = pktHours >= 12 ? "PM" : "AM";
    const h12 = pktHours % 12 || 12;
    return `${h12}:${pktMinutes.toString().padStart(2, "0")} ${ampm} PKT`;
  } catch {
    return "N/A";
  }
}

// ─── Mappers (exported for dashboard screen) ──────────────────────────────────

function _mapNewsSentiment(
  sentiment: string,
  tone: ApiDashboardNewsItem["tone"],
): NewsSentiment {
  const s = sentiment.toUpperCase();
  if (s === "EXCELLENT" || tone === "positive") return "POSITIVE";
  if (s === "VERY_BAD" || tone === "negative") return "NEGATIVE";
  return "NEUTRAL";
}

export function mapToPortfolioHealth(api: ApiPortfolioHealth): PortfolioHealth {
  const healthLabel = api.health_label ?? api.label;
  const overallRisk = api.overall_risk ?? api.risk_level;
  return {
    status: healthLabel,
    score: api.score,
    rawScore: api.raw_score,
    primaryDriver: api.primary_driver,
    totalValue: api.total_value,
    changePercent: api.todays_change_pct,
    riskLevel: overallRisk,
    downsideExposurePct: api.downside_exposure_pct,
    riskLabel: api.risk_sublabel,
    diversificationScore: api.diversification_score,
    diversificationLabel: api.diversification_label,
    totalHoldings: api.total_holdings,
  };
}

export function mapToMarketIntelligence(
  res: DashboardNewsResponse,
): MarketIntelligence {
  return {
    news: res.items.map((item) => ({
      id: item.id,
      sentiment: _mapNewsSentiment(item.sentiment, item.tone),
      title: item.headline,
      source: item.source,
      timeAgo: item.time_ago,
    })),
  };
}

/**
 * Returns [featured, ...compactList] — first item is used as the featured hero
 * card in TopPerformersSection; the rest are compact rows.
 */
export function mapToTopPerformers(res: DashboardStocksResponse): TopPerformer[] {
  const mapItem = (item: ApiTopPerformerStock, isFeatured: boolean): TopPerformer => ({
    ticker: item.symbol,
    company: item.name,
    sector: item.industry,
    price: item.current_price,
    priceUpdatedAt: item.price_updated_at ?? null,
    changePercent: item.change_pct_today,
    currency: "Rs.",
    signal: _mapSignal(item.signal_action),
    rsi: Math.round(item.rsi14),
    ...(isFeatured && {
      forecast: item.forecast_change_pct,
      signalLabel: _formatSignalLabel(item.signal_action),
      sentiment: _mapConfidence(item.signal_confidence),
    }),
  });

  const featured = mapItem(res.top_performers.featured, true);
  const list = res.top_performers.list.slice(0, 4).map((s) => mapItem(s, false));
  return [featured, ...list];
}

export function mapToRisingStars(
  res: DashboardStocksResponse,
  limit?: number,
): RisingStar[] {
  const stocks =
    limit != null
      ? res.rising_stars.stocks.slice(0, limit)
      : res.rising_stars.stocks;

  return stocks.map((s) => ({
    ticker: s.symbol,
    company: s.name,
    sector: s.industry,
    price: s.current_price,
    priceUpdatedAt: s.price_updated_at ?? null,
    changePercent: s.change_pct_today,
    currency: "Rs.",
    signal: _mapSignal(s.action),
    signalLabel: _formatSignalLabel(s.action),
    signalStrength: _mapSignalStrength(s.action),
    forecast90d: s.forecast_change_pct,
    sentimentLabel: s.health_label.toUpperCase(),
    riskLabel:
      s.forecast_confidence >= 0.96 ? "LOW RISK"
      : s.forecast_confidence >= 0.93 ? "MED RISK"
      : "HIGH RISK",
  }));
}

export function mapToAIPick(res: DashboardStocksResponse): AIPickStock | null {
  const p = res.ai_pick;
  // ai_pick is null when the backend has no qualifying pick for the day.
  if (!p) return null;
  return {
    ticker: p.symbol,
    companyName: p.symbol,
    sector: p.industry,
    price: p.current_price,
    priceUpdatedAt: p.price_updated_at ?? null,
    changePercent: p.change_pct_today,
    currency: "Rs.",
    forecast: p.forecast_change_pct,
    signal: _mapSignal(p.signal_action),
    rsi: Math.round(p.rsi14),
    description: p.reason,
    badge: "TOP PICK",
  };
}

export function mapToMarketMood(res: DashboardStocksResponse): MarketMood {
  const m = res.market_mood;
  const total = m.total || 1;

  const newsSentimentPct =
    m.news_sentiment === "Positive"
      ? Math.round((m.buy_count / total) * 100)
      : m.news_sentiment === "Negative"
        ? Math.round((m.sell_count / total) * 100)
        : Math.round((m.hold_count / total) * 100);

  return {
    sentiment: _mapMoodLabel(m.mood_label),
    score: m.buy_count,
    totalStocks: m.total,
    caption: `PSX market in ${m.mood_label} mode today`,
    bullCount: m.buy_count,
    neutralCount: m.hold_count,
    bearCount: m.sell_count,
    buySignals: res.market_summary.buy,
    holdSignals: res.market_summary.hold,
    sellSignals: res.market_summary.sell,
    newsSentiment: (m.news_sentiment as NewsSentimentType) ?? "Neutral",
    newsSentimentPercent: newsSentimentPct,
    confidenceIndex: Math.round(m.confidence_index),
    hottestSector: m.hottest_sector,
    updatedAt: _formatPKTTime(res.generated_at),
  };
}

export function mapToSectors(res: DashboardStocksResponse): SectorItem[] {
  return res.sector_performance.sectors
    .filter((s) => s.buy_count + s.hold_count + s.sell_count > 0)
    .slice(0, 8)
    .map((s, idx) => ({
      id: String(idx + 1),
      name: s.sector,
      changePercent: s.avg_forecast_pct,
      label: _mapHealthToSectorLabel(s.health_label),
      stockCount: s.stock_count,
      avgForecast: s.avg_forecast_pct,
      buyCount: s.buy_count,
      holdCount: s.hold_count,
      sellCount: s.sell_count,
      sentiment: _mapHealthToSentiment(s.health_label),
      isHottest: s.is_hottest,
      iconKey: _sectorIconKey(s.sector),
    }));
}

// ─── API Function ─────────────────────────────────────────────────────────────

export type FetchDashboardStocksOptions = {
  /** Filter rising_stars by sector (backend default: all) */
  sector?: string;
  /** Max rising_stars returned (backend default: 10) */
  limit?: number;
};

/** Fetch aggregated dashboard data: stocks, market mood, and portfolio health. */
export async function fetchDashboardStocks(
  token: string,
  options?: FetchDashboardStocksOptions,
): Promise<DashboardStocksResponse> {
  const params = new URLSearchParams();
  if (options?.sector) params.set("sector", options.sector);
  if (options?.limit != null) params.set("limit", String(options.limit));

  const query = params.toString();
  const path = query ? `/dashboard/stocks/?${query}` : "/dashboard/stocks/";
  const response = await authGet(path, token);
  if (!response.ok) throw new Error("Failed to fetch dashboard stocks data");
  return response.json();
}

/** Fetch curated dashboard news (one item per sentiment bucket). */
export async function fetchDashboardNews(
  token: string,
): Promise<DashboardNewsResponse> {
  const response = await authGet("/dashboard/news/", token);
  if (!response.ok) throw new Error("Failed to fetch dashboard news");
  return response.json();
}
