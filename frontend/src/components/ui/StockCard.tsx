import LivePriceUpdated from "@/components/ui/LivePriceUpdated";
import { colors, fonts } from "@/styles/global";
import { TrendingDown, TrendingUp } from "lucide-react-native";
import { Pressable, StyleSheet, Text, View } from "react-native";

// ─── Types ────────────────────────────────────────────────────────────────────

export type StockCardData = {
  ticker: string;
  company: string;
  sector?: string;
  price: number;
  changePercent: number;
  currency?: string;
  priceUpdatedAt?: string | null;
};

type Props = {
  data: StockCardData;
  onPress?: () => void;
  onDetailPress?: () => void;
};

// ─── Ticker Colour Map ────────────────────────────────────────────────────────

const TICKER_COLORS: Record<string, string> = {
  HBL:   "#0D4954",
  UBL:   "#1E3A5F",
  MCB:   "#065F46",
  NBP:   "#1D4ED8",
  LUCI:  "#7C3AED",
  PKGS:  "#374151",
  OGDC:  "#0369A1",
  TRG:   "#6D28D9",
  ENGRO: "#065F46",
  PNSC:  "#92400E",
  LUPC:  "#9D174D",
  NVDA:  "#1E3A5F",
  AAPL:  "#374151",
  MSFT:  "#1D4ED8",
  TSLA:  "#B91C1C",
  GOOGL: "#0369A1",
};

function getTickerColor(ticker: string): string {
  return TICKER_COLORS[ticker] ?? colors.primary;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function StockCard({ data, onPress, onDetailPress }: Props) {
  const isPositive = data.changePercent >= 0;
  const changeColor = isPositive ? "#16A34A" : "#DC2626";
  const changeBg    = isPositive ? "#DCFCE7" : "#FEE2E2";
  const currency    = data.currency ?? "Rs.";
  const changeLabel = `${isPositive ? "+" : ""}${data.changePercent.toFixed(2)}%`;

  return (
    <Pressable style={styles.card} onPress={onPress}>
      {/* Ticker badge */}
      <View style={[styles.tickerBadge, { backgroundColor: getTickerColor(data.ticker) }]}>
        <Text style={styles.tickerText}>{data.ticker}</Text>
      </View>

      {/* Company name */}
      <Text style={styles.company} numberOfLines={2}>
        {data.company}
      </Text>

      {/* Price */}
      <Text style={styles.price}>
        {currency} {data.price.toLocaleString("en-PK", { minimumFractionDigits: 2 })}
      </Text>

      {/* Change badge */}
      <View style={[styles.changeBadge, { backgroundColor: changeBg }]}>
        {isPositive ? (
          <TrendingUp size={10} color={changeColor} strokeWidth={2.5} />
        ) : (
          <TrendingDown size={10} color={changeColor} strokeWidth={2.5} />
        )}
        <Text style={[styles.changeText, { color: changeColor }]}>{changeLabel}</Text>
      </View>
      <View style={styles.cardFooter}>
        <LivePriceUpdated
          at={data.priceUpdatedAt}
          onPress={onDetailPress ?? onPress}
          style={styles.cardFooterText}
        />
      </View>
    </Pressable>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  card: {
    flex: 1,
    backgroundColor: colors.background,
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: 6,
    justifyContent: "space-between",
    minHeight: 140,
  },
  cardFooter: {
    marginTop: "auto",
    alignSelf: "stretch",
  },
  cardFooterText: {
    marginTop: 0,
  },
  tickerBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    marginBottom: 2,
  },
  tickerText: {
    fontFamily: fonts.heading,
    fontSize: 11,
    color: "#FFFFFF",
    letterSpacing: 0.5,
  },
  company: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
    lineHeight: 17,
    minHeight: 34,
  },
  price: {
    fontFamily: fonts.heading,
    fontSize: 15,
    color: colors.text,
    letterSpacing: -0.3,
  },
  changeBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    alignSelf: "flex-start",
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 20,
  },
  changeText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
  },
});
