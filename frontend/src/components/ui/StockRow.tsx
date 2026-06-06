import { colors, fonts } from "@/styles/global";
import { TrendingDown, TrendingUp } from "lucide-react-native";
import { Pressable, StyleSheet, Text, View } from "react-native";

// ─── Types ────────────────────────────────────────────────────────────────────

export type StockRowData = {
  ticker: string;
  company: string;
  sector?: string;
  price: number;
  changePercent: number;
  currency?: string;
};

type Props = {
  data: StockRowData;
  onPress?: () => void;
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

export default function StockRow({ data, onPress }: Props) {
  const isPositive = data.changePercent >= 0;
  const changeColor = isPositive ? "#16A34A" : "#DC2626";
  const changeBg    = isPositive ? "#DCFCE7" : "#FEE2E2";
  const currency    = data.currency ?? "Rs.";
  const changeLabel = `${isPositive ? "+" : ""}${data.changePercent.toFixed(2)}%`;

  return (
    <Pressable style={styles.row} onPress={onPress}>
      {/* Ticker badge */}
      <View style={[styles.tickerBadge, { backgroundColor: getTickerColor(data.ticker) }]}>
        <Text style={styles.tickerText}>{data.ticker}</Text>
      </View>

      {/* Company + change badge */}
      <View style={styles.middle}>
        <Text style={styles.company} numberOfLines={1}>{data.company}</Text>
        <View style={[styles.changeBadge, { backgroundColor: changeBg }]}>
          {isPositive ? (
            <TrendingUp size={10} color={changeColor} strokeWidth={2.5} />
          ) : (
            <TrendingDown size={10} color={changeColor} strokeWidth={2.5} />
          )}
          <Text style={[styles.changeText, { color: changeColor }]}>{changeLabel}</Text>
        </View>
      </View>

      {/* Price */}
      <Text style={styles.price}>
        {currency} {data.price.toLocaleString("en-PK", { minimumFractionDigits: 2 })}
      </Text>
    </Pressable>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 10,
  },
  tickerBadge: {
    width: 52,
    paddingVertical: 7,
    borderRadius: 8,
    alignItems: "center",
  },
  tickerText: {
    fontFamily: fonts.heading,
    fontSize: 11,
    color: "#FFFFFF",
    letterSpacing: 0.4,
  },
  middle: {
    flex: 1,
    gap: 5,
  },
  company: {
    fontFamily: fonts.heading,
    fontSize: 13,
    color: colors.text,
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
  price: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: colors.text,
    textAlign: "right",
  },
});
