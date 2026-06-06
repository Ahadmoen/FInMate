import LivePriceUpdated from "@/components/ui/LivePriceUpdated";
import { PAKISTAN_BROKERS, type PakistanBroker } from "@/constants/pakistanBrokers";
import { useAuth } from "@/context/AuthContext";
import { fetchAllStocks, type StockSearchResult } from "@/services/portfolio";
import { colors, fonts } from "@/styles/global";
import { useRouter } from "expo-router";
import {
  ArrowDownCircle,
  ArrowUpCircle,
  Building2,
  Check,
  ChevronLeft,
  Landmark,
  Link2,
  Search,
  TrendingUp,
} from "lucide-react-native";
import { memo, useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  ListRenderItem,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

const MVP_MESSAGE =
  "Broker connection and live buy/sell are not included in this MVP. You can preview brokers and PSX stocks; trading will be available in a future release.";

const BROKER_ROW_HEIGHT = 50;
const STOCK_ROW_HEIGHT = 64;
/** Minimum scroll area per panel when flex layout is constrained. */
const MIN_LIST_PANEL_HEIGHT = 140;

type StockRowData = {
  symbol_id: string;
  symbol: string;
  name: string;
  industry: string;
  priceLabel: string;
  changeLabel: string | null;
  changePositive: boolean;
  priceUpdatedAt: string | null;
};

function formatPrice(value: string | null): string {
  if (value == null) return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `Rs. ${n.toLocaleString("en-PK", { maximumFractionDigits: 2 })}`;
}

function toStockRowData(stock: StockSearchResult): StockRowData {
  const pct = stock.change_percent;
  const changePositive = (pct ?? 0) >= 0;
  return {
    symbol_id: stock.symbol_id,
    symbol: stock.symbol,
    name: stock.name,
    industry: stock.industry,
    priceLabel: formatPrice(stock.current_price),
    changeLabel:
      pct != null ? `${changePositive ? "+" : ""}${pct.toFixed(2)}%` : null,
    changePositive,
    priceUpdatedAt: stock.price_updated_at,
  };
}

type StockRowProps = {
  item: StockRowData;
  selected: boolean;
  enabled: boolean;
  onPress: (symbolId: string) => void;
};

const StockRow = memo(function StockRow({
  item,
  selected,
  enabled,
  onPress,
}: StockRowProps) {
  const handlePress = useCallback(() => {
    onPress(item.symbol_id);
  }, [item.symbol_id, onPress]);

  return (
    <Pressable
      style={[
        styles.stockRow,
        !enabled && styles.stockRowDisabled,
        selected && enabled && styles.stockRowSelected,
      ]}
      onPress={handlePress}
      disabled={!enabled}
      android_ripple={{ color: colors.bgPrimaryLight }}
    >
      <View style={styles.stockRowTop}>
        <View style={styles.stockBadge}>
          <Text style={styles.stockBadgeText} numberOfLines={1}>
            {item.symbol}
          </Text>
        </View>
        <View style={styles.stockInfo}>
          <Text
            style={[styles.stockName, !enabled && styles.textDisabled]}
            numberOfLines={1}
          >
            {item.name}
          </Text>
          <Text style={[styles.stockIndustry, !enabled && styles.textDisabled]}>
            {item.industry}
          </Text>
        </View>
        <View style={styles.stockPriceCol}>
          <Text style={[styles.stockPrice, !enabled && styles.textDisabled]}>
            {item.priceLabel}
          </Text>
          {item.changeLabel ? (
            <Text
              style={[
                styles.stockChange,
                !enabled && styles.textDisabled,
                item.changePositive ? styles.changeUp : styles.changeDown,
              ]}
            >
              {item.changeLabel}
            </Text>
          ) : null}
        </View>
      </View>
      <LivePriceUpdated
        at={item.priceUpdatedAt}
        style={styles.stockPriceUpdated}
      />
    </Pressable>
  );
});

type BrokerRowProps = {
  broker: PakistanBroker;
  selected: boolean;
  onPress: (broker: PakistanBroker) => void;
};

const BrokerRow = memo(function BrokerRow({ broker, selected, onPress }: BrokerRowProps) {
  const handlePress = useCallback(() => {
    onPress(broker);
  }, [broker, onPress]);

  return (
    <Pressable
      style={[styles.brokerRow, selected && styles.brokerRowSelected]}
      onPress={handlePress}
      android_ripple={{ color: colors.bgPrimaryLight }}
    >
      <View style={styles.brokerText}>
        <Text style={[styles.brokerName, selected && styles.brokerNameSelected]}>
          {broker.name}
        </Text>
        <Text style={styles.brokerCity}>{broker.city}</Text>
      </View>
      {selected ? (
        <View style={styles.brokerCheck}>
          <Check size={14} color="#FFFFFF" strokeWidth={2.5} />
        </View>
      ) : (
        <Building2 size={16} color={colors.mutedText} strokeWidth={1.5} />
      )}
    </Pressable>
  );
});

export default function BuySellStockScreen() {
  const router = useRouter();
  const { token } = useAuth();

  const [selectedBrokerId, setSelectedBrokerId] = useState<string | null>(null);
  const [stocks, setStocks] = useState<StockSearchResult[]>([]);
  const [stocksLoading, setStocksLoading] = useState(true);
  const [stocksError, setStocksError] = useState<string | null>(null);
  const [brokerQuery, setBrokerQuery] = useState("");
  const [stockQuery, setStockQuery] = useState("");
  const [selectedStockId, setSelectedStockId] = useState<string | null>(null);

  const stocksEnabled = selectedBrokerId !== null;
  const selectedBroker = useMemo(
    () => PAKISTAN_BROKERS.find((b) => b.id === selectedBrokerId) ?? null,
    [selectedBrokerId],
  );

  useEffect(() => {
    if (!token) return;
    setStocksLoading(true);
    setStocksError(null);
    fetchAllStocks(token)
      .then((list) => setStocks(Array.isArray(list) ? list : []))
      .catch((err) =>
        setStocksError(err instanceof Error ? err.message : "Failed to load stocks."),
      )
      .finally(() => setStocksLoading(false));
  }, [token]);

  const stockRows = useMemo(() => stocks.map(toStockRowData), [stocks]);

  const filteredBrokers = useMemo(() => {
    const q = brokerQuery.trim().toLowerCase();
    if (!q) return PAKISTAN_BROKERS;
    return PAKISTAN_BROKERS.filter(
      (b) =>
        b.name.toLowerCase().includes(q) || b.city.toLowerCase().includes(q),
    );
  }, [brokerQuery]);

  const filteredStocks = useMemo(() => {
    const q = stockQuery.trim().toLowerCase();
    if (!q) return stockRows;
    return stockRows.filter(
      (s) =>
        s.symbol.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q) ||
        s.industry.toLowerCase().includes(q),
    );
  }, [stockRows, stockQuery]);

  const onSelectBroker = useCallback((broker: PakistanBroker) => {
    setSelectedBrokerId(broker.id);
  }, []);

  const onSelectStock = useCallback((symbolId: string) => {
    setSelectedStockId(symbolId);
  }, []);

  const brokerKeyExtractor = useCallback((item: PakistanBroker) => item.id, []);

  const brokerGetItemLayout = useCallback(
    (_: ArrayLike<PakistanBroker> | null | undefined, index: number) => ({
      length: BROKER_ROW_HEIGHT,
      offset: BROKER_ROW_HEIGHT * index,
      index,
    }),
    [],
  );

  const renderBroker: ListRenderItem<PakistanBroker> = useCallback(
    ({ item }) => (
      <BrokerRow
        broker={item}
        selected={selectedBrokerId === item.id}
        onPress={onSelectBroker}
      />
    ),
    [selectedBrokerId, onSelectBroker],
  );

  const brokerListEmpty = useCallback(
    () => (
      <View style={styles.listPlaceholder}>
        <Text style={styles.listEmpty}>No brokerage firms match your search.</Text>
      </View>
    ),
    [],
  );

  const stockKeyExtractor = useCallback((item: StockRowData) => item.symbol_id, []);

  const stockGetItemLayout = useCallback(
    (_: ArrayLike<StockRowData> | null | undefined, index: number) => ({
      length: STOCK_ROW_HEIGHT,
      offset: STOCK_ROW_HEIGHT * index,
      index,
    }),
    [],
  );

  const renderStock: ListRenderItem<StockRowData> = useCallback(
    ({ item }) => (
      <StockRow
        item={item}
        selected={item.symbol_id === selectedStockId}
        enabled={stocksEnabled}
        onPress={onSelectStock}
      />
    ),
    [selectedStockId, stocksEnabled, onSelectStock],
  );

  const stockListEmpty = useCallback(() => {
    if (stocksLoading) {
      return (
        <View style={styles.listPlaceholder}>
          <ActivityIndicator color={colors.primary} />
        </View>
      );
    }
    if (stocksError) {
      return (
        <View style={styles.listPlaceholder}>
          <Text style={styles.listError}>{stocksError}</Text>
        </View>
      );
    }
    if (!stocksEnabled) {
      return (
        <View style={styles.listPlaceholder}>
          <Text style={styles.listEmpty}>Select a broker to browse stocks.</Text>
        </View>
      );
    }
    return (
      <View style={styles.listPlaceholder}>
        <Text style={styles.listEmpty}>No stocks match your search.</Text>
      </View>
    );
  }, [stocksEnabled, stocksError, stocksLoading]);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <Pressable style={styles.backBtn} onPress={() => router.back()} hitSlop={10}>
          <ChevronLeft size={22} color={colors.primary} strokeWidth={2} />
        </Pressable>
        <Text style={styles.headerTitle}>Buy / Sell Stock</Text>
        <Text style={styles.headerLogo}>FinMate</Text>
      </View>

      <View style={styles.body}>
        <View style={styles.topSection}>
          <Text style={styles.introTitle}>Trade on PSX</Text>
          <View style={styles.actionRow}>
            <Pressable style={[styles.actionBtn, styles.actionBtnDisabled]} disabled>
              <ArrowUpCircle size={16} color={colors.mutedText} strokeWidth={1.8} />
              <Text style={styles.actionBtnTextDisabled}>Buy</Text>
            </Pressable>
            <Pressable style={[styles.actionBtn, styles.actionBtnDisabled]} disabled>
              <ArrowDownCircle size={16} color={colors.mutedText} strokeWidth={1.8} />
              <Text style={styles.actionBtnTextDisabled}>Sell</Text>
            </Pressable>
          </View>
        </View>

        <View style={styles.panelsContainer}>
        <View style={[styles.card, styles.brokerPanel]}>
          <View style={[styles.cardHeader, { backgroundColor: colors.bgPrimaryLight }]}>
            <View style={styles.cardHeaderIcon}>
              <Landmark size={17} color={colors.primary} strokeWidth={2} />
            </View>
            <Text style={styles.cardHeaderTitle}>Brokerage Firms (Pakistan)</Text>
          </View>
          <View style={styles.cardBody}>
            <View style={styles.searchWrap}>
              <Search size={16} color={colors.mutedText} />
              <TextInput
                style={styles.searchInput}
                placeholder="Search broker or city…"
                placeholderTextColor={colors.mutedText}
                value={brokerQuery}
                onChangeText={setBrokerQuery}
              />
            </View>
          </View>
          <View style={styles.listWindow}>
            <FlatList
              data={filteredBrokers}
              keyExtractor={brokerKeyExtractor}
              renderItem={renderBroker}
              ListEmptyComponent={brokerListEmpty}
              extraData={selectedBrokerId}
              getItemLayout={brokerGetItemLayout}
              initialNumToRender={8}
              maxToRenderPerBatch={10}
              windowSize={6}
              removeClippedSubviews
              showsVerticalScrollIndicator
              keyboardShouldPersistTaps="handled"
              style={styles.panelFlatList}
            />
          </View>
        </View>

        <View
          style={[
            styles.card,
            styles.stockPanel,
            !stocksEnabled && styles.cardMuted,
          ]}
        >
          <View
            style={[
              styles.cardHeader,
              {
                backgroundColor: stocksEnabled ? colors.bgTertiaryLight : colors.bgLight,
              },
            ]}
          >
            <View style={styles.cardHeaderIcon}>
              <TrendingUp
                size={17}
                color={stocksEnabled ? colors.primary : colors.mutedText}
                strokeWidth={2}
              />
            </View>
            <View style={styles.cardHeaderTextCol}>
              <Text
                style={[
                  styles.cardHeaderTitle,
                  !stocksEnabled && styles.cardHeaderTitleMuted,
                ]}
              >
                PSX Stocks
              </Text>
              <Text style={styles.cardHeaderHint}>
                {stocksEnabled
                  ? `Previewing via ${selectedBroker?.name}`
                  : "Select a broker above to enable this list"}
              </Text>
            </View>
          </View>

          <View style={[styles.cardBody, !stocksEnabled && styles.cardBodyDisabled]}>
            <View
              style={[styles.searchWrap, !stocksEnabled && styles.searchWrapDisabled]}
            >
              <Search size={16} color={colors.mutedText} />
              <TextInput
                style={[styles.searchInput, !stocksEnabled && styles.searchInputDisabled]}
                placeholder="Search ticker or company…"
                placeholderTextColor={colors.mutedText}
                value={stockQuery}
                onChangeText={setStockQuery}
                editable={stocksEnabled}
              />
            </View>
          </View>

          <View style={styles.listWindow}>
            <FlatList
              data={!stocksLoading && !stocksError ? filteredStocks : []}
              keyExtractor={stockKeyExtractor}
              renderItem={renderStock}
              ListEmptyComponent={stockListEmpty}
              extraData={selectedStockId}
              getItemLayout={stockGetItemLayout}
              initialNumToRender={10}
              maxToRenderPerBatch={14}
              windowSize={7}
              updateCellsBatchingPeriod={16}
              removeClippedSubviews
              scrollEnabled={stocksEnabled && !stocksLoading && !stocksError}
              showsVerticalScrollIndicator={stocksEnabled}
              keyboardShouldPersistTaps="handled"
              style={styles.panelFlatList}
            />
          </View>
        </View>
        </View>

        <View style={styles.footer}>
          <Pressable style={styles.connectBtn} disabled>
            <Link2 size={16} color={colors.background} strokeWidth={2} />
            <Text style={styles.connectBtnText}>Connect Broker Account</Text>
          </Pressable>
          <Text style={styles.mvpNote}>{MVP_MESSAGE}</Text>
        </View>
      </View>
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
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: colors.background,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  backBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontFamily: fonts.heading,
    fontSize: 16,
    color: colors.text,
    letterSpacing: -0.3,
  },
  headerLogo: {
    fontFamily: fonts.heading,
    fontSize: 13,
    color: colors.primary,
    letterSpacing: -0.2,
    minWidth: 56,
    textAlign: "right",
  },

  body: {
    flex: 1,
    paddingHorizontal: 16,
    paddingBottom: 6,
  },
  topSection: {
    flexShrink: 0,
    paddingTop: 8,
    paddingBottom: 6,
    gap: 6,
  },
  panelsContainer: {
    flex: 1,
    minHeight: 0,
    gap: 8,
  },
  footer: {
    flexShrink: 0,
    gap: 6,
    paddingTop: 6,
    paddingBottom: 8,
  },
  brokerPanel: {
    flex: 1,
  },
  stockPanel: {
    flex: 1,
  },
  listWindow: {
    flex: 1,
    minHeight: MIN_LIST_PANEL_HEIGHT,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
    backgroundColor: colors.bgLightest,
    overflow: "hidden",
  },
  panelFlatList: {
    flex: 1,
  },
  listPlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 20,
    minHeight: 80,
  },
  listEmpty: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
    textAlign: "center",
  },
  listError: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.error,
    textAlign: "center",
  },

  introTitle: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: colors.primary,
    letterSpacing: -0.2,
  },

  actionRow: {
    flexDirection: "row",
    gap: 8,
  },
  actionBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    height: 36,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderMutedLight,
    backgroundColor: colors.bgLight,
  },
  actionBtnDisabled: {
    opacity: 0.65,
  },
  actionBtnTextDisabled: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: colors.mutedText,
  },

  card: {
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderLight,
    overflow: "hidden",
    backgroundColor: colors.background,
    flex: 1,
    minHeight: 0,
  },
  cardMuted: {
    opacity: 0.92,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.bgIconLight,
    flexShrink: 0,
  },
  cardHeaderIcon: {
    width: 34,
    height: 34,
    borderRadius: 9,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.bgIconLight,
    alignItems: "center",
    justifyContent: "center",
  },
  cardHeaderTextCol: { flex: 1, gap: 2 },
  cardHeaderTitle: {
    fontFamily: fonts.heading,
    fontSize: 15,
    color: colors.primary,
    letterSpacing: -0.2,
  },
  cardHeaderTitleMuted: {
    color: colors.mutedText,
  },
  cardHeaderHint: {
    fontFamily: fonts.body,
    fontSize: 10,
    color: colors.mutedText,
    lineHeight: 14,
  },
  cardBody: {
    paddingHorizontal: 12,
    paddingBottom: 2,
    flexShrink: 0,
  },
  cardBodyDisabled: {
    opacity: 0.55,
  },

  divider: {
    height: 1,
    backgroundColor: colors.borderLight,
  },

  brokerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    height: BROKER_ROW_HEIGHT,
    paddingHorizontal: 12,
    gap: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  brokerRowSelected: {
    backgroundColor: colors.bgPrimaryLight,
  },
  brokerText: { flex: 1, gap: 2 },
  brokerName: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.text,
  },
  brokerNameSelected: {
    color: colors.primary,
  },
  brokerCity: {
    fontFamily: fonts.body,
    fontSize: 10,
    color: colors.mutedText,
  },
  brokerCheck: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },

  searchWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    height: 36,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderMutedLight,
    paddingHorizontal: 10,
    marginVertical: 6,
    backgroundColor: colors.background,
  },
  searchWrapDisabled: {
    backgroundColor: colors.bgLight,
    borderColor: colors.borderLight,
  },
  searchInput: {
    flex: 1,
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.text,
    paddingVertical: 0,
  },
  searchInputDisabled: {
    color: colors.mutedText,
  },

  stockRow: {
    flexDirection: "column",
    alignItems: "stretch",
    justifyContent: "center",
    height: STOCK_ROW_HEIGHT,
    paddingHorizontal: 12,
    paddingVertical: 6,
    gap: 2,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  stockRowTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  stockRowDisabled: {
    opacity: 0.7,
  },
  stockRowSelected: {
    backgroundColor: colors.bgPrimaryLight,
  },
  stockBadge: {
    minWidth: 44,
    paddingHorizontal: 6,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: colors.bgSecondaryLight,
    alignItems: "center",
  },
  stockBadgeText: {
    fontFamily: fonts.heading,
    fontSize: 11,
    color: colors.primary,
  },
  stockInfo: { flex: 1, gap: 2 },
  stockName: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.text,
  },
  stockIndustry: {
    fontFamily: fonts.body,
    fontSize: 10,
    color: colors.mutedText,
  },
  stockPriceCol: { alignItems: "flex-end", gap: 2 },
  stockPrice: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.text,
  },
  stockChange: {
    fontFamily: fonts.body,
    fontSize: 10,
  },
  stockPriceUpdated: {
    marginTop: 2,
  },
  changeUp: { color: "#1D9E75" },
  changeDown: { color: "#E24B4A" },
  textDisabled: { color: colors.mutedText },

  connectBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    height: 40,
    borderRadius: 10,
    backgroundColor: colors.mutedText,
    opacity: 0.55,
  },
  connectBtnText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: colors.background,
  },
  mvpNote: {
    fontFamily: fonts.body,
    fontSize: 10,
    color: colors.mutedText,
    textAlign: "center",
    lineHeight: 14,
    paddingHorizontal: 4,
  },
});
