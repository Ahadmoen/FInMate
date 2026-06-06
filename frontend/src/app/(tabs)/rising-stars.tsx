import RisingStarCard from "@/components/dashboard/RisingStarCard";
import ScreenHeader from "@/components/ui/ScreenHeader";
import { getRisingStarsFromDashboard } from "@/navigation/risingStarsNavigation";
import type { RisingStar, SignalType } from "@/services/dashboard";
import { colors, fonts } from "@/styles/global";
import { useFocusEffect, useRouter } from "expo-router";
import { ChevronLeft } from "lucide-react-native";
import { useCallback, useState } from "react";
import {
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

function signalToParam(signal: SignalType): string {
  if (signal === "BULLISH") return "BUY";
  if (signal === "BEARISH") return "SELL";
  return "HOLD";
}

export default function RisingStarsScreen() {
  const router = useRouter();
  const [risingStars, setRisingStars] = useState<RisingStar[]>(() =>
    getRisingStarsFromDashboard(),
  );

  useFocusEffect(
    useCallback(() => {
      setRisingStars(getRisingStarsFromDashboard());
    }, []),
  );

  const openStockInsight = useCallback(
    (star: RisingStar) => {
      router.push({
        pathname: "/stock-insight/[ticker]",
        params: {
          ticker: star.ticker,
          company_name: star.company,
          sector: star.sector,
          close: String(star.price),
          change_pct:
            star.changePercent != null ? String(star.changePercent) : "",
          signal: signalToParam(star.signal),
          signal_label: star.signalLabel,
          health_display: star.sentimentLabel,
          confidence_display: "",
          rsi14: "",
        },
      });
    },
    [router],
  );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScreenHeader />

      <View style={styles.pageBar}>
        <Pressable
          style={styles.backBtn}
          onPress={() => router.back()}
          hitSlop={8}
        >
          <ChevronLeft size={22} color={colors.text} strokeWidth={2} />
        </Pressable>
        <View style={styles.pageBarCenter}>
          <Text style={styles.pageTitle}>Rising Stars</Text>
          {risingStars.length > 0 ? (
            <Text style={styles.pageSubtitle}>
              {risingStars.length} stocks
            </Text>
          ) : null}
        </View>
        <View style={styles.backBtn} />
      </View>

      <FlatList
        data={risingStars}
        keyExtractor={(item) => item.ticker}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        renderItem={({ item }) => (
          <RisingStarCard
            data={item}
            fullWidth
            onIconPress={() => openStockInsight(item)}
          />
        )}
        ListEmptyComponent={
          <Text style={styles.emptyText}>
            Open Rising Stars from the dashboard to see stocks here.
          </Text>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.bgLight,
  },
  pageBar: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: colors.background,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  backBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  pageBarCenter: {
    flex: 1,
    alignItems: "center",
    gap: 2,
  },
  pageTitle: {
    fontFamily: fonts.heading,
    fontSize: 17,
    color: colors.text,
    letterSpacing: -0.3,
  },
  pageSubtitle: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
  },
  listContent: {
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 100,
    gap: 12,
  },
  emptyText: {
    fontFamily: fonts.body,
    fontSize: 14,
    color: colors.mutedText,
    textAlign: "center",
    marginTop: 40,
    paddingHorizontal: 24,
  },
});
