import { useUnreadNotificationCount } from "@/hooks/useUnreadNotificationCount";
import { colors, fonts } from "@/styles/global";
import { useRouter } from "expo-router";
import { Bell, Building2, User } from "lucide-react-native";
import { Pressable, StyleSheet, Text, View } from "react-native";

type Props = {
  onBellPress?: () => void;
};

export default function ScreenHeader({ onBellPress }: Props) {
  const router = useRouter();
  const unreadCount = useUnreadNotificationCount();

  const handleBellPress = onBellPress ?? (() => router.push("/notifications"));

  const badgeLabel =
    unreadCount > 99 ? "99+" : unreadCount > 0 ? String(unreadCount) : null;

  return (
    <View style={styles.header}>
      <View style={styles.left}>
        <Building2 size={21} color={colors.primary} strokeWidth={1.8} />

        <Text style={styles.logo}>FinMate</Text>
      </View>

      <View style={styles.right}>
        <Pressable style={styles.bellBtn} onPress={handleBellPress} hitSlop={8}>
          <Bell size={19} color={colors.text} strokeWidth={1.8} />
          {badgeLabel ? (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{badgeLabel}</Text>
            </View>
          ) : null}
        </Pressable>

        <Pressable
          style={styles.avatar}
          onPress={() => router.push("/(tabs)/profile")}
          hitSlop={8}
        >
          <User size={16} color="#FFFFFF" strokeWidth={2} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",

    alignItems: "center",

    justifyContent: "space-between",

    paddingHorizontal: 20,

    paddingVertical: 11,

    backgroundColor: colors.background,

    borderBottomWidth: 1,

    borderBottomColor: colors.borderLight,
  },

  left: {
    flexDirection: "row",

    alignItems: "center",

    gap: 8,
  },

  logo: {
    fontFamily: fonts.heading,

    fontSize: 19,

    color: colors.primary,

    letterSpacing: -0.5,
  },

  right: {
    flexDirection: "row",

    alignItems: "center",

    gap: 10,
  },

  bellBtn: {
    width: 36,

    height: 36,

    borderRadius: 18,

    borderWidth: 1,

    borderColor: colors.borderLight,

    backgroundColor: colors.bgLight,

    alignItems: "center",

    justifyContent: "center",

    position: "relative",
  },

  badge: {
    position: "absolute",
    top: -2,
    right: -2,
    minWidth: 16,
    height: 16,
    paddingHorizontal: 4,
    borderRadius: 8,
    backgroundColor: colors.error,
    borderWidth: 1.5,
    borderColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
  },

  badgeText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 9,
    color: "#FFFFFF",
    lineHeight: 11,
  },

  avatar: {
    width: 36,

    height: 36,

    borderRadius: 18,

    backgroundColor: colors.primary,

    alignItems: "center",

    justifyContent: "center",
  },
});
