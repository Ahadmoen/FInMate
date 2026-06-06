import { chatColors } from "@/components/chat/chatTheme";
import { fonts } from "@/styles/global";
import { History, MessageSquarePlus } from "lucide-react-native";
import { Pressable, StyleSheet, Text, View } from "react-native";

type Props = {
  onRecentChats: () => void;
  onNewChat: () => void;
  disabled?: boolean;
  recentCount?: number;
};

export default function ChatToolbar({
  onRecentChats,
  onNewChat,
  disabled = false,
  recentCount = 0,
}: Props) {
  return (
    <View style={styles.bar}>
      <Pressable
        style={[styles.btn, styles.btnOutline, disabled && styles.btnDim]}
        onPress={onRecentChats}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel="Recent chats"
      >
        <History size={16} color={chatColors.teal} strokeWidth={2} />
        <Text style={styles.btnTextOutline}>Recent chats</Text>
        {recentCount > 0 ? (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>
              {recentCount > 9 ? "9+" : recentCount}
            </Text>
          </View>
        ) : null}
      </Pressable>

      <Pressable
        style={[styles.btn, styles.btnSolid, disabled && styles.btnDim]}
        onPress={onNewChat}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel="New chat"
      >
        <MessageSquarePlus size={16} color="#FFFFFF" strokeWidth={2} />
        <Text style={styles.btnTextSolid}>New chat</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: chatColors.bg,
    borderBottomWidth: 1,
    borderBottomColor: chatColors.line,
  },
  btn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 999,
  },
  btnOutline: {
    backgroundColor: chatColors.card,
    borderWidth: 1,
    borderColor: chatColors.line,
  },
  btnSolid: {
    backgroundColor: chatColors.teal,
  },
  btnDim: {
    opacity: 0.45,
  },
  btnTextOutline: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: chatColors.teal,
  },
  btnTextSolid: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: "#FFFFFF",
  },
  badge: {
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: chatColors.tealAccent,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 4,
    marginLeft: 2,
  },
  badgeText: {
    fontFamily: fonts.heading,
    fontSize: 10,
    color: chatColors.teal,
  },
});
