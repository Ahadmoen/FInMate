import CitationsDrawer from "@/components/chat/CitationsDrawer";
import { chatColors, chatShadow } from "@/components/chat/chatTheme";
import type { ChatCitation } from "@/components/chat/types";
import { fonts } from "@/styles/global";
import { ChevronRight, Link2 } from "lucide-react-native";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

const VISIBLE_COUNT = 3;

type Props = {
  citations: ChatCitation[];
};

function formatShortDate(iso: string): string {
  const normalized = iso.includes("T") ? iso : iso.replace(" ", "T");
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function CitationChip({ item }: { item: ChatCitation }) {
  const shortDate = formatShortDate(item.publishedAt);

  return (
    <View style={styles.chip}>
      <View style={[styles.favicon, { backgroundColor: item.faviconColor }]}>
        <Text style={styles.faviconText}>{item.faviconLetter}</Text>
      </View>
      <View style={styles.textCol}>
        <Text style={styles.name} numberOfLines={1}>
          {item.source}
        </Text>
        <Text style={styles.subtitle} numberOfLines={1}>
          {item.ticker} · {item.docType}
          {shortDate ? ` · ${shortDate}` : ""}
        </Text>
      </View>
    </View>
  );
}

export default function SourceChips({ citations }: Props) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (!citations.length) return null;

  const visible = citations.slice(0, VISIBLE_COUNT);
  const hasMore = citations.length > VISIBLE_COUNT;

  return (
    <View style={styles.wrap}>
      <View style={styles.labelRow}>
        <Link2 size={12} color={chatColors.muted2} strokeWidth={2.2} />
        <Text style={styles.label}>Sources</Text>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {visible.map((item) => (
          <CitationChip key={item.docId} item={item} />
        ))}

        {hasMore ? (
          <Pressable style={styles.seeMore} onPress={() => setDrawerOpen(true)}>
            <Text style={styles.seeMoreText}>See more</Text>
            <Text style={styles.seeMoreCount}>
              +{citations.length - VISIBLE_COUNT}
            </Text>
            <ChevronRight size={14} color={chatColors.teal} strokeWidth={2.2} />
          </Pressable>
        ) : null}
      </ScrollView>

      <CitationsDrawer
        visible={drawerOpen}
        citations={citations}
        onClose={() => setDrawerOpen(false)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: 8,
  },
  labelRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginLeft: 2,
  },
  label: {
    fontFamily: fonts.heading,
    fontSize: 11,
    letterSpacing: 0.4,
    textTransform: "uppercase",
    color: chatColors.muted2,
  },
  scrollContent: {
    gap: 9,
    paddingHorizontal: 2,
    paddingBottom: 4,
    alignItems: "center",
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    width: 184,
    backgroundColor: chatColors.card,
    borderWidth: 1,
    borderColor: chatColors.line,
    borderRadius: 14,
    paddingVertical: 9,
    paddingHorizontal: 12,
    ...chatShadow.card,
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 2,
  },
  favicon: {
    width: 26,
    height: 26,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  faviconText: {
    fontFamily: fonts.heading,
    fontSize: 11,
    color: "#FFFFFF",
  },
  textCol: {
    flex: 1,
    minWidth: 0,
    gap: 1,
  },
  name: {
    fontFamily: fonts.heading,
    fontSize: 10.5,
    color: chatColors.tealSoft,
  },
  subtitle: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    color: chatColors.ink,
  },
  seeMore: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    height: 44,
    paddingHorizontal: 14,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: chatColors.line,
    backgroundColor: chatColors.card,
  },
  seeMoreText: {
    fontFamily: fonts.heading,
    fontSize: 12,
    color: chatColors.teal,
  },
  seeMoreCount: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    color: chatColors.muted2,
  },
});
