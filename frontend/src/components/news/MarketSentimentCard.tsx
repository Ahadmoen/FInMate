import type { MarketSentimentIndex } from "@/services/news";
import { fonts } from "@/styles/global";
import { StyleSheet, Text, View } from "react-native";
import Svg, { Path } from "react-native-svg";

const TEAL_DARK = "#0E4D53";
const GOLD = "#E8C547";

type Props = {
  data: MarketSentimentIndex;
};

export default function MarketSentimentCard({ data }: Props) {
  const changePrefix = data.change_pct >= 0 ? "+" : "";
  const changeText = `${changePrefix}${data.change_pct}%`;

  return (
    <View style={styles.card}>
      <View style={styles.chartBg}>
        <Svg width={120} height={80} viewBox="0 0 120 80">
          <Path
            d="M0 60 L25 45 L50 50 L75 30 L100 20 L120 10"
            stroke="rgba(255,255,255,0.15)"
            strokeWidth={2}
            fill="none"
          />
        </Svg>
      </View>

      <Text style={styles.label}>MARKET SENTIMENT INDEX</Text>

      <View style={styles.valueRow}>
        <Text style={styles.value}>{data.value.toFixed(1)}</Text>
        <Text style={styles.change}>{changeText}</Text>
      </View>

      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width: `${Math.min(100, Math.max(0, data.progress))}%` }]} />
      </View>

      <Text style={styles.message}>{data.message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: TEAL_DARK,
    borderRadius: 16,
    padding: 18,
    marginBottom: 16,
    overflow: "hidden",
  },
  chartBg: {
    position: "absolute",
    right: 8,
    top: 12,
    opacity: 0.9,
  },
  label: {
    fontFamily: fonts.bodyMedium,
    fontSize: 10,
    color: "rgba(255,255,255,0.75)",
    letterSpacing: 1.2,
    marginBottom: 6,
  },
  valueRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 10,
    marginBottom: 12,
  },
  value: {
    fontFamily: fonts.heading,
    fontSize: 36,
    color: "#FFFFFF",
    letterSpacing: -1,
    lineHeight: 40,
  },
  change: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: "rgba(255,255,255,0.9)",
    marginBottom: 6,
  },
  barTrack: {
    height: 6,
    backgroundColor: "rgba(255,255,255,0.2)",
    borderRadius: 3,
    marginBottom: 12,
    overflow: "hidden",
  },
  barFill: {
    height: 6,
    backgroundColor: GOLD,
    borderRadius: 3,
  },
  message: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: "rgba(255,255,255,0.85)",
    lineHeight: 16,
    paddingRight: 48,
  },
});
