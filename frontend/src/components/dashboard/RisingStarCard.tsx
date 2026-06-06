import LivePriceUpdated from "@/components/ui/LivePriceUpdated";
import type { RisingStar, SignalType } from "@/services/dashboard";
import { colors, fonts } from "@/styles/global";
import { formatDayChangePct } from "@/utils/livePrice";
import { StyleSheet, Text, View } from "react-native";

const SIGNAL_CONFIG: Record<SignalType, { text: string; bg: string }> = {
  BULLISH: { text: "#16A34A", bg: "#DCFCE7" },
  NEUTRAL: { text: "#D97706", bg: "#FEF3C7" },
  BEARISH: { text: "#DC2626", bg: "#FEE2E2" },
};

const SENTIMENT_COLOR: Record<string, string> = {
  EXCELLENT: "#16A34A",
  GOOD: "#16A34A",
  FAIR: "#D97706",
  POOR: "#DC2626",
};

function SignalDots({
  strength,
  color,
}: {
  strength: 1 | 2 | 3;
  color: string;
}) {
  return (
    <View style={styles.signalDotsRow}>
      {([1, 2, 3] as const).map((i) => (
        <View
          key={i}
          style={[
            styles.signalDot,
            { backgroundColor: i <= strength ? color : "#E5E7EB" },
          ]}
        />
      ))}
    </View>
  );
}

type RisingStarCardProps = {
  data: RisingStar;
  onIconPress: () => void;
  fullWidth?: boolean;
};

export default function RisingStarCard({
  data,
  onIconPress,
  fullWidth = false,
}: RisingStarCardProps) {
  const currency = data.currency ?? "Rs.";
  const sig = SIGNAL_CONFIG[data.signal];
  const change = data.changePercent;
  const isPositive = (change ?? 0) >= 0;
  const todayColor =
    change != null ? (isPositive ? "#16A34A" : "#DC2626") : colors.mutedText;
  const todayLabel = formatDayChangePct(change, {
    suffix: "Today",
    decimals: 1,
  });
  const sentColor = SENTIMENT_COLOR[data.sentimentLabel] ?? colors.mutedText;

  return (
    <View style={[styles.card, fullWidth && styles.cardFullWidth]}>
      <View style={styles.topRow}>
        <View style={styles.topLeft}>
          <View style={styles.tickerBadge}>
            <Text style={styles.tickerText}>{data.ticker}</Text>
          </View>
          <View style={[styles.signalPill, { backgroundColor: sig.bg }]}>
            <Text style={[styles.signalPillText, { color: sig.text }]}>
              {data.signal}
            </Text>
          </View>
        </View>
        <Text style={styles.riskLabel}>{data.riskLabel}</Text>
      </View>

      <Text style={styles.price}>
        {currency}{" "}
        {data.price.toLocaleString("en-PK", { minimumFractionDigits: 2 })}
      </Text>

      <Text style={[styles.today, { color: todayColor }]}>{todayLabel}</Text>

      <View style={styles.divider} />

      <View style={styles.metaRow}>
        <Text style={styles.metaLabel}>Forecast (90d)</Text>
        <Text style={styles.metaValue}>
          {data.forecast90d >= 0 ? "+" : ""}
          {data.forecast90d.toFixed(1)}%
        </Text>
      </View>

      <View style={styles.metaRow}>
        <Text style={styles.metaLabel}>Sentiment</Text>
        <Text style={[styles.metaValueAccent, { color: sentColor }]}>
          {data.sentimentLabel}
        </Text>
      </View>

      <View style={styles.signalRow}>
        <SignalDots strength={data.signalStrength} color={sig.text} />
        <Text style={[styles.signalLabel, { color: sig.text }]}>
          {data.signalLabel}
        </Text>
      </View>

      <LivePriceUpdated at={data.priceUpdatedAt} onPress={onIconPress} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    width: 228,
    backgroundColor: colors.background,
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: 8,
  },
  cardFullWidth: {
    width: "100%",
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  topLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    flex: 1,
    paddingRight: 8,
  },
  tickerBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: colors.bgLight,
  },
  tickerText: {
    fontFamily: fonts.heading,
    fontSize: 11,
    color: colors.text,
    letterSpacing: 0.4,
  },
  signalPill: {
    alignSelf: "flex-start",
    paddingHorizontal: 9,
    paddingVertical: 3,
    borderRadius: 20,
  },
  signalPillText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 10,
    letterSpacing: 0.3,
  },
  riskLabel: {
    fontFamily: fonts.body,
    fontSize: 10,
    color: colors.mutedText,
    letterSpacing: 0.3,
  },
  price: {
    fontFamily: fonts.heading,
    fontSize: 24,
    color: colors.text,
    letterSpacing: -0.8,
    marginTop: 2,
  },
  today: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
  },
  divider: {
    height: 1,
    backgroundColor: colors.borderLight,
  },
  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  metaLabel: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
  },
  metaValue: {
    fontFamily: fonts.heading,
    fontSize: 13,
    color: "#16A34A",
  },
  metaValueAccent: {
    fontFamily: fonts.heading,
    fontSize: 13,
  },
  signalDotsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  signalDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  signalRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    marginTop: 2,
  },
  signalLabel: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    letterSpacing: 0.2,
  },
});
