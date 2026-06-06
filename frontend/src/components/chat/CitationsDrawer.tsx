import { chatColors } from "@/components/chat/chatTheme";
import type { ChatCitation } from "@/components/chat/types";
import { colors, fonts } from "@/styles/global";
import { X } from "lucide-react-native";
import { useEffect, useRef } from "react";
import {
  Animated,
  Easing,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

type Props = {
  visible: boolean;
  citations: ChatCitation[];
  onClose: () => void;
};

function formatPublishedAt(iso: string): string {
  const normalized = iso.includes("T") ? iso : iso.replace(" ", "T");
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function CitationRow({ item }: { item: ChatCitation }) {
  return (
    <View style={styles.row}>
      <View style={[styles.avatar, { backgroundColor: item.faviconColor }]}>
        <Text style={styles.avatarText}>{item.faviconLetter}</Text>
      </View>
      <View style={styles.rowBody}>
        <Text style={styles.sourceName}>{item.source}</Text>
        <Text style={styles.meta}>
          {item.ticker} · {item.docType}
        </Text>
        <Text style={styles.date}>{formatPublishedAt(item.publishedAt)}</Text>
      </View>
      <Text style={styles.score}>{(item.score * 100).toFixed(1)}%</Text>
    </View>
  );
}

export default function CitationsDrawer({
  visible,
  citations,
  onClose,
}: Props) {
  const slideY = useRef(new Animated.Value(700)).current;
  const fadeOverlay = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      slideY.setValue(700);
      fadeOverlay.setValue(0);
      Animated.parallel([
        Animated.timing(slideY, {
          toValue: 0,
          duration: 280,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
        Animated.timing(fadeOverlay, {
          toValue: 1,
          duration: 220,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
      ]).start();
    }
  }, [visible, slideY, fadeOverlay]);

  const handleClose = () => {
    Animated.parallel([
      Animated.timing(slideY, {
        toValue: 700,
        duration: 230,
        easing: Easing.in(Easing.cubic),
        useNativeDriver: true,
      }),
      Animated.timing(fadeOverlay, {
        toValue: 0,
        duration: 190,
        easing: Easing.in(Easing.cubic),
        useNativeDriver: true,
      }),
    ]).start(() => onClose());
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="none"
      onRequestClose={handleClose}
    >
      <Animated.View style={[styles.overlay, { opacity: fadeOverlay }]}>
        <Pressable style={StyleSheet.absoluteFillObject} onPress={handleClose} />
      </Animated.View>

      <Animated.View style={[styles.sheet, { transform: [{ translateY: slideY }] }]}>
        <View style={styles.handle} />
        <View style={styles.header}>
          <Text style={styles.title}>All sources</Text>
          <Text style={styles.subtitle}>{citations.length} citations</Text>
          <Pressable style={styles.closeBtn} onPress={handleClose} hitSlop={10}>
            <X size={20} color={colors.textSecondary} strokeWidth={2} />
          </Pressable>
        </View>

        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {citations.map((item) => (
            <CitationRow key={item.docId} item={item} />
          ))}
        </ScrollView>
      </Animated.View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(12, 31, 31, 0.45)",
  },
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    maxHeight: "78%",
    backgroundColor: colors.background,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    paddingBottom: 28,
  },
  handle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: chatColors.line,
    marginTop: 10,
    marginBottom: 8,
  },
  header: {
    paddingHorizontal: 20,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: chatColors.line,
  },
  title: {
    fontFamily: fonts.heading,
    fontSize: 17,
    color: chatColors.ink,
    letterSpacing: -0.2,
  },
  subtitle: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: chatColors.muted,
    marginTop: 2,
  },
  closeBtn: {
    position: "absolute",
    right: 16,
    top: 0,
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  scroll: {
    flexGrow: 0,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
    gap: 10,
  },
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 12,
    backgroundColor: chatColors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: chatColors.line,
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: {
    fontFamily: fonts.heading,
    fontSize: 12,
    color: "#FFFFFF",
  },
  rowBody: {
    flex: 1,
    minWidth: 0,
    gap: 2,
  },
  sourceName: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: chatColors.ink,
  },
  meta: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: chatColors.tealSoft,
  },
  date: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: chatColors.muted2,
    marginTop: 2,
  },
  score: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    color: chatColors.muted2,
    paddingTop: 2,
  },
});
