import { useAuth } from "@/context/AuthContext";
import type { UserDetails } from "@/services/auth";
import { colors, fonts } from "@/styles/global";
import { useFocusEffect, useRouter } from "expo-router";
import {
  ArrowLeftRight,
  Bell,
  Briefcase,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  LogOut,
  Pencil,
  ShieldCheck,
  User,
} from "lucide-react-native";
import type { ComponentType } from "react";
import { useCallback } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

// ─── Types ────────────────────────────────────────────────────────────────────

type MenuItem = {
  id: string;
  label: string;
  Icon: ComponentType<{ size: number; color: string; strokeWidth: number }>;
  iconBg: string;
  iconColor: string;
  labelColor: string;
  chevronColor: string;
  route?: string;
  danger?: boolean;
};

function formatDisplayName(user: UserDetails | null): string {
  if (!user) return "";
  const full = [user.first_name, user.last_name].filter(Boolean).join(" ").trim();
  return full || user.email.split("@")[0] || "User";
}

function formatInitials(user: UserDetails | null): string {
  if (!user) return "";
  const first = user.first_name?.trim().charAt(0) ?? "";
  const last = user.last_name?.trim().charAt(0) ?? "";
  const initials = `${first}${last}`.toUpperCase();
  if (initials) return initials;
  return user.email.charAt(0).toUpperCase();
}

// ─── Data ─────────────────────────────────────────────────────────────────────

const menuItems: MenuItem[] = [
  {
    id: "personal",
    label: "Personal Info",
    Icon: User,
    iconBg: colors.bgLight,
    iconColor: colors.textSecondary,
    labelColor: colors.text,
    chevronColor: colors.mutedText,
    route: "/personal-info",
  },
  {
    id: "alerts",
    label: "Alert Settings",
    Icon: Bell,
    iconBg: colors.bgLight,
    iconColor: colors.textSecondary,
    labelColor: colors.text,
    chevronColor: colors.mutedText,
    route: "/alert-settings",
  },
  {
    id: "portfolio",
    label: "Manage Portfolio",
    Icon: Briefcase,
    iconBg: colors.bgLight,
    iconColor: colors.textSecondary,
    labelColor: colors.text,
    chevronColor: colors.mutedText,
    route: "/manage-portfolio",
  },
  {
    id: "buy-sell",
    label: "Buy / Sell Stock",
    Icon: ArrowLeftRight,
    iconBg: colors.bgLight,
    iconColor: colors.textSecondary,
    labelColor: colors.text,
    chevronColor: colors.mutedText,
    route: "/buy-sell-stock",
  },
  {
    id: "financial",
    label: "Financial Profile",
    Icon: CircleDollarSign,
    iconBg: colors.bgLight,
    iconColor: colors.textSecondary,
    labelColor: colors.text,
    chevronColor: colors.mutedText,
    route: "/financial-profile",
  },
  {
    id: "privacy",
    label: "Privacy Policy",
    Icon: ShieldCheck,
    iconBg: colors.bgLight,
    iconColor: colors.textSecondary,
    labelColor: colors.text,
    chevronColor: colors.mutedText,
    route: "/privacy-policy",
  },
  {
    id: "logout",
    label: "Logout",
    Icon: LogOut,
    iconBg: "#FEE2E2",
    iconColor: "#DC2626",
    labelColor: "#DC2626",
    chevronColor: "#DC2626",
    danger: true,
  },
];

// ─── Sub-components ───────────────────────────────────────────────────────────

function ProfileHeader() {
  const router = useRouter();

  return (
    <View style={styles.header}>
      <Pressable style={styles.headerBtn} onPress={() => router.back()} hitSlop={10}>
        <ChevronLeft size={22} color={colors.primary} strokeWidth={2} />
      </Pressable>
      <Text style={styles.headerTitle}>Profile</Text>
      <View style={styles.headerBtn} />
    </View>
  );
}

function AvatarSection({
  user,
  loading,
}: {
  user: UserDetails | null;
  loading: boolean;
}) {
  const router = useRouter();
  const displayName = formatDisplayName(user);
  const email = user?.email ?? "";
  const initials = formatInitials(user);

  return (
    <View style={styles.avatarSection}>
      <View style={styles.avatarWrap}>
        <View style={styles.avatarPlaceholder}>
          {loading ? (
            <ActivityIndicator size="small" color={colors.primary} />
          ) : initials ? (
            <Text style={styles.avatarInitials}>{initials}</Text>
          ) : (
            <User size={52} color={colors.primary} strokeWidth={1.2} />
          )}
        </View>
        <Pressable
          style={styles.editBadge}
          onPress={() => router.push("/personal-info")}
          hitSlop={8}
        >
          <Pencil size={11} color="#FFFFFF" strokeWidth={2.5} />
        </Pressable>
      </View>
      {loading ? (
        <ActivityIndicator size="small" color={colors.primary} style={{ marginTop: 8 }} />
      ) : (
        <>
          <Text style={styles.userName}>{displayName || "—"}</Text>
          <Text style={styles.userEmail}>{email || "—"}</Text>
        </>
      )}
    </View>
  );
}

function MenuCard() {
  const router = useRouter();
  const { logout } = useAuth();

  const handlePress = async (item: MenuItem) => {
    if (item.danger) {
      await logout();
    } else if (item.route) {
      router.push(item.route as never);
    }
  };

  return (
    <View style={styles.menuCard}>
      {menuItems.map((item, index) => {
        const Icon = item.Icon;
        return (
          <View key={item.id}>
            {index > 0 && <View style={styles.divider} />}
            <Pressable
              style={styles.menuRow}
              onPress={() => handlePress(item)}
              android_ripple={{ color: colors.bgLight }}
            >
              <View style={[styles.menuIcon, { backgroundColor: item.iconBg }]}>
                <Icon size={17} color={item.iconColor} strokeWidth={1.8} />
              </View>
              <Text style={[styles.menuLabel, { color: item.labelColor }]}>
                {item.label}
              </Text>
              <ChevronRight size={16} color={item.chevronColor} strokeWidth={2} />
            </Pressable>
          </View>
        );
      })}
    </View>
  );
}

// ─── Screen ───────────────────────────────────────────────────────────────────

export default function ProfileScreen() {
  const { user, isLoading, refreshUser } = useAuth();

  useFocusEffect(
    useCallback(() => {
      refreshUser();
    }, [refreshUser]),
  );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ProfileHeader />
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <AvatarSection user={user} loading={isLoading} />
        <MenuCard />
        <Text style={styles.version}>FINMATE V 1.0</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },

  // ── Header
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 18,
    paddingVertical: 13,
    backgroundColor: colors.background,
  },
  headerBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontFamily: fonts.heading,
    fontSize: 20,
    color: colors.primary,
    letterSpacing: -0.3,
  },

  // ── Scroll
  scroll: { flex: 1 },
  content: {
    paddingHorizontal: 20,
    paddingBottom: 32,
    gap: 24,
  },

  // ── Avatar
  avatarSection: {
    alignItems: "center",
    paddingTop: 16,
    gap: 6,
  },
  avatarWrap: {
    position: "relative",
    marginBottom: 8,
  },
  avatarPlaceholder: {
    width: 96,
    height: 96,
    borderRadius: 14,
    backgroundColor: colors.bgSecondaryLight,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.borderMuted,
  },
  avatarInitials: {
    fontFamily: fonts.heading,
    fontSize: 32,
    color: colors.primary,
    letterSpacing: -0.5,
  },
  editBadge: {
    position: "absolute",
    bottom: -6,
    right: -6,
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: colors.bgPrimaryLight,
  },
  userName: {
    fontFamily: fonts.heading,
    fontSize: 18,
    color: colors.text,
    letterSpacing: -0.3,
    marginTop: 2,
  },
  userEmail: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.mutedText,
  },

  // ── Menu Card
  menuCard: {
    backgroundColor: colors.background,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderLight,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  divider: {
    height: 1,
    backgroundColor: colors.borderLight,
    marginLeft: 62,
  },
  menuRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 15,
    paddingHorizontal: 16,
    gap: 14,
  },
  menuIcon: {
    width: 36,
    height: 36,
    borderRadius: 9,
    alignItems: "center",
    justifyContent: "center",
  },
  menuLabel: {
    flex: 1,
    fontFamily: fonts.body,
    fontSize: 14,
    letterSpacing: 0.1,
  },

  // ── Footer
  version: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    color: colors.mutedText,
    textAlign: "center",
    letterSpacing: 1.2,
  },
});
