import ScreenHeader from "@/components/ui/ScreenHeader";
import { useAuth } from "@/context/AuthContext";
import {
  fetchPortfolioAnalytics,
  type AnalyticsHolding,
  type PortfolioAnalyticsNewsItem,
  type PortfolioAnalyticsResponse,
  type PortfolioRecommendation,
  type SectorAllocation,
} from "@/services/portfolio";
import { colors, fonts } from "@/styles/global";
import { formatHealthLabel, formatOverallRisk } from "@/utils/portfolioMetrics";
import { useRouter } from "expo-router";
import {
  Briefcase,
  ChevronRight,
  TrendingDown,
  TrendingUp,
} from "lucide-react-native";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Circle, G } from "react-native-svg";

// ─── Formatters ───────────────────────────────────────────────────────────────

const fmtRs = (n: number, dp = 2) =>
  `Rs. ${n.toLocaleString("en-PK", { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;

const fmtRsSigned = (n: number) => {
  const sign = n >= 0 ? "+" : "-";
  return `${sign}${fmtRs(Math.abs(n))}`;
};

const fmtPct = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;

const titleCaseIndustry = (raw: string) =>
  raw
    .toLowerCase()
    .split(/\s+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

const TREND_UP = "#16A34A";
const TREND_DOWN = "#DC2626";

/** Muted dark sector palette — donut segments and bars use the same color per row */
const SECTOR_COLORS = [
  "#114B5F",
  "#5E6A71",
  "#5C5346",
  "#A8B8C0",
  colors.themeDarkest,
  colors.themeDark,
  colors.themeMedium,
  "#4A5F6B",
];

function sectorColor(index: number) {
  return SECTOR_COLORS[index % SECTOR_COLORS.length];
}

type NewsSentiment = "POSITIVE" | "NEUTRAL" | "NEGATIVE";

function mapNewsSentiment(item: PortfolioAnalyticsNewsItem): NewsSentiment {
  const s = item.sentiment.toUpperCase();
  if (s === "EXCELLENT" || item.tone === "positive") return "POSITIVE";
  if (s === "VERY_BAD" || item.tone === "negative") return "NEGATIVE";
  return "NEUTRAL";
}

function recommendationAccent(color: string) {
  if (color === "red") {
    return { bg: "#FEE2E2", text: colors.error, border: colors.error };
  }
  if (color === "green") {
    return { bg: colors.bgTertiaryLight, text: colors.themeDark, border: colors.themeDark };
  }
  return { bg: colors.bgPrimaryLight, text: colors.primary, border: colors.themeMedium };
}

/** How urgent FinMate thinks this recommendation is (not price high/low). */
function recommendationPriorityMeta(severity: string): {
  level: string;
  hint: string;
} {
  const level = severity.toUpperCase();
  if (level === "HIGH") {
    return {
      level,
      hint: "Needs attention soon",
    };
  }
  if (level === "MEDIUM") {
    return {
      level,
      hint: "Review when you can",
    };
  }
  return {
    level: level === "LOW" ? "LOW" : severity,
    hint: "Monitor — no urgent action",
  };
}

function holdingToInsightParams(holding: AnalyticsHolding) {
  return {
    ticker: holding.symbol,
    symbol_id: holding.symbol_id,
    company_name: holding.name,
    sector: holding.industry,
    close: String(holding.current_price),
    change_pct: String(holding.todays_change_pct),
    signal: holding.action ?? "",
    signal_label: holding.action ?? "",
    health_display: holding.health_label ?? "",
    confidence_display: holding.signal_confidence ?? "",
    rsi14: holding.rsi14 != null ? String(holding.rsi14) : "",
  };
}

function recommendationToInsightParams(rec: PortfolioRecommendation) {
  return {
    ticker: rec.symbol,
    company_name: rec.name,
    sector: "",
    close: "",
    change_pct: String(rec.pnl_pct),
    signal: "",
    signal_label: rec.label,
    health_display: "",
    confidence_display: "",
    rsi14: "",
  };
}

// ─── Donut chart ──────────────────────────────────────────────────────────────

type DonutSegment = { label: string; percent: number; color: string };

function SectorDonut({
  data,
  centerLabel,
  centerSub,
}: {
  data: DonutSegment[];
  centerLabel: string;
  centerSub: string;
}) {
  const SIZE = 140;
  const STROKE = 14;
  const radius = (SIZE - STROKE) / 2;
  const circumference = 2 * Math.PI * radius;
  const GAP = 3;

  let offset = 0;
  const segments = data.map((seg) => {
    const segLength = (seg.percent / 100) * circumference - GAP;
    const circle = { ...seg, segLength, offset };
    offset += (seg.percent / 100) * circumference;
    return circle;
  });

  return (
    <View style={styles.donutWrap}>
      <Svg width={SIZE} height={SIZE}>
        <G rotation="-90" origin={`${SIZE / 2}, ${SIZE / 2}`}>
          {segments.map((seg) => (
            <Circle
              key={seg.label}
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={radius}
              stroke={seg.color}
              strokeWidth={STROKE}
              fill="none"
              strokeDasharray={`${seg.segLength} ${circumference - seg.segLength}`}
              strokeDashoffset={-seg.offset}
              strokeLinecap="round"
            />
          ))}
        </G>
      </Svg>
      <View style={styles.donutLabel}>
        <Text style={styles.donutTotal}>{centerLabel}</Text>
        <Text style={styles.donutAssets}>{centerSub}</Text>
      </View>
    </View>
  );
}

// ─── Sections ─────────────────────────────────────────────────────────────────

function PortfolioSummaryCard({
  summary,
}: {
  summary: NonNullable<PortfolioAnalyticsResponse["summary"]>;
}) {
  const pnlUp = summary.total_unrealized_pnl >= 0;
  const todayUp = summary.todays_total_pct >= 0;
  const pnlTint = pnlUp ? TREND_UP : TREND_DOWN;
  const todayTint = todayUp ? TREND_UP : TREND_DOWN;
  const PnlIcon = pnlUp ? TrendingUp : TrendingDown;
  const TodayIcon = todayUp ? TrendingUp : TrendingDown;

  return (
    <View style={styles.summaryCard}>
      <Text style={styles.summaryEyebrow}>Total Portfolio Value</Text>
      <Text style={styles.summaryValue}>{fmtRs(summary.total_portfolio_value)}</Text>
      <View style={styles.summaryDivider} />
      <View style={styles.summaryBottom}>
        <View style={styles.summaryCol}>
          <Text style={styles.summaryColLabel}>Cost Basis</Text>
          <Text style={styles.summaryColValue}>{fmtRs(summary.total_cost_basis)}</Text>
        </View>
        <View style={styles.summaryCol}>
          <Text style={styles.summaryColLabel}>Unrealized P&L</Text>
          <View style={styles.trendInline}>
            <Text style={[styles.summaryColValue, { color: pnlTint }]}>
              {fmtRsSigned(summary.total_unrealized_pnl)}
            </Text>
          </View>
          <View style={styles.trendInline}>
            <PnlIcon size={12} color={pnlTint} strokeWidth={2.5} />
            <Text style={[styles.summaryColPct, { color: pnlTint }]}>
              {fmtPct(summary.total_pnl_pct)}
            </Text>
          </View>
        </View>
      </View>
      <View style={styles.summaryTodayRow}>
        <TodayIcon size={14} color={todayTint} strokeWidth={2.5} />
        <Text style={[styles.summaryToday, { color: todayTint }]}>
          {fmtPct(summary.todays_total_pct)} ({fmtRsSigned(summary.todays_total_change)}) Today
        </Text>
      </View>
    </View>
  );
}

function HealthCard({ health }: { health: NonNullable<PortfolioAnalyticsResponse["health"]> }) {
  const score = Math.max(0, Math.min(100, health.score));

  return (
    <View style={styles.healthCard}>
      <View style={styles.healthTop}>
        <Text style={styles.healthTitle}>Portfolio Health</Text>
        <View style={styles.healthBadge}>
          <Text style={styles.healthBadgeText}>{formatHealthLabel(health.label)}</Text>
        </View>
      </View>
      <View style={styles.healthProgressTrack}>
        <View style={[styles.healthProgressFill, { flex: score }]} />
        <View style={{ flex: 100 - score }} />
      </View>
      <View style={styles.healthMetaRow}>
        <Text style={styles.healthMetaText}>
          Score: <Text style={styles.healthMetaBold}>{health.score}/100</Text>
        </Text>
        <Text style={styles.healthMetaText}>
          Driver: <Text style={styles.healthMetaBold}>{health.primary_driver}</Text>
        </Text>
      </View>
    </View>
  );
}

function SectorAllocationCard({
  sectors,
  totalHoldings,
}: {
  sectors: SectorAllocation[];
  totalHoldings: number;
}) {
  const donutData: DonutSegment[] = sectors.map((s, i) => ({
    label: s.industry,
    percent: s.weight_pct,
    color: sectorColor(i),
  }));

  return (
    <View style={styles.card}>
      <Text style={[styles.cardTitle, styles.cardTitleSpaced]}>Sector Allocation</Text>
      {sectors.length === 0 ? (
        <Text style={styles.muted}>No sector data yet.</Text>
      ) : (
        <>
          <SectorDonut
            data={donutData}
            centerLabel="TOTAL"
            centerSub={`${totalHoldings} ${totalHoldings === 1 ? "Asset" : "Assets"}`}
          />
          <View style={styles.sectorList}>
            {sectors.map((s, i) => (
              <View key={s.industry} style={styles.sectorBlock}>
                <View style={styles.sectorRow}>
                  <View
                    style={[styles.legendDot, { backgroundColor: sectorColor(i) }]}
                  />
                  <Text style={styles.sectorName}>{titleCaseIndustry(s.industry)}</Text>
                  <Text style={styles.sectorPct}>{s.weight_pct.toFixed(1)}%</Text>
                </View>
                <View style={styles.sectorBarTrack}>
                  <View
                    style={[
                      styles.sectorBarFill,
                      {
                        width: `${Math.min(100, s.weight_pct)}%`,
                        backgroundColor: sectorColor(i),
                      },
                    ]}
                  />
                </View>
              </View>
            ))}
          </View>
        </>
      )}
    </View>
  );
}

function RecommendationCard({
  rec,
  onPress,
}: {
  rec: PortfolioRecommendation;
  onPress: () => void;
}) {
  const accent = recommendationAccent(rec.color);
  const priority = recommendationPriorityMeta(rec.severity);
  const pnlUp = rec.pnl_pct >= 0;
  const pnlTint = pnlUp ? TREND_UP : TREND_DOWN;
  const PnlIcon = pnlUp ? TrendingUp : TrendingDown;

  return (
    <Pressable
      style={({ pressed }) => [styles.recCard, pressed && styles.recCardPressed]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${rec.symbol}, ${rec.label}, ${priority.level} priority`}
      accessibilityHint="Opens stock insight"
    >
      <View style={[styles.recAccent, { backgroundColor: accent.border }]} />
      <View style={styles.recInner}>
        <View style={styles.recHeader}>
          <View style={styles.recTitleBlock}>
            <Text style={styles.recTicker}>{rec.symbol}</Text>
            <Text style={styles.recName} numberOfLines={1}>
              {rec.name}
            </Text>
          </View>
          <View style={styles.priorityBlock}>
            <Text style={styles.priorityCaption}>Priority</Text>
            <View
              style={[
                styles.severityPill,
                { backgroundColor: accent.bg, borderColor: accent.border },
              ]}
            >
              <Text style={[styles.severityText, { color: accent.text }]}>
                {priority.level}
              </Text>
            </View>
            <Text style={styles.priorityHint} numberOfLines={2}>
              {priority.hint}
            </Text>
          </View>
          <ChevronRight size={18} color={colors.mutedText} strokeWidth={2} />
        </View>

        <Text style={styles.recLabel}>{rec.label}</Text>

        <View style={styles.recStatsRow}>
          <View style={styles.recStat}>
            <Text style={styles.recStatLabel}>P&L</Text>
            <View style={styles.trendInline}>
              <PnlIcon size={13} color={pnlTint} strokeWidth={2.5} />
              <Text style={[styles.recStatValue, { color: pnlTint }]}>
                {fmtPct(rec.pnl_pct)}
              </Text>
            </View>
          </View>
          <View style={styles.recStatDivider} />
          <View style={styles.recStat}>
            <Text style={styles.recStatLabel}>Weight</Text>
            <Text style={styles.recStatValue}>{rec.position_weight.toFixed(1)}%</Text>
          </View>
          <View style={styles.recStatDivider} />
          <View style={styles.recStat}>
            <Text style={styles.recStatLabel}>Value</Text>
            <Text style={styles.recStatValue}>{fmtRs(rec.current_value, 0)}</Text>
          </View>
        </View>
      </View>
    </Pressable>
  );
}

function PortfolioRecommendationsSection({
  items,
  holdingsBySymbol,
  onOpenStock,
}: {
  items: PortfolioRecommendation[];
  holdingsBySymbol: Map<string, AnalyticsHolding>;
  onOpenStock: (rec: PortfolioRecommendation, holding?: AnalyticsHolding) => void;
}) {
  if (items.length === 0) return null;

  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Portfolio Recommendations</Text>
      <Text style={styles.sectionSub}>
        Tap a card for stock insight. Priority (HIGH / MEDIUM / LOW) is how urgent the
        action is—not the stock price.
      </Text>
      {items.map((rec) => (
        <RecommendationCard
          key={rec.symbol}
          rec={rec}
          onPress={() => onOpenStock(rec, holdingsBySymbol.get(rec.symbol))}
        />
      ))}
    </View>
  );
}

function RiskProfileCard({
  risk,
}: {
  risk: NonNullable<PortfolioAnalyticsResponse["risk"]>;
}) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Risk Profile</Text>
      <View style={styles.riskRow}>
        <View style={styles.riskCol}>
          <Text style={styles.riskLabel}>Overall Risk</Text>
          <Text style={styles.riskValue}>{formatOverallRisk(risk.overall_risk)}</Text>
        </View>
        <View style={styles.riskCol}>
          <Text style={styles.riskLabel}>Weighted Volatility</Text>
          <Text style={styles.riskValue}>{risk.weighted_volatility.toFixed(4)}</Text>
        </View>
      </View>
    </View>
  );
}

function SentimentBadge({ sentiment }: { sentiment: NewsSentiment }) {
  const config = {
    POSITIVE: { color: "#16A34A", bg: "#DCFCE7", label: "POSITIVE" },
    NEUTRAL: { color: "#D97706", bg: "#FEF3C7", label: "NEUTRAL" },
    NEGATIVE: { color: "#DC2626", bg: "#FEE2E2", label: "NEGATIVE" },
  }[sentiment];

  return (
    <View style={[styles.sentimentBadge, { backgroundColor: config.bg }]}>
      <Text style={[styles.sentimentText, { color: config.color }]}>{config.label}</Text>
    </View>
  );
}

function MarketIntelligenceSection({
  items,
  onViewAllPress,
}: {
  items: PortfolioAnalyticsNewsItem[];
  onViewAllPress?: () => void;
}) {
  if (items.length === 0) return null;

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeaderRow}>
        <Text style={styles.sectionTitle}>Market Intelligence</Text>
        <Pressable style={styles.viewAllBtn} hitSlop={8} onPress={onViewAllPress}>
          <Text style={styles.viewAllText}>View All News</Text>
          <ChevronRight size={13} color={colors.primary} strokeWidth={2.2} />
        </Pressable>
      </View>
      {items.map((item) => (
        <View key={item.id} style={styles.newsCard}>
          <SentimentBadge sentiment={mapNewsSentiment(item)} />
          <Text style={styles.newsTitle} numberOfLines={3}>
            {item.headline}
          </Text>
          <Text style={styles.newsMeta}>
            {item.source} <Text style={styles.newsTime}>{item.time_ago}</Text>
          </Text>
        </View>
      ))}
    </View>
  );
}

function EmptyPortfolio() {
  const router = useRouter();

  return (
    <View style={styles.emptyState}>
      <View style={styles.emptyIcon}>
        <Briefcase size={28} color={colors.primary} strokeWidth={1.8} />
      </View>
      <Text style={styles.emptyTitle}>No holdings yet</Text>
      <Text style={styles.emptySub}>
        Add PSX stocks to see portfolio value, health, allocation, and insights.
      </Text>
      <Pressable style={styles.emptyBtn} onPress={() => router.push("/manage-portfolio")}>
        <Text style={styles.emptyBtnText}>Manage Portfolio</Text>
        <ChevronRight size={16} color={colors.background} strokeWidth={2.2} />
      </Pressable>
    </View>
  );
}

// ─── Screen ───────────────────────────────────────────────────────────────────

export default function PortfolioScreen() {
  const router = useRouter();
  const { token } = useAuth();
  const [data, setData] = useState<PortfolioAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (isRefresh = false) => {
      if (!token) return;
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      setError(null);
      try {
        const res = await fetchPortfolioAnalytics(token);
        setData(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load portfolio.");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [token],
  );

  useEffect(() => {
    load();
  }, [load]);

  const hasHoldings = data?.has_holdings && (data.summary?.total_holdings ?? 0) > 0;
  const recommendations = data?.recommendations?.recommendations ?? [];
  const newsItems = data?.news?.items ?? [];

  const holdingsBySymbol = new Map<string, AnalyticsHolding>();
  for (const h of data?.holdings?.all_holdings ?? []) {
    holdingsBySymbol.set(h.symbol, h);
  }

  const openRecommendationInsight = useCallback(
    (rec: PortfolioRecommendation, holding?: AnalyticsHolding) => {
      router.push({
        pathname: "/stock-insight/[ticker]",
        params: holding
          ? holdingToInsightParams(holding)
          : recommendationToInsightParams(rec),
      });
    },
    [router],
  );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScreenHeader />
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => load(true)}
            tintColor={colors.primary}
          />
        }
      >
        {loading && !data ? (
          <ActivityIndicator size="large" color={colors.primary} style={styles.loader} />
        ) : error && !data ? (
          <Text style={styles.errorText}>{error}</Text>
        ) : !hasHoldings ? (
          <EmptyPortfolio />
        ) : data?.summary ? (
          <>
            <PortfolioSummaryCard summary={data.summary} />
            {data.health ? <HealthCard health={data.health} /> : null}
            {data.allocation ? (
              <SectorAllocationCard
                sectors={data.allocation.sectors}
                totalHoldings={data.allocation.total_holdings}
              />
            ) : null}
            <PortfolioRecommendationsSection
              items={recommendations}
              holdingsBySymbol={holdingsBySymbol}
              onOpenStock={openRecommendationInsight}
            />
            {data.risk ? <RiskProfileCard risk={data.risk} /> : null}
            <MarketIntelligenceSection
              items={newsItems}
              onViewAllPress={() => router.push("/(tabs)/news")}
            />
          </>
        ) : (
          <Text style={styles.errorText}>{error ?? "Unable to load portfolio data."}</Text>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scroll: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 100,
    gap: 14,
  },
  loader: { marginTop: 48 },
  errorText: {
    fontFamily: fonts.body,
    fontSize: 14,
    color: colors.mutedText,
    textAlign: "center",
    marginTop: 32,
  },

  summaryCard: {
    backgroundColor: colors.background,
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  summaryEyebrow: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  summaryValue: {
    fontFamily: fonts.heading,
    fontSize: 30,
    color: colors.text,
    letterSpacing: -0.8,
    lineHeight: 36,
    marginTop: 4,
  },
  summaryDivider: {
    height: 1,
    backgroundColor: colors.borderLight,
    marginVertical: 14,
  },
  summaryBottom: {
    flexDirection: "row",
    gap: 16,
  },
  summaryCol: {
    flex: 1,
    gap: 4,
  },
  summaryColLabel: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
  },
  summaryColValue: {
    fontFamily: fonts.heading,
    fontSize: 16,
    color: colors.text,
    letterSpacing: -0.3,
  },
  summaryColPct: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
  },
  trendInline: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  summaryTodayRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  summaryToday: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    flex: 1,
  },

  healthCard: {
    backgroundColor: colors.primary,
    borderRadius: 16,
    padding: 16,
  },
  healthTitle: {
    fontFamily: fonts.heading,
    fontSize: 16,
    color: colors.background,
    letterSpacing: -0.2,
  },
  healthTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  healthBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
    backgroundColor: "rgba(234, 242, 245, 0.22)",
    borderWidth: 1,
    borderColor: "rgba(234, 242, 245, 0.38)",
  },
  healthBadgeText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 10,
    letterSpacing: 0.6,
    color: colors.background,
  },
  healthProgressTrack: {
    flexDirection: "row",
    height: 8,
    backgroundColor: colors.themeMedium,
    borderRadius: 999,
    overflow: "hidden",
    marginBottom: 12,
  },
  healthProgressFill: {
    height: "100%",
    borderRadius: 999,
    backgroundColor: colors.background,
  },
  healthMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  healthMetaText: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.bgTertiaryLight,
  },
  healthMetaBold: {
    fontFamily: fonts.bodyMedium,
    color: colors.background,
  },

  card: {
    backgroundColor: colors.background,
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  cardTitle: {
    fontFamily: fonts.heading,
    fontSize: 16,
    color: colors.primary,
    letterSpacing: -0.2,
  },
  cardTitleSpaced: {
    marginBottom: 4,
  },

  section: {
    gap: 10,
  },
  sectionTitle: {
    fontFamily: fonts.heading,
    fontSize: 16,
    color: colors.primary,
    letterSpacing: -0.2,
  },
  sectionSub: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: colors.mutedText,
    lineHeight: 16,
    marginTop: -4,
    marginBottom: 4,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 2,
  },
  viewAllBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
  },
  viewAllText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.primary,
  },
  muted: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.mutedText,
    textAlign: "center",
    paddingVertical: 12,
  },

  donutWrap: {
    alignSelf: "center",
    width: 140,
    height: 140,
    justifyContent: "center",
    alignItems: "center",
    marginVertical: 12,
  },
  donutLabel: {
    position: "absolute",
    alignItems: "center",
  },
  donutTotal: {
    fontFamily: fonts.bodyMedium,
    fontSize: 9,
    color: colors.mutedText,
    letterSpacing: 0.6,
  },
  donutAssets: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: colors.text,
    letterSpacing: -0.2,
  },
  sectorList: {
    gap: 12,
    marginTop: 4,
  },
  sectorBlock: {
    gap: 6,
  },
  sectorRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
  },
  sectorName: {
    flex: 1,
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.text,
    paddingRight: 8,
  },
  sectorPct: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.text,
  },
  sectorBarTrack: {
    height: 8,
    backgroundColor: colors.bgSecondaryLight,
    borderRadius: 999,
    overflow: "hidden",
    marginLeft: 16,
  },
  sectorBarFill: {
    height: "100%",
    borderRadius: 999,
  },

  recCard: {
    flexDirection: "row",
    backgroundColor: colors.background,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderLight,
    overflow: "hidden",
    marginBottom: 10,
  },
  recCardPressed: {
    opacity: 0.92,
    backgroundColor: colors.bgLighter,
  },
  recAccent: {
    width: 4,
  },
  recInner: {
    flex: 1,
    padding: 14,
    gap: 10,
  },
  recHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 8,
  },
  priorityBlock: {
    alignItems: "flex-end",
    maxWidth: 108,
    gap: 2,
  },
  priorityCaption: {
    fontFamily: fonts.body,
    fontSize: 9,
    color: colors.mutedText,
    letterSpacing: 0.3,
    textTransform: "uppercase",
  },
  priorityHint: {
    fontFamily: fonts.body,
    fontSize: 9,
    color: colors.mutedText,
    textAlign: "right",
    lineHeight: 12,
  },
  recTitleBlock: {
    flex: 1,
    gap: 2,
  },
  recTicker: {
    fontFamily: fonts.heading,
    fontSize: 16,
    color: colors.text,
    letterSpacing: -0.3,
  },
  severityPill: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
  },
  severityText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 9,
    letterSpacing: 0.5,
  },
  recName: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.textSecondary,
  },
  recLabel: {
    fontFamily: fonts.heading,
    fontSize: 15,
    color: colors.text,
    letterSpacing: -0.25,
    lineHeight: 20,
  },
  recStatsRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.bgLight,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 8,
  },
  recStat: {
    flex: 1,
    alignItems: "center",
    gap: 4,
  },
  recStatDivider: {
    width: 1,
    height: 28,
    backgroundColor: colors.borderLight,
  },
  recStatLabel: {
    fontFamily: fonts.body,
    fontSize: 10,
    color: colors.mutedText,
    textTransform: "uppercase",
    letterSpacing: 0.3,
  },
  recStatValue: {
    fontFamily: fonts.heading,
    fontSize: 13,
    color: colors.text,
    letterSpacing: -0.2,
  },

  riskRow: {
    flexDirection: "row",
    gap: 16,
    marginTop: 14,
  },
  riskCol: {
    flex: 1,
    gap: 6,
  },
  riskLabel: {
    fontFamily: fonts.body,
    fontSize: 10,
    color: colors.mutedText,
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },
  riskValue: {
    fontFamily: fonts.heading,
    fontSize: 15,
    color: colors.primary,
    letterSpacing: -0.2,
  },

  newsCard: {
    backgroundColor: colors.background,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: 8,
  },
  sentimentBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  sentimentText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 10,
    letterSpacing: 0.6,
  },
  newsTitle: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
  },
  newsMeta: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
  },
  newsTime: {
    color: colors.mutedText,
  },

  emptyState: {
    alignItems: "center",
    paddingTop: 48,
    paddingHorizontal: 24,
    gap: 10,
  },
  emptyIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.bgPrimaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 8,
  },
  emptyTitle: {
    fontFamily: fonts.heading,
    fontSize: 18,
    color: colors.text,
  },
  emptySub: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.mutedText,
    textAlign: "center",
    lineHeight: 20,
  },
  emptyBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginTop: 12,
    backgroundColor: colors.primary,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 24,
  },
  emptyBtnText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: colors.background,
  },
});
