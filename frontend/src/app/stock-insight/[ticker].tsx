import { useAuth } from "@/context/AuthContext";
import {
  fetchInsightDetail,
  fetchInsightNews,
  type InsightCardParams,
  type InsightNewsItem,
  type InsightStockDetail,
} from "@/services/insights";
import LivePriceUpdated from "@/components/ui/LivePriceUpdated";
import { colors, fonts } from "@/styles/global";
import { resolveLiveChangePct } from "@/utils/livePrice";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ChevronLeft } from "lucide-react-native";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ActivityIndicator,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

const BG = "#FFFFFF";
const GREEN = "#16A34A";
const RED = "#DC2626";

function fmtRs(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return `Rs. ${n.toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}

async function openNewsLink(url: string | undefined) {
  const trimmed = url?.trim();
  if (!trimmed) return;
  try {
    const canOpen = await Linking.canOpenURL(trimmed);
    if (canOpen) await Linking.openURL(trimmed);
  } catch {
    /* ignore — invalid or blocked URL */
  }
}

export default function StockInsightDetailScreen() {
  const router = useRouter();
  const { token } = useAuth();
  const params = useLocalSearchParams<InsightCardParams>();

  const ticker = params.ticker ?? "";
  const preview = useMemo(
    () => ({
      company_name: params.company_name ?? ticker,
      sector: params.sector ?? "",
      close: params.close ? parseFloat(params.close) : null,
      change_pct:
        params.change_pct != null && String(params.change_pct).trim() !== ""
          ? parseFloat(String(params.change_pct))
          : null,
      signal_label: params.signal_label ?? "",
      health_display: params.health_display ?? "",
      confidence_display: params.confidence_display ?? "",
      rsi14: params.rsi14 ? parseFloat(params.rsi14) : null,
    }),
    [params, ticker],
  );

  const [detail, setDetail] = useState<InsightStockDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(true);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [news, setNews] = useState<InsightNewsItem[]>([]);
  const [newsTotal, setNewsTotal] = useState(0);
  const [newsHasMore, setNewsHasMore] = useState(false);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsLoadingMore, setNewsLoadingMore] = useState(false);

  useEffect(() => {
    if (!token || !ticker) return;
    setDetailLoading(true);
    setDetailError(null);
    fetchInsightDetail(token, ticker)
      .then(setDetail)
      .catch((e) => setDetailError(e instanceof Error ? e.message : "Failed to load detail."))
      .finally(() => setDetailLoading(false));
  }, [token, ticker]);

  const loadNews = useCallback(
    async (offset: number, append: boolean) => {
      if (!token || !ticker) return;
      if (append) setNewsLoadingMore(true);
      else setNewsLoading(true);
      try {
        const res = await fetchInsightNews(token, ticker, offset, 5);
        setNews((prev) => (append ? [...prev, ...res.items] : res.items));
        setNewsTotal(res.total);
        setNewsHasMore(res.has_more);
      } finally {
        setNewsLoading(false);
        setNewsLoadingMore(false);
      }
    },
    [token, ticker],
  );

  useEffect(() => {
    loadNews(0, false);
  }, [loadNews]);

  const live = detail?.live;
  const signal = detail?.signal;
  const forecast = detail?.forecast;

  const price = live?.close ?? preview.close;
  const changePct = resolveLiveChangePct(live, preview.change_pct);
  const pos = (changePct ?? 0) >= 0;

  const contributions = signal?.contributions ?? {};
  const contribEntries = Object.entries(contributions).sort((a, b) => b[1] - a[1]);
  const contribMax = contribEntries.length ? Math.max(...contribEntries.map(([, v]) => v)) : 1;

  const companyName = detail?.company_name ?? preview.company_name;
  const sectorLabel = (detail?.sector || preview.sector).toUpperCase();

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <View style={styles.topBar}>
          <Pressable style={styles.backBtn} onPress={() => router.back()} hitSlop={8}>
            <ChevronLeft size={22} color={colors.primary} strokeWidth={2.2} />
          </Pressable>
          <View style={styles.headerTitleWrap}>
            <Text style={styles.topCompany} numberOfLines={2}>
              {companyName}
            </Text>
            <Text style={styles.topTicker}>{ticker}</Text>
          </View>
          <View style={styles.backBtn} />
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.heroCard}>
          {sectorLabel ? <Text style={styles.sector}>{sectorLabel}</Text> : null}
          <Text style={styles.heroPrice}>{fmtRs(price)}</Text>
          <Text style={[styles.heroChange, { color: pos ? "#86EFAC" : "#FCA5A5" }]}>
            {changePct != null ? `${fmtPct(changePct)} today` : "—"}
          </Text>
          <View style={styles.heroPills}>
            {(signal?.signal_label ?? preview.signal_label) ? (
              <View style={[styles.pill, styles.pillOnPrimary]}>
                <Text style={[styles.pillText, styles.pillTextOnPrimary]}>
                  {signal?.signal_label ?? preview.signal_label}
                </Text>
              </View>
            ) : null}
            {(signal?.health_display ?? preview.health_display) ? (
              <View style={[styles.pill, styles.pillOnPrimary]}>
                <Text style={[styles.pillText, styles.pillTextOnPrimary]}>
                  HEALTH: {signal?.health_display ?? preview.health_display}
                </Text>
              </View>
            ) : null}
            {(signal?.confidence_display ?? preview.confidence_display) ? (
              <View style={[styles.pill, styles.pillOnPrimary]}>
                <Text style={[styles.pillText, styles.pillTextOnPrimary]}>
                  {signal?.confidence_display ?? preview.confidence_display}
                </Text>
              </View>
            ) : null}
          </View>
          <LivePriceUpdated at={live?.as_of ?? null} variant="onPrimary" />
        </View>

        {detailLoading ? (
          <ActivityIndicator color={colors.primary} style={styles.sectionLoader} />
        ) : detailError ? (
          <Text style={styles.errorText}>{detailError}</Text>
        ) : null}

        <SectionCard title="Live market">
          <View style={styles.metricsGrid}>
            <Metric label="Open" value={fmtRs(live?.open_price)} />
            <Metric label="High" value={fmtRs(live?.high)} />
            <Metric label="Low" value={fmtRs(live?.low)} />
            <Metric label="Volume" value={live?.volume?.toLocaleString() ?? "—"} />
            <Metric label="RSI (14)" value={live?.rsi14?.toFixed(1) ?? preview.rsi14?.toFixed(1) ?? "—"} />
            <Metric label="Volatility" value={live?.volatility20d?.toFixed(2) ?? "—"} />
            <Metric label="MA50" value={fmtRs(live?.ma50)} />
            <Metric label="MA200" value={fmtRs(live?.ma200)} />
            <Metric label="EPS" value={live?.eps != null ? String(live.eps) : "—"} />
            <Metric label="Vol. ratio" value={live?.volume_ratio?.toFixed(2) ?? "—"} />
          </View>
          <LivePriceUpdated at={live?.as_of ?? null} />
        </SectionCard>

        <SectionCard title="Model prediction">
          {forecast ? (
            <>
              <Row label="Direction" value={forecast.direction} />
              <Row label="Predicted price" value={fmtRs(forecast.predicted_price)} />
              <Row label="Expected change" value={fmtPct(forecast.expected_change_pct)} />
              <Row
                label="Confidence"
                value={`${(forecast.confidence * 100).toFixed(1)}%`}
              />
            </>
          ) : (
            <Text style={styles.muted}>No forecast available for this symbol.</Text>
          )}
        </SectionCard>

        <SectionCard title="Signal & drivers">
          {signal ? (
            <>
              <Row label="Action" value={signal.action} />
              <Row label="Blended score" value={signal.blended_score?.toFixed(3) ?? "—"} />
              <Row label="Forecast score" value={signal.forecast_score.toFixed(3)} />
              <Row label="Sentiment score" value={signal.sentiment_score.toFixed(3)} />
              {signal.horizon != null ? <Row label="Horizon" value={`${signal.horizon}d`} /> : null}
              {signal.reason ? (
                <Text style={styles.reason}>{signal.reason}</Text>
              ) : null}
              {contribEntries.length > 0 ? (
                <View style={styles.contribWrap}>
                  <Text style={styles.contribTitle}>Prediction drivers</Text>
                  {contribEntries.map(([name, pct]) => (
                    <View key={name} style={styles.contribRow}>
                      <Text style={styles.contribLabel}>{name}</Text>
                      <View style={styles.contribBarBg}>
                        <View
                          style={[
                            styles.contribBarFill,
                            { width: `${Math.min(100, (pct / contribMax) * 100)}%` },
                          ]}
                        />
                      </View>
                      <Text style={styles.contribPct}>{pct.toFixed(1)}%</Text>
                    </View>
                  ))}
                </View>
              ) : null}
            </>
          ) : (
            <Text style={styles.muted}>No signal data available.</Text>
          )}
        </SectionCard>

        <SectionCard title={`News (${newsTotal})`}>
          {newsLoading && news.length === 0 ? (
            <ActivityIndicator color={colors.primary} style={styles.sectionLoader} />
          ) : (
            <View style={styles.newsList}>
              {news.map((item) => (
                <View
                  key={item.id}
                  style={[
                    styles.newsCard,
                    item.tone === "positive" && styles.newsPositive,
                    item.tone === "negative" && styles.newsNegative,
                  ]}
                >
                  <View style={styles.newsTop}>
                    <Text
                      style={[
                        styles.newsTone,
                        item.tone === "positive" && { color: GREEN },
                        item.tone === "negative" && { color: RED },
                      ]}
                    >
                      {item.sentiment}
                    </Text>
                    <Text style={styles.newsTime}>{item.time_ago}</Text>
                  </View>
                  {item.link?.trim() ? (
                    <Pressable onPress={() => openNewsLink(item.link)} hitSlop={4}>
                      <Text style={[styles.newsHeadline, styles.newsHeadlineLink]}>
                        {item.headline}
                      </Text>
                    </Pressable>
                  ) : (
                    <Text style={styles.newsHeadline}>{item.headline}</Text>
                  )}
                  <Text style={styles.newsSource}>{item.source}</Text>
                </View>
              ))}
              {news.length === 0 && !newsLoading ? (
                <Text style={styles.muted}>No recent news for this stock.</Text>
              ) : null}
              {newsHasMore ? (
                <Pressable
                  style={styles.loadMoreBtn}
                  onPress={() => loadNews(news.length, true)}
                  disabled={newsLoadingMore}
                >
                  {newsLoadingMore ? (
                    <ActivityIndicator color="#FFFFFF" size="small" />
                  ) : (
                    <Text style={styles.loadMoreText}>Load more</Text>
                  )}
                </Pressable>
              ) : null}
            </View>
          )}
        </SectionCard>
      </ScrollView>
    </SafeAreaView>
  );
}

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <View style={styles.sectionCard}>
      <View style={styles.sectionCardHeader}>
        <Text style={styles.sectionCardHeaderTitle}>{title}</Text>
      </View>
      <View style={styles.sectionCardBody}>{children}</View>
    </View>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  header: {
    backgroundColor: "#FFFFFF",
    borderBottomWidth: 1,
    borderBottomColor: "#E8EEF0",
  },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: "#FFFFFF",
  },
  backBtn: { width: 40, height: 40, alignItems: "center", justifyContent: "center" },
  headerTitleWrap: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 8,
  },
  topCompany: {
    fontFamily: fonts.heading,
    fontSize: 15,
    color: colors.text,
    letterSpacing: -0.3,
    textAlign: "center",
  },
  topTicker: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.primary,
    letterSpacing: 0.4,
    marginTop: 2,
    textAlign: "center",
  },
  scroll: { padding: 16, paddingBottom: 40 },
  heroCard: {
    backgroundColor: colors.primary,
    borderRadius: 16,
    padding: 18,
    marginBottom: 16,
  },
  sector: {
    fontFamily: fonts.body,
    fontSize: 10,
    color: "rgba(255, 255, 255, 0.72)",
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  heroPrice: {
    fontFamily: fonts.heading,
    fontSize: 28,
    color: colors.background,
    letterSpacing: -0.5,
  },
  heroChange: { fontFamily: fonts.bodyMedium, fontSize: 14, marginTop: 4 },
  heroPills: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 14 },
  pill: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 10,
  },
  pillOnPrimary: {
    backgroundColor: "rgba(255, 255, 255, 0.18)",
  },
  pillText: { fontFamily: fonts.bodyMedium, fontSize: 10 },
  pillTextOnPrimary: { color: colors.background },
  sectionCard: {
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderLight,
    backgroundColor: colors.background,
    overflow: "hidden",
    marginBottom: 16,
  },
  sectionCardHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: colors.bgPrimaryLight,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  sectionCardHeaderTitle: {
    fontFamily: fonts.heading,
    fontSize: 15,
    color: colors.primary,
    letterSpacing: -0.2,
  },
  sectionCardBody: {
    padding: 14,
    gap: 8,
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  metric: { width: "47%" },
  metricLabel: { fontFamily: fonts.body, fontSize: 11, color: colors.mutedText },
  metricValue: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.text, marginTop: 2 },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  rowLabel: { fontFamily: fonts.body, fontSize: 12, color: colors.mutedText },
  rowValue: { fontFamily: fonts.bodyMedium, fontSize: 12, color: colors.text },
  reason: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 18,
    marginTop: 8,
    fontStyle: "italic",
  },
  contribWrap: { marginTop: 12, gap: 10 },
  contribTitle: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.primary,
    marginBottom: 4,
  },
  contribRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  contribLabel: { width: 72, fontFamily: fonts.body, fontSize: 11, color: colors.mutedText },
  contribBarBg: {
    flex: 1,
    height: 8,
    backgroundColor: "#E8EEF0",
    borderRadius: 4,
    overflow: "hidden",
  },
  contribBarFill: { height: 8, backgroundColor: colors.primary, borderRadius: 4 },
  contribPct: {
    width: 44,
    textAlign: "right",
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    color: colors.text,
  },
  newsList: { gap: 10 },
  newsCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 12,
    padding: 12,
    borderLeftWidth: 3,
    borderLeftColor: "#D1D5DB",
    borderWidth: 1,
    borderColor: "#E8EEF0",
  },
  newsPositive: { borderLeftColor: GREEN },
  newsNegative: { borderLeftColor: RED },
  newsTop: { flexDirection: "row", justifyContent: "space-between", marginBottom: 6 },
  newsTone: { fontFamily: fonts.bodyMedium, fontSize: 10, color: colors.mutedText },
  newsTime: { fontFamily: fonts.body, fontSize: 10, color: colors.mutedText },
  newsHeadline: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.text,
    lineHeight: 19,
    marginBottom: 4,
  },
  newsHeadlineLink: {
    color: colors.primary,
    textDecorationLine: "underline",
  },
  newsSource: { fontFamily: fonts.body, fontSize: 11, color: colors.mutedText },
  loadMoreBtn: {
    backgroundColor: colors.primary,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 8,
  },
  loadMoreText: {
    fontFamily: fonts.heading,
    fontSize: 13,
    color: "#FFFFFF",
    letterSpacing: 0.5,
  },
  muted: { fontFamily: fonts.body, fontSize: 13, color: colors.mutedText },
  errorText: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: RED,
    marginBottom: 12,
    textAlign: "center",
  },
  sectionLoader: { marginVertical: 16 },
});
