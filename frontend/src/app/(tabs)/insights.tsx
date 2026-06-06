import InsightStockCard from "@/components/insights/InsightStockCard";
import InsightsFilterBar from "@/components/insights/InsightsFilterBar";
import InsightsPagination from "@/components/insights/InsightsPagination";
import ScreenHeader from "@/components/ui/ScreenHeader";
import { useAuth } from "@/context/AuthContext";
import {
  fetchInsightsFilters,
  fetchInsightsStocks,
  type InsightStockCard as InsightStockCardData,
  type InsightsFilterOption,
} from "@/services/insights";
import { fonts } from "@/styles/global";
import { useRouter } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

const BG = "#FFFFFF";
const TEAL = "#0E4D53";

const DEFAULT_SECTORS: InsightsFilterOption[] = [{ id: "all", label: "All Sectors" }];
const DEFAULT_TRENDS: InsightsFilterOption[] = [{ id: "all", label: "All Signals" }];
const DEFAULT_SORT: InsightsFilterOption[] = [{ id: "name", label: "Sort by Name" }];

export default function InsightsTabScreen() {
  const { token } = useAuth();
  const router = useRouter();

  const [filtersVisible, setFiltersVisible] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [sectorId, setSectorId] = useState("all");
  const [trendId, setTrendId] = useState("all");
  const [sortId, setSortId] = useState("name");
  const [page, setPage] = useState(1);

  const [sectors, setSectors] = useState(DEFAULT_SECTORS);
  const [trends, setTrends] = useState(DEFAULT_TRENDS);
  const [sortOptions, setSortOptions] = useState(DEFAULT_SORT);

  const [stocks, setStocks] = useState<InsightStockCardData[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearchQuery(searchInput.trim());
      setPage(1);
    }, 350);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [searchInput]);

  useEffect(() => {
    if (!token) return;
    fetchInsightsFilters(token)
      .then((f) => {
        setSectors(f.sectors);
        setTrends(f.trends);
        setSortOptions(f.sort_options);
      })
      .catch(() => {
        /* keep defaults */
      });
  }, [token]);

  const loadStocks = useCallback(
    async (isRefresh = false) => {
      if (!token) return;
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      setError(null);
      try {
        const data = await fetchInsightsStocks(token, {
          q: searchQuery,
          sector: sectorId,
          trend: trendId,
          sort: sortId,
          page,
        });
        setStocks(data.results);
        setTotalPages(Math.max(1, data.total_pages));
        setCount(data.count);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load insights.");
        setStocks([]);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [token, searchQuery, sectorId, trendId, sortId, page],
  );

  useEffect(() => {
    loadStocks();
  }, [loadStocks]);

  const openDetail = useCallback(
    (item: InsightStockCardData) => {
      router.push({
        pathname: "/stock-insight/[ticker]",
        params: {
          ticker: item.ticker,
          symbol_id: item.symbol_id,
          company_name: item.company_name,
          sector: item.sector,
          close: item.close != null ? String(item.close) : "",
          change_pct: item.change_pct != null ? String(item.change_pct) : "",
          signal: item.signal ?? "",
          signal_label: item.signal_label ?? "",
          health_display: item.health_display ?? "",
          confidence_display: item.confidence_display ?? "",
          rsi14: item.rsi14 != null ? String(item.rsi14) : "",
        },
      });
    },
    [router],
  );

  const onSectorChange = (id: string) => {
    setSectorId(id);
    setPage(1);
  };
  const onTrendChange = (id: string) => {
    setTrendId(id);
    setPage(1);
  };
  const onSortChange = (id: string) => {
    setSortId(id);
    setPage(1);
  };

  const clearFilters = useCallback(() => {
    setSearchInput("");
    setSearchQuery("");
    setSectorId("all");
    setTrendId("all");
    setSortId("name");
    setPage(1);
  }, []);

  const hasActiveFilters =
    searchInput.trim() !== "" ||
    sectorId !== "all" ||
    trendId !== "all" ||
    sortId !== "name";

  const renderItem = useCallback(
    ({ item }: { item: InsightStockCardData }) => (
      <InsightStockCard data={item} onPress={() => openDetail(item)} onIconPress={() => openDetail(item)} />
    ),
    [openDetail],
  );

  const listHeader = (
    <InsightsFilterBar
      visible={filtersVisible}
      onToggleVisible={() => setFiltersVisible((v) => !v)}
      search={searchInput}
      onSearchChange={setSearchInput}
      sectors={sectors}
      trends={trends}
      sortOptions={sortOptions}
      sectorId={sectorId}
      trendId={trendId}
      sortId={sortId}
      onSectorChange={onSectorChange}
      onTrendChange={onTrendChange}
      onSortChange={onSortChange}
      onClearFilters={clearFilters}
      hasActiveFilters={hasActiveFilters}
    />
  );

  const listFooter = (
    <>
      {!loading && stocks.length > 0 && count > stocks.length ? (
        <View style={styles.loadedHint}>
          <Text style={styles.loadedHintText}>
            {count} stocks with live data · page {page} of {totalPages}
          </Text>
        </View>
      ) : null}
      <InsightsPagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </>
  );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScreenHeader />
      <FlatList
        data={stocks}
        keyExtractor={(item) => item.symbol_id}
        renderItem={renderItem}
        contentContainerStyle={styles.listContent}
        ListHeaderComponent={listHeader}
        ListFooterComponent={listFooter}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => loadStocks(true)} tintColor={TEAL} />
        }
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator size="large" color={TEAL} style={styles.loader} />
          ) : (
            <Text style={styles.emptyText}>
              {error ?? (searchQuery ? `No results for "${searchQuery}"` : "No stocks available.")}
            </Text>
          )
        }
        showsVerticalScrollIndicator={false}
        initialNumToRender={10}
        maxToRenderPerBatch={10}
        windowSize={5}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  listContent: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 100,
  },
  loader: { marginTop: 48 },
  emptyText: {
    fontFamily: fonts.body,
    fontSize: 14,
    color: "#6B7280",
    textAlign: "center",
    marginTop: 40,
  },
  loadedHint: {
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: "#C5D5D9",
    borderRadius: 12,
    padding: 14,
    alignItems: "center",
    marginTop: 4,
    marginBottom: 8,
  },
  loadedHintText: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: "#6B7280",
    letterSpacing: 0.3,
  },
});
