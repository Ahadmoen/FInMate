import LivePriceUpdated from "@/components/ui/LivePriceUpdated";
import type { InsightStockCard as InsightStockCardData } from "@/services/insights";
import { colors, fonts } from "@/styles/global";
import { Heart, TrendingDown, TrendingUp } from "lucide-react-native";
import { Pressable, StyleSheet, Text, View } from "react-native";

const TEAL = "#0E4D53";
const GREEN = "#16A34A";
const RED = "#DC2626";
const ORANGE = "#D97706";

type Props = {
  data: InsightStockCardData;
  onPress: () => void;
  onIconPress?: () => void;
};

function healthColor(display: string | null): string {
  const d = (display ?? "").toUpperCase();
  if (d === "EXCELLENT") return GREEN;
  if (d === "GOOD") return ORANGE;
  if (d === "STABLE") return "#6B7280";
  return RED;
}

function confidenceStyle(display: string | null) {
  const d = (display ?? "").toUpperCase();
  if (d.includes("HIGH")) return { bg: "#DCFCE7", text: GREEN };
  if (d.includes("MED")) return { bg: "#FEF3C7", text: ORANGE };
  return { bg: "#F3F4F6", text: "#6B7280" };
}

function signalColor(signal: string | null): string {
  const s = (signal ?? "").toUpperCase();
  if (s.includes("BUY")) return GREEN;
  if (s.includes("SELL")) return RED;
  return ORANGE;
}

export default function InsightStockCard({ data, onPress, onIconPress }: Props) {
  const pos = (data.change_pct ?? 0) >= 0;
  const changeColor = pos ? GREEN : RED;
  const changeLabel =
    data.change_pct != null
      ? `${pos ? "+" : ""}${data.change_pct.toFixed(2)}%`
      : "—";
  const conf = confidenceStyle(data.confidence_display);
  const sigColor = signalColor(data.signal);
  const dots = data.signal_strength_dots ?? 1;
  const sectorLabel = (data.sector || "—").toUpperCase();

  const openDetail = onIconPress ?? onPress;

  return (
    <View style={styles.card}>
      <Pressable onPress={onPress} style={styles.cardPressable}>
      <View style={styles.topRow}>
        <View style={styles.topLeft}>
          <View style={styles.tickerCircle}>
            <Text style={styles.tickerCircleText} numberOfLines={1}>
              {data.ticker.slice(0, 3)}
            </Text>
          </View>
          <View style={styles.identity}>
            <View style={styles.tickerRow}>
              <Text style={styles.ticker}>{data.ticker}</Text>
              <View style={styles.sectorPill}>
                <Text style={styles.sectorPillText} numberOfLines={1}>
                  {sectorLabel}
                </Text>
              </View>
            </View>
            <Text style={styles.company} numberOfLines={1}>
              {data.company_name}
            </Text>
          </View>
        </View>
        <View style={styles.priceCol}>
          <Text style={styles.price}>
            {data.close != null
              ? data.close.toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
              : "—"}
          </Text>
          <View style={styles.changeRow}>
            {data.change_pct != null ? (
              pos ? (
                <TrendingUp size={11} color={changeColor} strokeWidth={2.5} />
              ) : (
                <TrendingDown size={11} color={changeColor} strokeWidth={2.5} />
              )
            ) : null}
            <Text style={[styles.changeText, { color: changeColor }]}>{changeLabel}</Text>
          </View>
        </View>
      </View>

      <View style={styles.midRow}>
        <View style={styles.signalRow}>
          <View style={styles.dotsRow}>
            {[1, 2, 3].map((i) => (
              <View
                key={i}
                style={[styles.dot, { backgroundColor: i <= dots ? sigColor : "#E5E7EB" }]}
              />
            ))}
          </View>
          <Text style={[styles.signalLabel, { color: sigColor }]}>
            {data.signal_label ?? "—"}
          </Text>
        </View>
        {data.health_display ? (
          <View style={[styles.healthBadge, { borderColor: healthColor(data.health_display) }]}>
            <Heart size={10} color={healthColor(data.health_display)} strokeWidth={2} />
            <Text style={[styles.healthText, { color: healthColor(data.health_display) }]}>
              HEALTH: {data.health_display}
            </Text>
          </View>
        ) : null}
      </View>

      </Pressable>

      <View style={styles.bottomRow}>
        <Pressable onPress={onPress} style={styles.bottomLeftPress}>
          <View style={styles.bottomLeft}>
            {data.confidence_display ? (
              <View style={[styles.confBadge, { backgroundColor: conf.bg }]}>
                <Text style={[styles.confText, { color: conf.text }]}>
                  {data.confidence_display}
                </Text>
              </View>
            ) : null}
            {data.rsi14 != null ? (
              <Text style={styles.rsi}>RSI: {data.rsi14.toFixed(1)}</Text>
            ) : null}
          </View>
        </Pressable>
      </View>

      <LivePriceUpdated at={data.price_updated_at} onPress={openDetail} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#E8EEF0",
    shadowColor: "#0E4D53",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
    gap: 0,
  },
  cardPressable: {
    gap: 0,
  },
  bottomLeftPress: {
    flex: 1,
  },
  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 12,
  },
  topLeft: { flexDirection: "row", flex: 1, gap: 10, marginRight: 8 },
  tickerCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#E8F4F6",
    alignItems: "center",
    justifyContent: "center",
  },
  tickerCircleText: {
    fontFamily: fonts.heading,
    fontSize: 11,
    color: TEAL,
    letterSpacing: 0.3,
  },
  identity: { flex: 1, gap: 2 },
  tickerRow: { flexDirection: "row", alignItems: "center", gap: 6, flexWrap: "wrap" },
  ticker: {
    fontFamily: fonts.heading,
    fontSize: 15,
    color: colors.text,
    letterSpacing: -0.3,
  },
  sectorPill: {
    backgroundColor: "#F0F7F9",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
    maxWidth: "70%",
  },
  sectorPillText: {
    fontFamily: fonts.body,
    fontSize: 8,
    color: TEAL,
    letterSpacing: 0.4,
  },
  company: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: colors.mutedText,
  },
  priceCol: { alignItems: "flex-end" },
  price: {
    fontFamily: fonts.heading,
    fontSize: 18,
    color: colors.text,
    letterSpacing: -0.5,
  },
  changeRow: { flexDirection: "row", alignItems: "center", gap: 3, marginTop: 2 },
  changeText: { fontFamily: fonts.bodyMedium, fontSize: 11 },
  midRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#F0F4F6",
  },
  signalRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  dotsRow: { flexDirection: "row", gap: 4 },
  dot: { width: 7, height: 7, borderRadius: 4 },
  signalLabel: {
    fontFamily: fonts.bodyMedium,
    fontSize: 10,
    letterSpacing: 0.5,
  },
  healthBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    backgroundColor: "#FFFFFF",
  },
  healthText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 9,
    letterSpacing: 0.3,
  },
  bottomRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  bottomLeft: { flexDirection: "row", alignItems: "center", gap: 10, flex: 1 },
  confBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 10,
  },
  confText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 9,
    letterSpacing: 0.3,
  },
  rsi: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: colors.mutedText,
  },
});
