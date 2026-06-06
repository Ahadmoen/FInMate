import InsightsPagination from "@/components/insights/InsightsPagination";
import MarketSentimentCard from "@/components/news/MarketSentimentCard";
import NewsArticleCard from "@/components/news/NewsArticleCard";
import NewsFilterBar from "@/components/news/NewsFilterBar";
import NewsSearchBar from "@/components/news/NewsSearchBar";
import ScreenHeader from "@/components/ui/ScreenHeader";
import { useAuth } from "@/context/AuthContext";
import {
  fetchMarketSentimentIndex,
  fetchNewsFeed,
  fetchNewsFilters,
  fetchNewsSearch,
  type MarketSentimentIndex,
  type NewsArticle,
  type NewsFilterOption,
} from "@/services/news";
import { colors, fonts } from "@/styles/global";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

const TEAL = "#0E4D53";

const DEFAULT_SENTIMENTS: NewsFilterOption[] = [{ id: "all", label: "All Sentiment" }];
const DEFAULT_INDUSTRIES: NewsFilterOption[] = [{ id: "all", label: "All Industries" }];
const DEFAULT_STOCKS: NewsFilterOption[] = [{ id: "all", label: "All Stocks" }];

const DEFAULT_INDEX: MarketSentimentIndex = {
  value: 50,
  change_pct: 0,
  progress: 50,
  phase: "Neutral",
  message: "Loading market sentiment…",
  window_days: 7,
};

export default function NewsScreen() {
  const { token } = useAuth();

  const [filtersVisible, setFiltersVisible] = useState(false);
  const [sentimentId, setSentimentId] = useState("all");
  const [industryId, setIndustryId] = useState("all");
  const [stockId, setStockId] = useState("all");
  const [page, setPage] = useState(1);

  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const [sentiments, setSentiments] = useState(DEFAULT_SENTIMENTS);
  const [industries, setIndustries] = useState(DEFAULT_INDUSTRIES);
  const [stocks, setStocks] = useState(DEFAULT_STOCKS);

  const [sentimentIndex, setSentimentIndex] = useState<MarketSentimentIndex>(DEFAULT_INDEX);
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [indexLoading, setIndexLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isSearchActive = searchQuery.trim().length > 0;

  useEffect(() => {
    if (!token) return;
    fetchNewsFilters(token)
      .then((f) => {
        setSentiments(f.sentiments);
        setIndustries(f.industries);
        setStocks(f.stocks);
      })
      .catch(() => {
        /* keep defaults */
      });
  }, [token]);

  const loadIndex = useCallback(async () => {
    if (!token) return;
    setIndexLoading(true);
    try {
      const data = await fetchMarketSentimentIndex(token);
      setSentimentIndex(data);
    } catch {
      /* keep previous / default */
    } finally {
      setIndexLoading(false);
    }
  }, [token]);

  const loadFeed = useCallback(
    async (isRefresh = false) => {
      if (!token || isSearchActive) return;
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      setError(null);
      try {
        const data = await fetchNewsFeed(token, {
          sentiment: sentimentId,
          industry: industryId,
          stock: stockId,
          page,
        });
        setArticles(data.results);
        setTotalPages(Math.max(1, data.total_pages));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load news.");
        setArticles([]);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [token, sentimentId, industryId, stockId, page, isSearchActive],
  );

  const loadSearch = useCallback(
    async (isRefresh = false) => {
      if (!token || !isSearchActive) return;
      if (isRefresh) setRefreshing(true);
      else setSearching(true);
      setError(null);
      try {
        const data = await fetchNewsSearch(token, {
          q: searchQuery,
          sentiment: sentimentId,
          industry: industryId,
          stock: stockId,
          page,
        });
        setArticles(data.results);
        setTotalPages(Math.max(1, data.total_pages));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to search news.");
        setArticles([]);
      } finally {
        setSearching(false);
        setRefreshing(false);
      }
    },
    [token, searchQuery, sentimentId, industryId, stockId, page, isSearchActive],
  );

  useEffect(() => {
    loadIndex();
  }, [loadIndex]);

  useEffect(() => {
    if (isSearchActive) {
      loadSearch();
    } else {
      loadFeed();
    }
  }, [isSearchActive, loadSearch, loadFeed]);

  const onRefresh = useCallback(() => {
    if (!isSearchActive) {
      loadIndex();
    }
    if (isSearchActive) {
      loadSearch(true);
    } else {
      loadFeed(true);
    }
  }, [isSearchActive, loadIndex, loadSearch, loadFeed]);

  const submitSearch = useCallback(() => {
    const q = searchInput.trim();
    if (!q) return;
    setArticles([]);
    setSearchQuery(q);
    setPage(1);
  }, [searchInput]);

  const exitSearch = useCallback(() => {
    setSearchInput("");
    setSearchQuery("");
    setPage(1);
    setError(null);
    setArticles([]);
    setLoading(true);
  }, []);

  const onSentimentChange = (id: string) => {
    setSentimentId(id);
    setPage(1);
  };
  const onIndustryChange = (id: string) => {
    setIndustryId(id);
    setPage(1);
  };
  const onStockChange = (id: string) => {
    setStockId(id);
    setPage(1);
  };

  const clearFilters = useCallback(() => {
    setSentimentId("all");
    setIndustryId("all");
    setStockId("all");
    setPage(1);
  }, []);

  const hasActiveFilters =
    sentimentId !== "all" || industryId !== "all" || stockId !== "all";

  const listLoading = isSearchActive ? searching : loading;

  const listHeader = (
    <>
      <NewsSearchBar
        value={searchInput}
        onChangeText={setSearchInput}
        onSubmit={submitSearch}
        loading={searching}
      />
      <NewsFilterBar
        visible={filtersVisible}
        onToggleVisible={() => setFiltersVisible((v) => !v)}
        sentiments={sentiments}
        industries={industries}
        stocks={stocks}
        sentimentId={sentimentId}
        industryId={industryId}
        stockId={stockId}
        onSentimentChange={onSentimentChange}
        onIndustryChange={onIndustryChange}
        onStockChange={onStockChange}
        onClearFilters={clearFilters}
        hasActiveFilters={hasActiveFilters}
      />
      
      {!isSearchActive ? (
        indexLoading ? (
          <View style={styles.indexLoader}>
            <ActivityIndicator color={TEAL} size="large" />
          </View>
        ) : (
          <MarketSentimentCard data={sentimentIndex} />
        )
      ) : null}
    </>
  );

  const listFooter = (
    <InsightsPagination page={page} totalPages={totalPages} onPageChange={setPage} />
  );

  const emptyComponent = () => {
    if (listLoading) {
      return <ActivityIndicator size="large" color={TEAL} style={styles.loader} />;
    }
    if (isSearchActive) {
      return (
        <View style={styles.emptySearch}>
          <Text style={styles.emptyText}>
            {error ?? `No headlines found for "${searchQuery}".`}
          </Text>
          <Pressable style={styles.backBtn} onPress={exitSearch}>
            <Text style={styles.backBtnText}>Back to News</Text>
          </Pressable>
        </View>
      );
    }
    return (
      <Text style={styles.emptyText}>
        {error ?? "No news articles match your filters."}
      </Text>
    );
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScreenHeader />

      <FlatList
        data={articles}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <NewsArticleCard article={item} />}
        contentContainerStyle={styles.listContent}
        ListHeaderComponent={listHeader}
        ListFooterComponent={listFooter}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={TEAL} />
        }
        ListEmptyComponent={emptyComponent()}
        showsVerticalScrollIndicator={false}
        initialNumToRender={10}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  listContent: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 100,
  },
  indexLoader: {
    height: 140,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  loader: { marginTop: 40 },
  emptySearch: {
    alignItems: "center",
    marginTop: 32,
    gap: 16,
    paddingHorizontal: 16,
  },
  emptyText: {
    fontFamily: fonts.body,
    fontSize: 14,
    color: "#6B7280",
    textAlign: "center",
  },
  backBtn: {
    backgroundColor: TEAL,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 24,
  },
  backBtnText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: "#FFFFFF",
  },
});
