import { useAuth } from "@/context/AuthContext";
import {
  addHolding,
  deleteHolding,
  fetchAllStocks,
  fetchHoldings,
  updateHolding,
  type PortfolioHolding,
  type StockSearchResult,
} from "@/services/portfolio";
import LivePriceUpdated from "@/components/ui/LivePriceUpdated";
import { colors, fonts } from "@/styles/global";
import { useRouter } from "expo-router";
import {
  Briefcase,
  Check,
  CheckCircle2,
  ChevronLeft,
  Info,
  Landmark,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react-native";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Animated,
  Easing,
  FlatList,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

// ─── Types ────────────────────────────────────────────────────────────────────

type Step = 1 | 2 | 3;
type SheetMode = "add" | "edit";
type InputMode = "qtyPrice" | "totalInvested";

type Lot = { id: string; amountOrShares: string; price: string };

// ─── Local accent tokens ──────────────────────────────────────────────────────

const GREEN = "#1D9E75";
const RED = "#E24B4A";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const parseNum = (v: string) => {
  const n = Number(v.replace(/,/g, "").trim());
  return Number.isFinite(n) ? n : 0;
};

const fmtRs = (n: number, dp = 2) =>
  `Rs. ${n.toLocaleString("en-PK", { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;

const fmtPct = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(3)}%`;

const newLot = (): Lot => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
  amountOrShares: "",
  price: "",
});

/** Weighted average from filled lot rows only (empty rows are ignored). */
function calcLotsFromRows(lots: Lot[], mode: InputMode) {
  let shares = 0;
  let invested = 0;
  let validLotCount = 0;

  lots.forEach((l) => {
    const left = parseNum(l.amountOrShares);
    const price = parseNum(l.price);
    if (left <= 0 || price <= 0) return;
    validLotCount += 1;
    if (mode === "qtyPrice") {
      shares += left;
      invested += left * price;
    } else {
      invested += left;
      shares += left / price;
    }
  });

  return {
    shares,
    invested,
    avgPrice: shares > 0 ? invested / shares : 0,
    validLotCount,
  };
}

function holdingToStockResult(h: PortfolioHolding): StockSearchResult {
  return {
    symbol_id: h.symbol_id,
    symbol: h.ticker,
    name: h.name,
    industry: h.industry,
    current_price: h.current_price != null ? String(h.current_price) : null,
    change_percent: h.change_percent,
    last_close: null,
    price_updated_at: h.price_updated_at,
  };
}

// ─── Screen ───────────────────────────────────────────────────────────────────

export default function ManagePortfolioScreen() {
  const router = useRouter();
  const { token } = useAuth();

  // ── Portfolio holdings (real data from API)
  const [holdings, setHoldings] = useState<PortfolioHolding[]>([]);
  const [holdingsLoading, setHoldingsLoading] = useState(true);
  const [holdingsError, setHoldingsError] = useState<string | null>(null);

  const loadHoldings = () => {
    if (!token) return;
    setHoldingsLoading(true);
    setHoldingsError(null);
    fetchHoldings(token)
      .then(setHoldings)
      .catch((err) => setHoldingsError(err instanceof Error ? err.message : "Failed to load portfolio."))
      .finally(() => setHoldingsLoading(false));
  };

  useEffect(loadHoldings, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── All PSX stocks (fetched once for the search sheet)
  const [allStocks, setAllStocks] = useState<StockSearchResult[]>([]);
  const [stocksLoading, setStocksLoading] = useState(false);
  const [stocksError, setStocksError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    setStocksLoading(true);
    fetchAllStocks(token)
      .then((r) => setAllStocks(Array.isArray(r) ? r : []))
      .catch((err) => setStocksError(err instanceof Error ? err.message : "Failed to load stocks."))
      .finally(() => setStocksLoading(false));
  }, [token]);

  // ── Bottom-sheet state
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sheetMode, setSheetMode] = useState<SheetMode>("add");
  const [editingHolding, setEditingHolding] = useState<PortfolioHolding | null>(null);
  const [step, setStep] = useState<Step>(1);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<StockSearchResult | null>(null);
  const [mode, setMode] = useState<InputMode>("qtyPrice");
  const [lots, setLots] = useState<Lot[]>([newLot()]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const slideY = useRef(new Animated.Value(700)).current;
  const fadeOverlay = useRef(new Animated.Value(0)).current;

  // ── Derived portfolio totals
  const totalPortfolioValue = holdings.reduce((a, h) => a + (h.current_value ?? h.total_invested ?? 0), 0);
  const totalPortfolioInvested = holdings.reduce((a, h) => a + (h.total_invested ?? 0), 0);
  const todayPct =
    totalPortfolioInvested > 0
      ? ((totalPortfolioValue - totalPortfolioInvested) / totalPortfolioInvested) * 100
      : 0;

  // ── Client-side stock filter
  const filteredStocks = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return allStocks;
    return allStocks.filter(
      (s) =>
        s.symbol.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q) ||
        s.industry.toLowerCase().includes(q),
    );
  }, [allStocks, query]);

  // ── Lots → weighted average (one lot = one purchase; add more for multiple buys)
  const lotsCalc = useMemo(() => calcLotsFromRows(lots, mode), [lots, mode]);

  const reviewCalc = useMemo(() => {
    const curPrice = selected?.current_price != null ? parseNum(String(selected.current_price)) : 0;
    const curValue = lotsCalc.shares * curPrice;
    const pnl = curValue - lotsCalc.invested;
    const ret = lotsCalc.invested > 0 ? (pnl / lotsCalc.invested) * 100 : 0;
    return {
      shares: lotsCalc.shares,
      invested: lotsCalc.invested,
      avgPrice: lotsCalc.avgPrice,
      curValue,
      pnl,
      ret,
      lotCount: lotsCalc.validLotCount,
    };
  }, [lotsCalc, selected?.current_price]);

  const canReview = lotsCalc.validLotCount >= 1 && lotsCalc.shares > 0 && lotsCalc.avgPrice > 0;

  const stepLabel = useMemo(() => {
    if (sheetMode === "edit") {
      if (step === 2) return "Step 1 of 2";
      if (step === 3) return "Step 2 of 2";
      return "";
    }
    return `Step ${step} of 3`;
  }, [sheetMode, step]);

  const showSheetBack = sheetMode === "add" ? step > 1 : step > 2;

  const animateSheetOpen = () => {
    slideY.setValue(700);
    fadeOverlay.setValue(0);
    Animated.parallel([
      Animated.timing(slideY, { toValue: 0, duration: 280, easing: Easing.out(Easing.cubic), useNativeDriver: true }),
      Animated.timing(fadeOverlay, { toValue: 1, duration: 220, easing: Easing.out(Easing.cubic), useNativeDriver: true }),
    ]).start();
  };

  const resetSheetForm = () => {
    setSaving(false);
    setSaveError(null);
    setSaved(false);
    setMode("qtyPrice");
    setLots([newLot()]);
  };

  // ── Sheet open / close
  const openSheet = () => {
    setSheetMode("add");
    setEditingHolding(null);
    setSheetOpen(true);
    setStep(1);
    setQuery("");
    setSelected(null);
    resetSheetForm();
    animateSheetOpen();
  };

  const openEditSheet = (holding: PortfolioHolding) => {
    const stock = holdingToStockResult(holding);
    const qty = parseFloat(holding.quantity);
    const avg = parseFloat(holding.avg_buy_price);

    setSheetMode("edit");
    setEditingHolding(holding);
    setSheetOpen(true);
    setStep(2);
    setQuery("");
    setSelected(stock);
    setMode("qtyPrice");
    setSaving(false);
    setSaveError(null);
    setSaved(false);
    setLots([
      {
        id: newLot().id,
        amountOrShares: Number.isFinite(qty) ? String(qty) : "",
        price: Number.isFinite(avg) ? String(avg) : "",
      },
    ]);
    animateSheetOpen();
  };

  const closeSheet = () => {
    Animated.parallel([
      Animated.timing(slideY, { toValue: 700, duration: 230, easing: Easing.in(Easing.cubic), useNativeDriver: true }),
      Animated.timing(fadeOverlay, { toValue: 0, duration: 190, easing: Easing.in(Easing.cubic), useNativeDriver: true }),
    ]).start(() => {
      setSheetOpen(false);
      setEditingHolding(null);
      setSheetMode("add");
    });
  };

  const goBack = () => {
    if (sheetMode === "edit" && step === 2) {
      closeSheet();
      return;
    }
    setStep((p) => (p > 1 ? ((p - 1) as Step) : p));
  };

  // ── Confirm: POST (add) or PATCH (edit), then refresh holdings
  const handleConfirm = async () => {
    if (!selected || !token) return;
    setSaving(true);
    setSaveError(null);
    try {
      const quantity = Number(reviewCalc.shares.toFixed(2));
      const avg_buy_price = Number(reviewCalc.avgPrice.toFixed(2));

      if (sheetMode === "edit" && editingHolding) {
        const updated = await updateHolding(token, editingHolding.id, { quantity, avg_buy_price });
        setHoldings((prev) => prev.map((h) => (h.id === updated.id ? updated : h)));
      } else {
        await addHolding(token, { symbol_id: selected.symbol_id, quantity, avg_buy_price });
        loadHoldings();
      }

      setSaved(true);
      setTimeout(closeSheet, 1500);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save holding.");
    } finally {
      setSaving(false);
    }
  };

  // ── Delete holding with confirmation
  const handleDelete = (holding: PortfolioHolding) => {
    Alert.alert(
      "Remove Holding",
      `Remove ${holding.ticker} from your portfolio?`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Remove",
          style: "destructive",
          onPress: async () => {
            if (!token) return;
            try {
              await deleteHolding(token, holding.id);
              setHoldings((prev) => prev.filter((h) => h.id !== holding.id));
            } catch {
              Alert.alert("Error", "Failed to remove holding.");
            }
          },
        },
      ],
    );
  };

  // ── Lot helpers
  const updateLot = (id: string, field: "amountOrShares" | "price", value: string) =>
    setLots((prev) => prev.map((l) => (l.id === id ? { ...l, [field]: value } : l)));

  const removeLot = (id: string) =>
    setLots((prev) => (prev.length > 1 ? prev.filter((l) => l.id !== id) : prev));

  const helperLine =
    selected?.last_close != null && selected?.current_price != null
      ? `Last close: ${fmtRs(selected.last_close)}  ·  Current: ${fmtRs(parseNum(String(selected.current_price)))}`
      : "Last close: —  ·  Current: —";

  // ── Step 1: stock search with FlatList
  const renderStockItem = ({ item: stock }: { item: StockSearchResult }) => {
    const isSelected = selected?.symbol === stock.symbol;
    const pos = (stock.change_percent ?? 0) >= 0;
    const price = stock.current_price != null ? parseNum(String(stock.current_price)) : null;
    return (
      <Pressable
        style={[styles.stockRow, isSelected && styles.stockRowSelected]}
        onPress={() => setSelected(stock)}
      >
        <View style={styles.stockRowMain}>
          <View style={styles.rowLeft}>
            <View style={styles.badge}>
              <Text style={styles.badgeText} numberOfLines={1}>{stock.symbol}</Text>
            </View>
            <View style={styles.rowMid}>
              <Text style={styles.stockName}>{stock.name}</Text>
              <Text style={styles.stockIndustry}>{stock.industry}</Text>
            </View>
          </View>
          <View style={styles.rowRight}>
            <Text style={styles.stockPrice}>{price != null ? fmtRs(price) : "—"}</Text>
            {isSelected ? (
              <Check size={16} color={GREEN} strokeWidth={2.8} />
            ) : (
              <View style={[styles.pill, { backgroundColor: pos ? "#E8F8F2" : "#FDECEC" }]}>
                <Text style={[styles.pillText, { color: pos ? GREEN : RED }]}>
                  {stock.change_percent != null ? fmtPct(stock.change_percent) : "—"}
                </Text>
              </View>
            )}
          </View>
        </View>
        <LivePriceUpdated at={stock.price_updated_at} />
      </Pressable>
    );
  };

  const renderStep1 = () => (
    <View style={styles.step1Wrap}>
      <View style={styles.sheetContent}>
        <Text style={styles.sheetTitle}>Add to Portfolio</Text>
        <Text style={styles.sheetSub}>Search and select a PSX stock</Text>
        <View style={styles.searchBox}>
          <Search size={15} color={colors.mutedText} strokeWidth={2} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Search by name or symbol e.g. HBL"
            placeholderTextColor={colors.mutedText}
            style={styles.searchInput}
            autoCorrect={false}
            autoCapitalize="none"
          />
          {stocksLoading && <ActivityIndicator size="small" color={colors.primary} />}
        </View>
      </View>

      {stocksError ? (
        <View style={[styles.errorBox, { marginHorizontal: 16 }]}>
          <Text style={styles.errorText}>{stocksError}</Text>
        </View>
      ) : (
        <FlatList
          data={filteredStocks}
          keyExtractor={(item) => item.symbol}
          renderItem={renderStockItem}
          style={styles.stockList}
          contentContainerStyle={styles.stockListContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
          initialNumToRender={14}
          maxToRenderPerBatch={12}
          windowSize={5}
          removeClippedSubviews
          ListEmptyComponent={
            !stocksLoading ? (
              <Text style={styles.emptyText}>
                {query ? `No results for "${query}"` : "No stocks available."}
              </Text>
            ) : null
          }
        />
      )}

      <View style={styles.step1Footer}>
        <Pressable
          style={[styles.primaryBtn, !selected && styles.btnDisabled]}
          disabled={!selected}
          onPress={() => setStep(2)}
        >
          <Text style={styles.primaryBtnText}>Continue</Text>
        </Pressable>
      </View>
    </View>
  );

  // ── Step 2: purchase lots (one lot = one buy; add rows for multiple purchases)
  const renderStep2 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.sheetTitle} numberOfLines={1}>
        {selected ? `${selected.symbol} — ${selected.name}` : "Purchase details"}
      </Text>
      <Text style={styles.sheetSub}>
        Current price:{" "}
        {selected?.current_price != null
          ? fmtRs(parseNum(String(selected.current_price)))
          : "—"}
      </Text>
      <Text style={styles.lotsHint}>
        {sheetMode === "edit"
          ? "Adjust your lots below. We recalculate weighted average cost from all filled rows."
          : "One purchase = one lot. Bought at different prices? Tap + Add another lot."}
      </Text>

      <View style={styles.chipRow}>
        {(["qtyPrice", "totalInvested"] as InputMode[]).map((m) => (
          <Pressable key={m} style={[styles.chip, mode === m && styles.chipActive]} onPress={() => setMode(m)}>
            <Text style={[styles.chipText, mode === m && styles.chipTextActive]}>
              {m === "qtyPrice" ? "Qty × Price" : "Total Invested"}
            </Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.fieldGroup}>
        {lots.map((lot, idx) => (
          <View key={lot.id} style={styles.lotRow}>
            <Text style={styles.lotLabel}>Lot {idx + 1}</Text>
            <View style={styles.lotInputs}>
              <TextInput
                value={lot.amountOrShares}
                onChangeText={(v) => updateLot(lot.id, "amountOrShares", v)}
                placeholder={mode === "qtyPrice" ? "Shares" : "Amount (Rs.)"}
                placeholderTextColor={colors.mutedText}
                keyboardType="numeric"
                style={[styles.textInput, styles.lotInput]}
              />
              <TextInput
                value={lot.price}
                onChangeText={(v) => updateLot(lot.id, "price", v)}
                placeholder="Price (Rs.)"
                placeholderTextColor={colors.mutedText}
                keyboardType="numeric"
                style={[styles.textInput, styles.lotInput]}
              />
            </View>
            {lots.length > 1 ? (
              <Pressable style={styles.removeBtn} onPress={() => removeLot(lot.id)}>
                <X size={13} color={colors.mutedText} strokeWidth={2.4} />
              </Pressable>
            ) : (
              <View style={styles.removePlaceholder} />
            )}
          </View>
        ))}

        <Pressable style={styles.addLotBtn} onPress={() => setLots((prev) => [...prev, newLot()])}>
          <Text style={styles.addLotText}>+ Add another lot</Text>
        </Pressable>

        <View style={styles.helperRow}>
          <Info size={13} color={colors.mutedText} strokeWidth={2} />
          <Text style={styles.helperText}>{helperLine}</Text>
        </View>

        <View style={styles.divider} />
        {[
          { label: "Lots entered", value: String(lotsCalc.validLotCount) },
          { label: "Calculated average", value: fmtRs(lotsCalc.avgPrice) },
          { label: "Total shares", value: Math.round(lotsCalc.shares).toLocaleString("en-PK") },
          { label: "Total invested", value: fmtRs(lotsCalc.invested) },
        ].map(({ label, value }) => (
          <View key={label} style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>{label}</Text>
            <Text style={styles.summaryValue}>{value}</Text>
          </View>
        ))}
      </View>

      <Pressable
        style={[styles.primaryBtn, !canReview && styles.btnDisabled, { marginTop: 6 }]}
        onPress={() => setStep(3)}
        disabled={!canReview}
      >
        <Text style={styles.primaryBtnText}>Review Position</Text>
      </Pressable>
    </View>
  );

  // ── Step 3: review + confirm
  const pnlPos = reviewCalc.pnl >= 0;

  const renderStep3 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.sheetTitle}>Review Your Position</Text>
      <Text style={styles.sheetSub}>
        {sheetMode === "edit" ? "Confirm your changes before saving" : "Confirm the details before adding"}
      </Text>

      <View style={styles.reviewCard}>
        <View style={styles.reviewTop}>
          <View style={styles.badgeLarge}>
            <Text style={styles.badgeLargeText}>{selected?.symbol ?? "—"}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.reviewName}>{selected?.name ?? "—"}</Text>
            <Text style={styles.reviewIndustry}>{selected?.industry ?? "—"}</Text>
          </View>
        </View>

        <View style={styles.reviewGrid}>
          {[
            { label: "Shares", value: Math.round(reviewCalc.shares).toLocaleString("en-PK") },
            { label: "Avg buy price", value: fmtRs(reviewCalc.avgPrice) },
            { label: "Total invested", value: fmtRs(reviewCalc.invested) },
            { label: "Current price", value: selected?.current_price != null ? fmtRs(parseNum(String(selected.current_price))) : "—" },
          ].map(({ label, value }) => (
            <View key={label} style={styles.metricRow}>
              <Text style={styles.metricLabel}>{label}</Text>
              <Text style={styles.metricValue}>{value}</Text>
            </View>
          ))}
        </View>

        <View style={styles.reviewDivider} />

        <View style={styles.metricRow}>
          <Text style={styles.metricLabel}>Current value</Text>
          <Text style={styles.metricValue}>{fmtRs(reviewCalc.curValue)}</Text>
        </View>
        <View style={styles.metricRow}>
          <Text style={styles.metricLabel}>Unrealized P&amp;L</Text>
          <Text style={[styles.metricValue, { color: pnlPos ? GREEN : RED }]}>
            {`${pnlPos ? "+" : "-"}${fmtRs(Math.abs(reviewCalc.pnl))}`}
          </Text>
        </View>
        <View style={styles.metricRow}>
          <Text style={styles.metricLabel}>Return</Text>
          <View style={[styles.pill, { backgroundColor: pnlPos ? "#E8F8F2" : "#FDECEC" }]}>
            <Text style={[styles.pillText, { color: pnlPos ? GREEN : RED }]}>{fmtPct(reviewCalc.ret)}</Text>
          </View>
        </View>
        <View style={styles.metricRow}>
          <Text style={styles.metricLabel}>Today&apos;s move</Text>
          <Text style={[styles.metricValue, { color: (selected?.change_percent ?? 0) >= 0 ? GREEN : RED }]}>
            {fmtPct(selected?.change_percent ?? 0)}
          </Text>
        </View>
      </View>

      <Text style={styles.addedAsText}>
        {reviewCalc.lotCount} lot{reviewCalc.lotCount !== 1 ? "s" : ""} · weighted average ·{" "}
        {mode === "qtyPrice" ? "Qty × Price" : "Total invested"}
      </Text>

      <View style={styles.noteBox}>
        <Text style={styles.noteText}>
          ⚠ P&amp;L is calculated based on your entered buy price. Update anytime from your portfolio.
        </Text>
      </View>

      {saveError && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{saveError}</Text>
        </View>
      )}

      {saved ? (
        <View style={styles.successWrap}>
          <CheckCircle2 size={34} color={GREEN} strokeWidth={2} />
          <Text style={styles.successText}>
            {selected?.symbol}{" "}
            {sheetMode === "edit" ? "updated in your portfolio" : "added to your portfolio"}
          </Text>
        </View>
      ) : (
        <View style={styles.actionRow}>
          <Pressable style={styles.editBtn} onPress={() => setStep(2)}>
            <Text style={styles.editBtnText}>Edit</Text>
          </Pressable>
          <Pressable
            style={[styles.primaryBtn, styles.flex1, saving && styles.btnDisabled]}
            onPress={handleConfirm}
            disabled={saving}
          >
            {saving ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <Text style={styles.primaryBtnText}>
                {sheetMode === "edit" ? "Save Changes" : "Add to Portfolio"}
              </Text>
            )}
          </Pressable>
        </View>
      )}
    </View>
  );

  // ── Main render
  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <Pressable style={styles.backBtn} onPress={() => router.back()} hitSlop={10}>
          <ChevronLeft size={22} color={colors.primary} strokeWidth={2} />
        </Pressable>
        <Text style={styles.headerTitle}>Manage Portfolio</Text>
        <View style={styles.backBtn}>
          <Landmark size={19} color={colors.primary} strokeWidth={1.8} />
        </View>
      </View>

      {holdingsLoading ? (
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : holdingsError ? (
        <View style={styles.loadingWrap}>
          <Text style={styles.errorText}>{holdingsError}</Text>
          <Pressable onPress={loadHoldings} style={styles.retryBtn}>
            <Text style={styles.retryText}>Retry</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView style={styles.scroll} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          {/* Portfolio value card — only shown when there are holdings */}
          {holdings.length > 0 && (
            <>
              <View style={styles.valueCard}>
                <Text style={styles.valueLabel}>TOTAL PORTFOLIO VALUE</Text>
                <Text style={styles.valueAmount}>{fmtRs(totalPortfolioValue)}</Text>
                <Text style={[styles.valueChange, { color: todayPct >= 0 ? "#7DE7B8" : "#FFB6B5" }]}>
                  {todayPct >= 0 ? "↑" : "↓"} {fmtPct(Math.abs(todayPct))} Today
                </Text>
              </View>

              <View style={styles.sectionHeader}>
                <Text style={styles.sectionTitle}>Your Holdings</Text>
                <Text style={styles.sectionRight}>{holdings.length} Stock{holdings.length !== 1 ? "s" : ""}</Text>
              </View>

              {holdings.map((h) => (
                <View key={h.id} style={styles.holdingCard}>
                  <View style={styles.holdingTop}>
                    <View style={styles.rowLeft}>
                      <View style={styles.badge}>
                        <Text style={styles.badgeText} numberOfLines={1}>{h.ticker}</Text>
                      </View>
                      <View>
                        <Text style={styles.holdingSymbol}>{h.ticker}</Text>
                        <Text style={styles.holdingCompany}>{h.name}</Text>
                      </View>
                    </View>
                    <View style={styles.holdingActions}>
                      <Pressable style={styles.iconBtn} hitSlop={8} onPress={() => openEditSheet(h)}>
                        <Pencil size={15} color={colors.textSecondary} strokeWidth={2} />
                      </Pressable>
                      <Pressable style={styles.iconBtn} hitSlop={8} onPress={() => handleDelete(h)}>
                        <Trash2 size={15} color={colors.error} strokeWidth={2} />
                      </Pressable>
                    </View>
                  </View>

                  <View style={styles.holdingGrid}>
                    <View style={styles.gridCell}>
                      <Text style={styles.gridLabel}>Quantity</Text>
                      <Text style={styles.gridValue}>{parseFloat(h.quantity).toLocaleString("en-PK")} Shares</Text>
                    </View>
                    <View style={styles.gridCell}>
                      <Text style={styles.gridLabel}>Avg Buy Price</Text>
                      <Text style={styles.gridValue}>{fmtRs(parseFloat(h.avg_buy_price))}</Text>
                    </View>
                    <View style={styles.gridCell}>
                      <Text style={styles.gridLabel}>Total Invested</Text>
                      <Text style={styles.gridValue}>{h.total_invested != null ? fmtRs(h.total_invested) : "—"}</Text>
                    </View>
                    <View style={styles.gridCell}>
                      <Text style={styles.gridLabel}>Current Value</Text>
                      <Text style={[styles.gridValue, styles.gridValueBold]}>
                        {h.current_value != null ? fmtRs(h.current_value) : "—"}
                      </Text>
                    </View>
                  </View>
                  <LivePriceUpdated at={h.price_updated_at} />
                </View>
              ))}
            </>
          )}

          {/* Empty state */}
          {holdings.length === 0 && (
            <View style={styles.emptyState}>
              <View style={styles.emptyIcon}>
                <Briefcase size={40} color={colors.primary} strokeWidth={1.5} />
              </View>
              <Text style={styles.emptyTitle}>No holdings yet</Text>
              <Text style={styles.emptySub}>Add your first PSX stock to start tracking your portfolio</Text>
            </View>
          )}
        </ScrollView>
      )}

      <View style={styles.ctaWrap}>
        <Pressable style={styles.addBtn} onPress={openSheet}>
          <Plus size={17} color="#FFFFFF" strokeWidth={2.5} />
          <Text style={styles.addBtnText}>Add Stock</Text>
        </Pressable>
      </View>

      {/* Bottom sheet */}
      <Modal visible={sheetOpen} transparent animationType="none" onRequestClose={closeSheet}>
        <Animated.View style={[styles.overlay, { opacity: fadeOverlay }]}>
          <Pressable style={StyleSheet.absoluteFillObject} onPress={closeSheet} />
        </Animated.View>

        <Animated.View style={[styles.sheet, { transform: [{ translateY: slideY }] }]}>
          <View style={styles.handle} />

          <View style={styles.sheetNav}>
            {showSheetBack ? (
              <Pressable style={styles.navBtn} onPress={goBack} hitSlop={10}>
                <ChevronLeft size={20} color={colors.textSecondary} strokeWidth={2} />
              </Pressable>
            ) : (
              <View style={styles.navBtn} />
            )}
            <Text style={styles.stepText}>{stepLabel}</Text>
            <Pressable style={styles.navBtn} onPress={closeSheet} hitSlop={10}>
              <X size={19} color={colors.textSecondary} strokeWidth={2} />
            </Pressable>
          </View>

          {step === 1 && renderStep1()}
          {(step === 2 || step === 3) && (
            <ScrollView
              style={styles.sheetScroll}
              contentContainerStyle={styles.sheetContent}
              showsVerticalScrollIndicator={false}
              keyboardShouldPersistTaps="handled"
            >
              {step === 2 && renderStep2()}
              {step === 3 && renderStep3()}
            </ScrollView>
          )}
        </Animated.View>
      </Modal>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  scroll: { flex: 1 },
  content: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 16, gap: 12 },

  // ── Header
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 18,
    paddingVertical: 13,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
    backgroundColor: colors.background,
  },
  backBtn: { width: 36, height: 36, alignItems: "center", justifyContent: "center" },
  headerTitle: { fontFamily: fonts.heading, fontSize: 17, color: colors.text, letterSpacing: -0.3 },

  // ── Loading / error / empty
  loadingWrap: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12 },
  retryBtn: {
    paddingHorizontal: 20, paddingVertical: 9,
    borderRadius: 8, backgroundColor: colors.bgPrimaryLight,
  },
  retryText: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.primary },
  emptyState: { flex: 1, alignItems: "center", justifyContent: "center", paddingTop: 60, gap: 10 },
  emptyIcon: {
    width: 72, height: 72, borderRadius: 36,
    backgroundColor: colors.bgPrimaryLight,
    alignItems: "center", justifyContent: "center", marginBottom: 4,
  },
  emptyTitle: { fontFamily: fonts.heading, fontSize: 17, color: colors.text, letterSpacing: -0.3 },
  emptySub: { fontFamily: fonts.body, fontSize: 13, color: colors.mutedText, textAlign: "center", paddingHorizontal: 32 },

  // ── Portfolio value card
  valueCard: {
    backgroundColor: colors.primary,
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 16,
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.14, shadowRadius: 6, elevation: 3,
  },
  valueLabel: { fontFamily: fonts.bodyMedium, fontSize: 10, color: "rgba(255,255,255,0.70)", letterSpacing: 0.8, marginBottom: 4 },
  valueAmount: { fontFamily: fonts.heading, fontSize: 26, color: "#FFFFFF", letterSpacing: -0.6, marginBottom: 5 },
  valueChange: { fontFamily: fonts.bodyMedium, fontSize: 13 },

  // ── Section header
  sectionHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sectionTitle: { fontFamily: fonts.heading, fontSize: 16, color: colors.text, letterSpacing: -0.2 },
  sectionRight: { fontFamily: fonts.bodyMedium, fontSize: 12, color: colors.mutedText },

  // ── Holding card
  holdingCard: {
    borderRadius: 12, borderWidth: 1, borderColor: colors.borderLight,
    backgroundColor: colors.background, padding: 14, gap: 12,
    shadowColor: "#000", shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04, shadowRadius: 3, elevation: 1,
  },
  holdingTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  holdingSymbol: { fontFamily: fonts.heading, fontSize: 15, color: colors.text, marginBottom: 1 },
  holdingCompany: { fontFamily: fonts.body, fontSize: 12, color: colors.mutedText },
  holdingActions: { flexDirection: "row", alignItems: "center", gap: 8 },
  iconBtn: { width: 28, height: 28, alignItems: "center", justifyContent: "center" },
  holdingGrid: { flexDirection: "row", flexWrap: "wrap", rowGap: 10 },
  gridCell: { width: "50%" },
  gridLabel: { fontFamily: fonts.body, fontSize: 12, color: colors.mutedText, marginBottom: 2 },
  gridValue: { fontFamily: fonts.bodyMedium, fontSize: 14, color: colors.text },
  gridValueBold: { fontFamily: fonts.heading },

  // ── Shared badge
  rowLeft: { flexDirection: "row", alignItems: "center", gap: 10, flex: 1 },
  rowMid: { flex: 1 },
  rowRight: { alignItems: "flex-end", gap: 4 },
  badge: {
    width: 36, height: 36, borderRadius: 9,
    backgroundColor: colors.primary, alignItems: "center", justifyContent: "center",
  },
  badgeText: { fontFamily: fonts.heading, color: "#FFFFFF", fontSize: 9 },

  // ── Add Stock button
  ctaWrap: {
    paddingHorizontal: 16, paddingVertical: 12,
    borderTopWidth: 1, borderTopColor: colors.borderLight,
    backgroundColor: colors.background,
  },
  addBtn: {
    height: 50, borderRadius: 10, backgroundColor: colors.primary,
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 7,
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12, shadowRadius: 5, elevation: 3,
  },
  addBtnText: { fontFamily: fonts.bodyMedium, color: "#FFFFFF", fontSize: 15, letterSpacing: 0.1 },

  // ── Overlay & sheet
  overlay: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(10,22,36,0.55)" },
  sheet: {
    position: "absolute", left: 0, right: 0, bottom: 0,
    height: "88%",
    backgroundColor: colors.background,
    borderTopLeftRadius: 20, borderTopRightRadius: 20,
    shadowColor: "#000", shadowOffset: { width: 0, height: -3 },
    shadowOpacity: 0.10, shadowRadius: 10, elevation: 14,
  },
  handle: {
    width: 48, height: 4, borderRadius: 999, backgroundColor: colors.borderLight,
    alignSelf: "center", marginTop: 10, marginBottom: 4,
  },
  sheetNav: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 14, paddingVertical: 8,
    borderBottomWidth: 1, borderBottomColor: colors.borderLight,
  },
  navBtn: { width: 32, height: 32, alignItems: "center", justifyContent: "center" },
  stepText: { fontFamily: fonts.bodyMedium, fontSize: 12, color: colors.mutedText },

  // ── Step 1 layout (FlatList-based)
  step1Wrap: { flex: 1, flexDirection: "column" },
  sheetScroll: { flex: 1 },
  sheetContent: { paddingHorizontal: 16, paddingTop: 14, paddingBottom: 24, gap: 0 },
  step1Footer: {
    paddingHorizontal: 16, paddingTop: 10, paddingBottom: 50,
    borderTopWidth: 1, borderTopColor: colors.borderLight,
    backgroundColor: colors.background,
  },
  stockList: { flex: 1, minHeight: 100 },
  stockListContent: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 6, gap: 6 },

  // ── Sheet typography
  stepContent: { gap: 12 },
  sheetTitle: { fontFamily: fonts.heading, fontSize: 19, color: colors.text, letterSpacing: -0.4 },
  sheetSub: { fontFamily: fonts.body, fontSize: 13, color: colors.mutedText, marginTop: -4 },
  lotsHint: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
    lineHeight: 17,
    marginTop: -2,
  },

  // ── Search
  searchBox: {
    height: 44, borderRadius: 9, borderWidth: 1, borderColor: colors.border,
    backgroundColor: colors.bgLight, paddingHorizontal: 11,
    flexDirection: "row", alignItems: "center", gap: 8,
  },
  searchInput: { flex: 1, fontFamily: fonts.body, fontSize: 13, color: colors.text, paddingVertical: 0 },

  // ── Stock row
  stockRow: {
    borderWidth: 1, borderColor: colors.borderLight, borderRadius: 10,
    paddingVertical: 9, paddingHorizontal: 10,
    gap: 4,
  },
  stockRowMain: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  stockRowSelected: {
    backgroundColor: colors.bgPrimaryLight, borderColor: colors.themeMedium,
    borderLeftWidth: 3, borderLeftColor: GREEN,
  },
  stockName: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.text, marginBottom: 1 },
  stockIndustry: { fontFamily: fonts.body, fontSize: 11, color: colors.mutedText },
  stockPrice: { fontFamily: fonts.heading, fontSize: 12, color: colors.text },
  pill: { borderRadius: 999, paddingHorizontal: 7, paddingVertical: 2 },
  pillText: { fontFamily: fonts.bodyMedium, fontSize: 10 },

  emptyText: { fontFamily: fonts.body, fontSize: 13, color: colors.mutedText, textAlign: "center", paddingVertical: 16 },
  errorBox: { borderRadius: 8, backgroundColor: "#FEE2E2", paddingHorizontal: 12, paddingVertical: 10 },
  errorText: { fontFamily: fonts.body, fontSize: 12, color: "#991B1B", lineHeight: 17 },

  // ── Purchase tabs
  tabRow: { flexDirection: "row", borderBottomWidth: 1, borderBottomColor: colors.borderLight },
  tabItem: { flex: 1, alignItems: "center", paddingBottom: 9, borderBottomWidth: 2, borderBottomColor: "transparent" },
  tabItemActive: { borderBottomColor: GREEN },
  tabText: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.mutedText },
  tabTextActive: { color: colors.text },

  // ── Mode chips
  chipRow: { flexDirection: "row", gap: 8 },
  chip: { flex: 1, height: 38, borderRadius: 9, backgroundColor: colors.bgSecondaryLight, alignItems: "center", justifyContent: "center" },
  chipActive: { backgroundColor: colors.primary },
  chipText: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.textSecondary },
  chipTextActive: { color: "#FFFFFF" },

  // ── Form fields
  fieldGroup: { gap: 10 },
  fieldItem: { gap: 5 },
  fieldLabel: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.textSecondary },
  textInput: {
    height: 46, borderRadius: 9, borderWidth: 1, borderColor: colors.border,
    backgroundColor: colors.bgLight, paddingHorizontal: 12,
    fontFamily: fonts.body, fontSize: 14, color: colors.text,
  },
  helperRow: {
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: colors.bgPrimaryLight, borderRadius: 7,
    paddingHorizontal: 10, paddingVertical: 7,
  },
  helperText: { flex: 1, fontFamily: fonts.body, fontSize: 12, color: colors.textSecondary },

  // ── Lots
  lotRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  lotLabel: { width: 38, fontFamily: fonts.bodyMedium, fontSize: 11, color: colors.mutedText },
  lotInputs: { flex: 1, flexDirection: "row", gap: 6 },
  lotInput: { flex: 1, height: 42 },
  removeBtn: { width: 24, height: 24, borderRadius: 12, backgroundColor: colors.bgSecondaryLight, alignItems: "center", justifyContent: "center" },
  removePlaceholder: { width: 24, height: 24 },
  addLotBtn: { alignSelf: "flex-start", marginTop: 2 },
  addLotText: { fontFamily: fonts.bodyMedium, fontSize: 13, color: GREEN },
  divider: { height: 1, backgroundColor: colors.borderLight, marginVertical: 6 },
  summaryRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  summaryLabel: { fontFamily: fonts.body, fontSize: 12, color: colors.mutedText },
  summaryValue: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.text },

  // ── Review card
  reviewCard: {
    borderRadius: 12, borderWidth: 1, borderColor: colors.bgPrimaryLight,
    backgroundColor: colors.bgPrimaryLight, padding: 12, gap: 8,
  },
  reviewTop: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 2 },
  badgeLarge: { width: 42, height: 42, borderRadius: 10, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
  badgeLargeText: { fontFamily: fonts.heading, color: "#FFFFFF", fontSize: 11 },
  reviewName: { fontFamily: fonts.bodyMedium, fontSize: 14, color: colors.text },
  reviewIndustry: { fontFamily: fonts.body, fontSize: 11, color: colors.mutedText },
  reviewGrid: { gap: 4 },
  metricRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: 22 },
  metricLabel: { fontFamily: fonts.body, fontSize: 12, color: colors.mutedText },
  metricValue: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.text },
  reviewDivider: { height: 1, backgroundColor: colors.borderLight, marginVertical: 2 },

  addedAsText: { fontFamily: fonts.body, fontSize: 11, color: colors.mutedText, textAlign: "center", marginTop: 2 },
  noteBox: { borderLeftWidth: 3, borderLeftColor: "#D97706", backgroundColor: "#FFFBEB", borderRadius: 7, paddingHorizontal: 10, paddingVertical: 8 },
  noteText: { fontFamily: fonts.body, fontSize: 12, color: "#92400E", lineHeight: 17 },

  // ── Action buttons
  actionRow: { flexDirection: "row", gap: 8, marginTop: 2 },
  flex1: { flex: 1 },
  editBtn: {
    flex: 1, height: 46, borderRadius: 9,
    borderWidth: 1, borderColor: colors.border,
    backgroundColor: colors.background, alignItems: "center", justifyContent: "center",
  },
  editBtnText: { fontFamily: fonts.bodyMedium, fontSize: 14, color: colors.textSecondary },
  primaryBtn: { height: 46, borderRadius: 9, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
  primaryBtnText: { fontFamily: fonts.bodyMedium, fontSize: 14, color: "#FFFFFF" },
  btnDisabled: { opacity: 0.4 },

  successWrap: { alignItems: "center", paddingVertical: 12, gap: 6 },
  successText: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.primary, textAlign: "center" },
});
