import type { NewsArticle } from "@/services/news";
import { fonts } from "@/styles/global";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";

const TEAL = "#0E4D53";
const GREEN = "#16A34A";
const GREEN_BG = "#DCFCE7";
const GRAY = "#6B7280";
const GRAY_BG = "#F3F4F6";

type Props = {
  article: NewsArticle;
};

function badgeColors(tone: NewsArticle["sentiment_tone"]) {
  if (tone === "positive") {
    return { bg: GREEN_BG, text: GREEN, dot: GREEN };
  }
  if (tone === "negative") {
    return { bg: "#FEE2E2", text: "#DC2626", dot: "#DC2626" };
  }
  return { bg: GRAY_BG, text: GRAY, dot: GRAY };
}

export default function NewsArticleCard({ article }: Props) {
  const colors = badgeColors(article.sentiment_tone);

  const openLink = () => {
    if (article.link?.trim()) {
      Linking.openURL(article.link).catch(() => undefined);
    }
  };

  return (
    <View style={styles.card}>
      <View style={styles.topRow}>
        <View style={styles.metaLeft}>
          <View style={[styles.statusBadge, { backgroundColor: colors.bg }]}>
            <Text style={[styles.statusText, { color: colors.text }]}>
              {article.status_badge}
            </Text>
          </View>
          <View style={styles.sentimentRow}>
            <View style={[styles.dot, { backgroundColor: colors.dot }]} />
            <Text style={[styles.sentimentLabel, { color: colors.text }]}>
              {article.sentiment_label}
            </Text>
          </View>
        </View>
        <Text style={styles.timeAgo}>{article.time_ago}</Text>
      </View>

      <Pressable onPress={openLink} disabled={!article.link?.trim()}>
        <Text style={styles.headline} numberOfLines={3}>
          {article.headline}
        </Text>
      </Pressable>

      <View style={styles.sourceRow}>
        <View style={styles.sourceIcon}>
          <Text style={styles.sourceInitial}>
            {(article.source || "?").charAt(0).toUpperCase()}
          </Text>
        </View>
        <Text style={styles.sourceName} numberOfLines={1}>
          {article.source}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#E8EEF0",
    shadowColor: "#0E4D53",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 10,
  },
  metaLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    flex: 1,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  statusText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 9,
    letterSpacing: 0.5,
  },
  sentimentRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  sentimentLabel: {
    fontFamily: fonts.bodyMedium,
    fontSize: 9,
    letterSpacing: 0.4,
  },
  timeAgo: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: GRAY,
    marginLeft: 8,
  },
  headline: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: "#111827",
    lineHeight: 20,
    marginBottom: 12,
  },
  sourceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flex: 1,
  },
  sourceIcon: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: "#E8EEF0",
    alignItems: "center",
    justifyContent: "center",
  },
  sourceInitial: {
    fontFamily: fonts.bodyMedium,
    fontSize: 10,
    color: TEAL,
  },
  sourceName: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: GRAY,
    flex: 1,
  },
});
