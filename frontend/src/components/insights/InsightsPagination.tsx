import { fonts } from "@/styles/global";
import { ChevronLeft, ChevronRight } from "lucide-react-native";
import { Pressable, StyleSheet, Text, View } from "react-native";

const TEAL = "#0E4D53";

type Props = {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
};

function pageNumbers(current: number, total: number): (number | "...")[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages: (number | "...")[] = [1];
  if (current > 3) pages.push("...");
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  for (let p = start; p <= end; p++) pages.push(p);
  if (current < total - 2) pages.push("...");
  if (total > 1) pages.push(total);
  return pages;
}

export default function InsightsPagination({ page, totalPages, onPageChange }: Props) {
  if (totalPages <= 1) return null;

  const pages = pageNumbers(page, totalPages);
  const canPrev = page > 1;
  const canNext = page < totalPages;

  return (
    <View style={styles.wrap}>
      <Pressable
        style={[styles.navBtn, !canPrev && styles.navBtnDisabled]}
        onPress={() => canPrev && onPageChange(page - 1)}
        disabled={!canPrev}
      >
        <ChevronLeft size={14} color={canPrev ? TEAL : "#9CA3AF"} strokeWidth={2.5} />
        <Text style={[styles.navText, !canPrev && styles.navTextDisabled]}>PREV</Text>
      </Pressable>

      <View style={styles.pagesRow}>
        {pages.map((p, idx) =>
          p === "..." ? (
            <Text key={`ellipsis-${idx}`} style={styles.ellipsis}>
              ...
            </Text>
          ) : (
            <Pressable
              key={p}
              style={[styles.pageBtn, p === page && styles.pageBtnActive]}
              onPress={() => onPageChange(p)}
            >
              <Text style={[styles.pageText, p === page && styles.pageTextActive]}>{p}</Text>
            </Pressable>
          ),
        )}
      </View>

      <Pressable
        style={[styles.navBtn, !canNext && styles.navBtnDisabled]}
        onPress={() => canNext && onPageChange(page + 1)}
        disabled={!canNext}
      >
        <Text style={[styles.navText, !canNext && styles.navTextDisabled]}>NEXT</Text>
        <ChevronRight size={14} color={canNext ? TEAL : "#9CA3AF"} strokeWidth={2.5} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 16,
    paddingHorizontal: 4,
  },
  navBtn: { flexDirection: "row", alignItems: "center", gap: 2, padding: 6 },
  navBtnDisabled: { opacity: 0.5 },
  navText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    color: TEAL,
    letterSpacing: 0.5,
  },
  navTextDisabled: { color: "#9CA3AF" },
  pagesRow: { flexDirection: "row", alignItems: "center", gap: 4 },
  pageBtn: {
    minWidth: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  pageBtnActive: { backgroundColor: TEAL },
  pageText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: "#6B7280",
  },
  pageTextActive: { color: "#FFFFFF" },
  ellipsis: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: "#9CA3AF",
    paddingHorizontal: 2,
  },
});
