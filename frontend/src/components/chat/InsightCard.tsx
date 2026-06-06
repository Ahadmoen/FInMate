import { chatColors, chatShadow } from "@/components/chat/chatTheme";
import type { StockInsight } from "@/components/chat/types";
import { fonts } from "@/styles/global";
import { StyleSheet, Text, View } from "react-native";

type Props = {
  insight: StockInsight;
};

function formatVolume(volume: number): string {
  if (volume >= 1_000_000) {
    return `${(volume / 1_000_000).toFixed(1)}M`;
  }
  if (volume >= 1_000) {
    return `${(volume / 1_000).toFixed(1)}K`;
  }
  return volume.toLocaleString("en-PK");
}

function formatUpdatedAt(iso: string): string {
  const d = new Date(iso.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function InsightCard({ insight }: Props) {
  return (
    <View style={styles.card}>
      <View style={styles.accentBar} />

      <View style={styles.inner}>
        <View style={styles.head}>
          <View style={styles.tag}>
            <View style={styles.spark} />
            <Text style={styles.tagText}>Insight</Text>
          </View>
          <Text style={styles.time}>
            As of {formatUpdatedAt(insight.updatedAt)}
          </Text>
        </View>

        <View style={styles.identity}>
          <Text style={styles.ticker}>{insight.symbol}</Text>
          <Text style={styles.company} numberOfLines={2}>
            {insight.companyName}
          </Text>
        </View>

        <View style={styles.priceRow}>
          <Text style={styles.price}>
            <Text style={styles.currency}>{insight.currency} </Text>
            {insight.currentPrice.toFixed(2)}
          </Text>
        </View>

        <View style={styles.stats}>
          {[
            { label: "Open", value: insight.open.toFixed(2) },
            { label: "High", value: insight.high.toFixed(2) },
            { label: "Low", value: insight.low.toFixed(2) },
            { label: "Volume", value: formatVolume(insight.volume) },
          ].map((stat) => (
            <View key={stat.label} style={styles.stat}>
              <Text style={styles.statLabel}>{stat.label}</Text>
              <Text style={styles.statVal}>{stat.value}</Text>
            </View>
          ))}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: chatColors.card,
    borderRadius: 16,
    overflow: "hidden",
    ...chatShadow.card,
  },
  accentBar: {
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    width: 4,
    backgroundColor: chatColors.teal,
  },
  inner: {
    paddingVertical: 14,
    paddingHorizontal: 16,
    paddingLeft: 18,
    gap: 12,
  },
  head: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  tag: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  spark: {
    width: 6,
    height: 6,
    borderRadius: 2,
    backgroundColor: chatColors.tealAccent,
  },
  tagText: {
    fontFamily: fonts.heading,
    fontSize: 10.5,
    letterSpacing: 0.6,
    textTransform: "uppercase",
    color: chatColors.tealSoft,
  },
  time: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    color: chatColors.muted2,
  },
  identity: {
    gap: 4,
  },
  ticker: {
    fontFamily: fonts.heading,
    fontSize: 17,
    color: chatColors.ink,
    letterSpacing: -0.2,
  },
  company: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: chatColors.muted,
    lineHeight: 18,
  },
  priceRow: {
    paddingTop: 2,
  },
  price: {
    fontFamily: fonts.heading,
    fontSize: 20,
    color: chatColors.ink,
    letterSpacing: -0.3,
  },
  currency: {
    fontSize: 12,
    color: chatColors.muted,
  },
  stats: {
    flexDirection: "row",
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: chatColors.line,
    gap: 6,
  },
  stat: {
    flex: 1,
    gap: 2,
  },
  statLabel: {
    fontFamily: fonts.heading,
    fontSize: 9,
    letterSpacing: 0.5,
    textTransform: "uppercase",
    color: chatColors.muted2,
  },
  statVal: {
    fontFamily: fonts.heading,
    fontSize: 12.5,
    color: chatColors.ink,
    letterSpacing: -0.2,
  },
});
