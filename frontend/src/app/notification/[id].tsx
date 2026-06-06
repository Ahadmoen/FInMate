import { useAuth } from "@/context/AuthContext";
import {
  buildNotificationTitle,
  fetchNotificationDetail,
  formatNotificationTime,
  markNotificationRead,
  type DigestTickerRow,
  type NewsPayloadItem,
  type NotificationDetail,
  type NotificationPayload,
} from "@/services/alertFeed";
import { colors, fonts } from "@/styles/global";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ChevronLeft } from "lucide-react-native";
import { useCallback, useEffect, useState } from "react";
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

function pctColor(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return colors.mutedText;
  return n >= 0 ? GREEN : RED;
}

async function openNewsLink(url: string | undefined) {
  const trimmed = url?.trim();
  if (!trimmed) return;
  try {
    const canOpen = await Linking.canOpenURL(trimmed);
    if (canOpen) await Linking.openURL(trimmed);
  } catch {
    /* ignore */
  }
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.statRow}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
    </View>
  );
}

function NewsList({ items }: { items: NewsPayloadItem[] }) {
  if (!items.length) return null;
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Recent news</Text>
      {items.map((n, i) => (
        <Pressable
          key={`${n.headline ?? i}-${i}`}
          style={styles.newsRow}
          onPress={() => openNewsLink(n.link)}
          disabled={!n.link}
        >
          <Text style={[styles.newsHeadline, n.link && styles.newsLink]}>
            {n.headline ?? "News item"}
          </Text>
          {(n.source || n.sentiment) && (
            <Text style={styles.newsMeta}>
              {[n.source, n.sentiment].filter(Boolean).join(" · ")}
            </Text>
          )}
        </Pressable>
      ))}
    </View>
  );
}

function DigestTable({ rows }: { rows: DigestTickerRow[] }) {
  if (!rows.length) return null;
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Stocks in this digest</Text>
      {rows.map((row) => (
        <View key={row.ticker} style={styles.digestRow}>
          <View style={styles.digestHeader}>
            <Text style={styles.digestTicker}>{row.ticker}</Text>
            <Text style={[styles.digestChange, { color: pctColor(row.change_pct ?? null) }]}>
              {fmtPct(row.change_pct)}
            </Text>
          </View>
          <Text style={styles.digestPrice}>
            {fmtRs(row.close)}
            {row.rsi14 != null ? ` · RSI ${row.rsi14.toFixed(1)}` : ""}
          </Text>
          {row.summary ? <Text style={styles.digestSummary}>{row.summary}</Text> : null}
        </View>
      ))}
    </View>
  );
}

function StockDetailBody({
  detail,
  payload,
}: {
  detail: NotificationDetail;
  payload: NotificationPayload;
}) {
  const summary = payload.summary ?? detail.body ?? detail.alert.reason;
  const signalLabel = (payload.signal ?? detail.alert.signal).replace(/_/g, " ");

  return (
    <>
      <View style={styles.heroCard}>
        <Text style={styles.heroTicker}>
          {payload.ticker ?? (detail.alert.ticker !== "DIGEST" ? detail.alert.ticker : "—")}
        </Text>
        <Text style={[styles.heroSignal, { color: signalLabel.includes("SELL") ? RED : GREEN }]}>
          {signalLabel}
        </Text>
        <Text style={styles.heroPrice}>
          {fmtRs(payload.close ?? payload.current)}
          {payload.change_pct != null ? (
            <Text style={{ color: pctColor(payload.change_pct) }}>
              {" "}
              {fmtPct(payload.change_pct)}
            </Text>
          ) : null}
        </Text>
        {payload.confidence ? (
          <Text style={styles.heroMeta}>Confidence: {payload.confidence}</Text>
        ) : null}
      </View>

      {detail.type === "POSITION_ALERT" &&
      (payload.qty != null || payload.avg_buy != null) ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Your position</Text>
          <StatRow label="Quantity" value={payload.qty != null ? String(payload.qty) : "—"} />
          <StatRow label="Avg buy" value={fmtRs(payload.avg_buy)} />
          <StatRow
            label="Unrealised P&L"
            value={
              payload.pnl_pct != null
                ? `${fmtPct(payload.pnl_pct)}${payload.pnl_pkr != null ? ` (${fmtRs(payload.pnl_pkr)})` : ""}`
                : "—"
            }
          />
        </View>
      ) : null}

      <Text style={styles.summary}>{summary}</Text>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Technicals</Text>
        <StatRow label="RSI 14" value={payload.rsi14 != null ? payload.rsi14.toFixed(1) : "—"} />
        <StatRow label="MA 50" value={fmtRs(payload.ma50)} />
        <StatRow label="MA 200" value={fmtRs(payload.ma200)} />
        {payload.volatility20d != null ? (
          <StatRow
            label="Volatility (20d)"
            value={`${(payload.volatility20d * 100).toFixed(1)}%`}
          />
        ) : null}
      </View>

      <NewsList items={payload.news ?? []} />
    </>
  );
}

export default function NotificationDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { token } = useAuth();

  const [detail, setDetail] = useState<NotificationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token || !id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchNotificationDetail(token, id);
      setDetail(data);
      if (data.read_at == null) {
        markNotificationRead(token, id).catch(() => undefined);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load notification.");
    } finally {
      setLoading(false);
    }
  }, [token, id]);

  useEffect(() => {
    load();
  }, [load]);

  const payload = detail?.payload;
  const windowLabel = detail?.window_label ?? payload?.window_label ?? "";

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <Pressable style={styles.backBtn} onPress={() => router.back()} hitSlop={10}>
          <ChevronLeft size={22} color={colors.primary} strokeWidth={2} />
        </Pressable>
        <Text style={styles.headerTitle} numberOfLines={1}>
          Alert detail
        </Text>
        <View style={styles.backBtn} />
      </View>

      {loading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : error || !detail ? (
        <View style={styles.centered}>
          <Text style={styles.errorText}>{error ?? "Notification not found."}</Text>
          <Pressable style={styles.retryBtn} onPress={load}>
            <Text style={styles.retryText}>Try again</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.content}
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.title}>
            {detail.title ||
              buildNotificationTitle(
                detail.type,
                detail.alert.ticker,
                detail.alert.alert_window,
              )}
          </Text>
          <Text style={styles.meta}>
            {formatNotificationTime(detail.created_at)}
            {windowLabel ? ` · ${windowLabel}` : ""}
          </Text>

          {payload && detail.type === "DIGEST" ? (
            <>
              <Text style={styles.summary}>
                {detail.body ||
                  detail.alert.reason ||
                  `Market digest with ${payload.count ?? payload.tickers?.length ?? 0} strong-buy moves.`}
              </Text>
              <DigestTable rows={payload.tickers ?? []} />
            </>
          ) : payload ? (
            <StockDetailBody detail={detail} payload={payload} />
          ) : (
            <Text style={styles.summary}>{detail.body || detail.alert.reason}</Text>
          )}

          {!payload && detail.alert.symbols?.length > 0 && detail.type === "DIGEST" ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Symbols</Text>
              <Text style={styles.symbolsList}>{detail.alert.symbols.join(", ")}</Text>
            </View>
          ) : null}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  backBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    flex: 1,
    fontFamily: fonts.heading,
    fontSize: 18,
    color: colors.text,
    textAlign: "center",
  },
  scroll: { flex: 1 },
  content: {
    paddingHorizontal: 20,
    paddingBottom: 32,
    paddingTop: 16,
  },
  title: {
    fontFamily: fonts.heading,
    fontSize: 20,
    color: colors.text,
    lineHeight: 26,
    marginBottom: 6,
  },
  meta: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
    marginBottom: 16,
  },
  summary: {
    fontFamily: fonts.body,
    fontSize: 15,
    color: colors.textSecondary,
    lineHeight: 22,
    marginBottom: 16,
  },
  heroCard: {
    backgroundColor: colors.bgLight,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderLight,
    padding: 16,
    marginBottom: 16,
  },
  heroTicker: {
    fontFamily: fonts.heading,
    fontSize: 24,
    color: colors.text,
  },
  heroSignal: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    marginTop: 4,
  },
  heroPrice: {
    fontFamily: fonts.body,
    fontSize: 15,
    color: colors.text,
    marginTop: 8,
  },
  heroMeta: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
    marginTop: 6,
  },
  section: {
    marginBottom: 16,
    padding: 14,
    backgroundColor: colors.bgLighter,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  sectionTitle: {
    fontFamily: fonts.heading,
    fontSize: 13,
    color: colors.mutedText,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 10,
  },
  statRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
  },
  statLabel: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.mutedText,
  },
  statValue: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.text,
  },
  newsRow: {
    marginBottom: 12,
  },
  newsHeadline: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
  },
  newsLink: {
    color: colors.primary,
  },
  newsMeta: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
    marginTop: 2,
  },
  digestRow: {
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
    paddingVertical: 10,
  },
  digestHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  digestTicker: {
    fontFamily: fonts.heading,
    fontSize: 15,
    color: colors.text,
  },
  digestChange: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
  },
  digestPrice: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
    marginTop: 2,
  },
  digestSummary: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 6,
    lineHeight: 18,
  },
  symbolsList: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  errorText: {
    fontFamily: fonts.body,
    fontSize: 14,
    color: colors.error,
    textAlign: "center",
    marginBottom: 12,
  },
  retryBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: colors.primary,
  },
  retryText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: "#FFFFFF",
  },
});
