import type { InsightsFilterOption } from "@/services/insights";
import { fonts } from "@/styles/global";
import { ArrowUpDown, ChevronDown, RotateCcw, Search, SlidersHorizontal, TrendingUp } from "lucide-react-native";
import { useState } from "react";
import {
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

const TEAL = "#0E4D53";
const TEAL_LIGHT = "#E5EBED";

type DropdownKind = "sector" | "trend" | "sort" | null;

type Props = {
  visible: boolean;
  onToggleVisible: () => void;
  search: string;
  onSearchChange: (v: string) => void;
  sectors: InsightsFilterOption[];
  trends: InsightsFilterOption[];
  sortOptions: InsightsFilterOption[];
  sectorId: string;
  trendId: string;
  sortId: string;
  onSectorChange: (id: string) => void;
  onTrendChange: (id: string) => void;
  onSortChange: (id: string) => void;
  onClearFilters?: () => void;
  hasActiveFilters?: boolean;
};

export default function InsightsFilterBar({
  visible,
  onToggleVisible,
  search,
  onSearchChange,
  sectors,
  trends,
  sortOptions,
  sectorId,
  trendId,
  sortId,
  onSectorChange,
  onTrendChange,
  onSortChange,
  onClearFilters,
  hasActiveFilters = false,
}: Props) {
  const [open, setOpen] = useState<DropdownKind>(null);

  const labelFor = (opts: InsightsFilterOption[], id: string) =>
    opts.find((o) => o.id === id)?.label ?? opts[0]?.label ?? "—";

  const chipLabel = (
    opts: InsightsFilterOption[],
    id: string,
    defaultLabel: string,
  ) => (id === "all" || id === "name" ? defaultLabel : labelFor(opts, id));

  const optionsFor = (): InsightsFilterOption[] => {
    if (open === "sector") return sectors;
    if (open === "trend") return trends;
    if (open === "sort") return sortOptions;
    return [];
  };

  const selectedId = open === "sector" ? sectorId : open === "trend" ? trendId : sortId;

  const onSelect = (id: string) => {
    if (open === "sector") onSectorChange(id);
    else if (open === "trend") onTrendChange(id);
    else if (open === "sort") onSortChange(id);
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
      <View style={styles.searchBox}>
        <Search size={16} color="#9CA3AF" strokeWidth={2} />
        <TextInput
          value={search}
          onChangeText={onSearchChange}
          placeholder="Search stocks, tickers or industries..."
          placeholderTextColor="#9CA3AF"
          style={styles.searchInput}
          autoCorrect={false}
          autoCapitalize="none"
          returnKeyType="search"
        />
      </View>

      <View style={styles.titleRow}>
        <Text style={styles.sectionTitle}>Stock Insights</Text>
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
          <Pressable style={chipStyle(sectorId !== "all")} onPress={() => setOpen("sector")}>
            <Text style={chipTextStyle(sectorId !== "all")} numberOfLines={1}>
              {chipLabel(sectors, sectorId, "Sector")}
            </Text>
            <ChevronDown
              size={14}
              color={sectorId !== "all" ? "#FFFFFF" : TEAL}
              strokeWidth={2}
            />
          </Pressable>

          <Pressable style={chipStyle(trendId !== "all")} onPress={() => setOpen("trend")}>
            <TrendingUp
              size={13}
              color={trendId !== "all" ? "#FFFFFF" : TEAL}
              strokeWidth={2}
            />
            <Text style={chipTextStyle(trendId !== "all")} numberOfLines={1}>
              {chipLabel(trends, trendId, "Signal")}
            </Text>
            <ChevronDown
              size={14}
              color={trendId !== "all" ? "#FFFFFF" : TEAL}
              strokeWidth={2}
            />
          </Pressable>

          <Pressable style={chipStyle(sortId !== "name")} onPress={() => setOpen("sort")}>
            <ArrowUpDown
              size={13}
              color={sortId !== "name" ? "#FFFFFF" : TEAL}
              strokeWidth={2}
            />
            <Text style={chipTextStyle(sortId !== "name")} numberOfLines={1}>
              {chipLabel(sortOptions, sortId, "Sort")}
            </Text>
            <ChevronDown
              size={14}
              color={sortId !== "name" ? "#FFFFFF" : TEAL}
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
  wrap: { gap: 10, marginBottom: 4 },
  searchBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: TEAL_LIGHT,
  },
  searchInput: {
    flex: 1,
    fontFamily: fonts.body,
    fontSize: 13,
    color: "#111827",
    paddingVertical: 0,
  },
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
  filterToggleText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: TEAL,
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
