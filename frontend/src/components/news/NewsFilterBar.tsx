import type { NewsFilterOption } from "@/services/news";
import { fonts } from "@/styles/global";
import { ChevronDown, RotateCcw, SlidersHorizontal } from "lucide-react-native";
import { useState } from "react";
import {
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

const TEAL = "#0E4D53";
const TEAL_LIGHT = "#E5EBED";

type DropdownKind = "sentiment" | "industry" | "stock" | null;

type Props = {
  visible: boolean;
  onToggleVisible: () => void;
  sentiments: NewsFilterOption[];
  industries: NewsFilterOption[];
  stocks: NewsFilterOption[];
  sentimentId: string;
  industryId: string;
  stockId: string;
  onSentimentChange: (id: string) => void;
  onIndustryChange: (id: string) => void;
  onStockChange: (id: string) => void;
  onClearFilters?: () => void;
  hasActiveFilters?: boolean;
};

export default function NewsFilterBar({
  visible,
  onToggleVisible,
  sentiments,
  industries,
  stocks,
  sentimentId,
  industryId,
  stockId,
  onSentimentChange,
  onIndustryChange,
  onStockChange,
  onClearFilters,
  hasActiveFilters = false,
}: Props) {
  const [open, setOpen] = useState<DropdownKind>(null);

  const labelFor = (opts: NewsFilterOption[], id: string) =>
    opts.find((o) => o.id === id)?.label ?? opts[0]?.label ?? "—";

  const shortLabel = (opts: NewsFilterOption[], id: string, fallback: string) => {
    if (id === "all") return fallback;
    const full = labelFor(opts, id);
    if (full.length <= 14) return full;
    return full.slice(0, 12) + "…";
  };

  const optionsFor = (): NewsFilterOption[] => {
    if (open === "sentiment") return sentiments;
    if (open === "industry") return industries;
    if (open === "stock") return stocks;
    return [];
  };

  const selectedId =
    open === "sentiment" ? sentimentId : open === "industry" ? industryId : stockId;

  const onSelect = (id: string) => {
    if (open === "sentiment") onSentimentChange(id);
    else if (open === "industry") onIndustryChange(id);
    else if (open === "stock") onStockChange(id);
    setOpen(null);
  };

  const chipStyle = (active: boolean) => [
    styles.chip,
    active ? styles.chipActive : styles.chipInactive,
  ];

  const chipTextStyle = (active: boolean) => [
    styles.chipText,
    active ? styles.chipTextActive : styles.chipTextInactive,
  ];

  return (
    <View style={styles.wrap}>
      <View style={styles.titleRow}>
        <Text style={styles.sectionTitle}>Latest Intelligence</Text>
        <View style={styles.filterActions}>
          <Pressable style={styles.filterToggle} onPress={onToggleVisible} hitSlop={8}>
            <SlidersHorizontal size={14} color={TEAL} strokeWidth={2} />
            <Text style={styles.filterToggleText}>Filter</Text>
          </Pressable>
          {onClearFilters ? (
            <Pressable
              style={[styles.clearBtn, hasActiveFilters && styles.clearBtnActive]}
              onPress={onClearFilters}
              accessibilityLabel="Clear filters"
              hitSlop={8}
            >
              <RotateCcw size={15} color={hasActiveFilters ? TEAL : "#9CA3AF"} strokeWidth={2} />
            </Pressable>
          ) : null}
        </View>
      </View>

      {visible ? (
        <View style={styles.chipsRow}>
          <Pressable
            style={chipStyle(true)}
            onPress={() => setOpen("sentiment")}
          >
            <Text style={chipTextStyle(true)} numberOfLines={1}>
              {sentimentId === "all" ? "Sentiment" : shortLabel(sentiments, sentimentId, "Sentiment")}
            </Text>
            <ChevronDown size={14} color="#FFFFFF" strokeWidth={2} />
          </Pressable>

          <Pressable
            style={chipStyle(industryId !== "all")}
            onPress={() => setOpen("industry")}
          >
            <Text style={chipTextStyle(industryId !== "all")} numberOfLines={1}>
              {industryId === "all" ? "Industry" : shortLabel(industries, industryId, "Industry")}
            </Text>
            <ChevronDown
              size={14}
              color={industryId !== "all" ? "#FFFFFF" : TEAL}
              strokeWidth={2}
            />
          </Pressable>

          <Pressable
            style={chipStyle(stockId !== "all")}
            onPress={() => setOpen("stock")}
          >
            <Text style={chipTextStyle(stockId !== "all")} numberOfLines={1}>
              {stockId === "all" ? "Stock" : shortLabel(stocks, stockId, "Stock")}
            </Text>
            <ChevronDown
              size={14}
              color={stockId !== "all" ? "#FFFFFF" : TEAL}
              strokeWidth={2}
            />
          </Pressable>
        </View>
      ) : null}

      <Modal visible={open !== null} transparent animationType="fade" onRequestClose={() => setOpen(null)}>
        <Pressable style={styles.modalOverlay} onPress={() => setOpen(null)}>
          <View style={styles.modalSheet}>
            <FlatList
              data={optionsFor()}
              keyExtractor={(item) => item.id}
              renderItem={({ item }) => (
                <Pressable
                  style={[styles.optionRow, item.id === selectedId && styles.optionRowActive]}
                  onPress={() => onSelect(item.id)}
                >
                  <Text
                    style={[
                      styles.optionText,
                      item.id === selectedId && styles.optionTextActive,
                    ]}
                  >
                    {item.label}
                  </Text>
                </Pressable>
              )}
            />
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: 14 },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  sectionTitle: {
    fontFamily: fonts.heading,
    fontSize: 22,
    color: "#111827",
    letterSpacing: -0.5,
  },
  filterActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  filterToggle: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  clearBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: TEAL_LIGHT,
    backgroundColor: "#FFFFFF",
  },
  clearBtnActive: {
    borderColor: TEAL,
    backgroundColor: "#F0F7F9",
  },
  filterToggleText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: TEAL,
  },
  chipsRow: {
    flexDirection: "row",
    gap: 8,
  },
  chip: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  chipActive: {
    backgroundColor: TEAL,
  },
  chipInactive: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: TEAL_LIGHT,
  },
  chipText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    flexShrink: 1,
  },
  chipTextActive: {
    color: "#FFFFFF",
  },
  chipTextInactive: {
    color: TEAL,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.35)",
    justifyContent: "flex-end",
  },
  modalSheet: {
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    maxHeight: "55%",
    paddingBottom: 24,
  },
  optionRow: {
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
  optionRowActive: { backgroundColor: "#F0F7F9" },
  optionText: { fontFamily: fonts.body, fontSize: 14, color: "#374151" },
  optionTextActive: { fontFamily: fonts.bodyMedium, color: TEAL },
});
