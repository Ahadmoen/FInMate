import { chatColors } from "@/components/chat/chatTheme";
import type { ChatSessionSummary } from "@/services/chatSessions";
import { colors, fonts } from "@/styles/global";
import { Trash2, X } from "lucide-react-native";
import { useEffect, useRef } from "react";
import {
  ActivityIndicator,
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
  sessions: ChatSessionSummary[];
  activeSessionId: string | null;
  loading?: boolean;
  error?: string | null;
  onClose: () => void;
  onSelect: (session: ChatSessionSummary) => void;
  onDelete: (sessionId: string) => void;
};

function formatWhen(iso: string): string {
  const normalized = iso.includes("T") ? iso : iso.replace(" ", "T");
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return iso;

  const now = new Date();
  const sameDay =
    d.getDate() === now.getDate() &&
    d.getMonth() === now.getMonth() &&
    d.getFullYear() === now.getFullYear();

  if (sameDay) {
    return d.toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
}

export default function RecentChatsDrawer({
  visible,
  sessions,
  activeSessionId,
  loading = false,
  error = null,
  onClose,
  onSelect,
  onDelete,
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
          <Text style={styles.title}>Recent chats</Text>
          <Text style={styles.subtitle}>Your conversation history with AIVA</Text>
          <Pressable style={styles.closeBtn} onPress={handleClose} hitSlop={10}>
            <X size={20} color={colors.textSecondary} strokeWidth={2} />
          </Pressable>
        </View>

        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {loading ? (
            <View style={styles.centered}>
              <ActivityIndicator color={chatColors.teal} />
            </View>
          ) : error ? (
            <Text style={styles.empty}>{error}</Text>
          ) : sessions.length === 0 ? (
            <Text style={styles.empty}>
              No past chats yet. Start a conversation with AIVA — it will appear
              here after your first reply.
            </Text>
          ) : (
            sessions.map((session) => {
              const isActive = session.sessionId === activeSessionId;
              return (
                <Pressable
                  key={session.sessionId}
                  style={[styles.row, isActive && styles.rowActive]}
                  onPress={() => {
                    onSelect(session);
                    handleClose();
                  }}
                >
                  <View style={styles.rowBody}>
                    <Text style={styles.rowTitle} numberOfLines={2}>
                      {session.title}
                    </Text>
                    <Text style={styles.rowMeta}>
                      {formatWhen(session.updatedAt)} · {session.messageCount}{" "}
                      messages
                    </Text>
                  </View>
                  <Pressable
                    style={styles.deleteBtn}
                    onPress={() => onDelete(session.sessionId)}
                    hitSlop={8}
                  >
                    <Trash2 size={16} color={chatColors.muted2} strokeWidth={2} />
                  </Pressable>
                </Pressable>
              );
            })
          )}
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
    maxHeight: "72%",
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
    fontSize: 12,
    color: chatColors.muted,
    marginTop: 4,
    paddingRight: 36,
    lineHeight: 17,
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
    padding: 16,
    gap: 8,
  },
  centered: {
    paddingVertical: 32,
    alignItems: "center",
  },
  empty: {
    fontFamily: fonts.body,
    fontSize: 14,
    color: chatColors.muted,
    lineHeight: 21,
    textAlign: "center",
    paddingVertical: 24,
    paddingHorizontal: 12,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: chatColors.line,
    backgroundColor: chatColors.card,
  },
  rowActive: {
    borderColor: chatColors.tealAccent,
    backgroundColor: "#F0F7F6",
  },
  rowBody: {
    flex: 1,
    minWidth: 0,
    gap: 4,
  },
  rowTitle: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: chatColors.ink,
    lineHeight: 20,
  },
  rowMeta: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: chatColors.muted2,
  },
  deleteBtn: {
    padding: 6,
  },
});
