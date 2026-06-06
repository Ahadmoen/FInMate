import { useAuth } from "@/context/AuthContext";
import {
  fetchNotificationPreferences,
  updateNotificationPreferences,
  type NotificationPreferences,
} from "@/services/notifications";
import { colors, fonts } from "@/styles/global";
import { useRouter } from "expo-router";
import {
  Bell,
  ChevronLeft,
  Clock,
  Hash,
  MessageCircle,
  Moon,
  Save,
  Smartphone,
  Sun,
  Sunrise,
} from "lucide-react-native";
import type { ComponentType, ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

type PrefKey = keyof Omit<NotificationPreferences, "id">;

type ToggleRowProps = {
  title: string;
  subtitle?: string;
  value: boolean;
  onValueChange: (v: boolean) => void;
  Icon?: ComponentType<{ size: number; color: string; strokeWidth: number }>;
  disabled?: boolean;
};

function PreferenceToggle({
  title,
  subtitle,
  value,
  onValueChange,
  Icon,
  disabled = false,
}: ToggleRowProps) {
  return (
    <View style={[styles.toggleRow, disabled && styles.toggleRowDisabled]}>
      <View style={styles.toggleLeft}>
        {Icon ? (
          <View style={[styles.rowIconWrap, disabled && styles.rowIconWrapDisabled]}>
            <Icon
              size={18}
              color={disabled ? colors.mutedText : colors.primary}
              strokeWidth={1.8}
            />
          </View>
        ) : null}
        <View style={[styles.toggleTextWrap, !Icon && styles.toggleTextNoIcon]}>
          <Text style={[styles.channelTitle, disabled && styles.channelTitleDisabled]}>
            {title}
          </Text>
          {subtitle ? (
            <Text style={[styles.channelDesc, disabled && styles.channelDescDisabled]}>
              {subtitle}
            </Text>
          ) : null}
        </View>
      </View>
      <Switch
        value={value}
        onValueChange={onValueChange}
        disabled={disabled}
        trackColor={{
          false: colors.borderLight,
          true: disabled ? colors.borderMuted : colors.primary,
        }}
        thumbColor="#FFFFFF"
        ios_backgroundColor={colors.borderLight}
      />
    </View>
  );
}

function SettingsCard({
  Icon,
  title,
  children,
  headerTint = colors.bgPrimaryLight,
}: {
  Icon: ComponentType<{ size: number; color: string; strokeWidth: number }>;
  title: string;
  children: ReactNode;
  headerTint?: string;
}) {
  return (
    <View style={styles.card}>
      <View style={[styles.cardSectionHeader, { backgroundColor: headerTint }]}>
        <View style={styles.cardSectionIcon}>
          <Icon size={17} color={colors.primary} strokeWidth={2} />
        </View>
        <Text style={styles.cardSectionTitle}>{title}</Text>
      </View>
      <View style={styles.cardBody}>{children}</View>
    </View>
  );
}

const EMPTY_PREFS: Omit<NotificationPreferences, "id"> = {
  in_app_enabled: true,
  email_enabled: true,
  whatsapp_enabled: false,
  slack_enabled: false,
  pre_market: true,
  mid_session: true,
  post_market: true,
};

export default function AlertSettingsScreen() {
  const router = useRouter();
  const { token } = useAuth();

  const [prefs, setPrefs] = useState<Omit<NotificationPreferences, "id">>(EMPTY_PREFS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const loadPreferences = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await fetchNotificationPreferences(token);
      setPrefs({
        in_app_enabled: data.in_app_enabled ?? true,
        email_enabled: data.email_enabled,
        whatsapp_enabled: data.whatsapp_enabled,
        slack_enabled: data.slack_enabled,
        pre_market: data.pre_market,
        mid_session: data.mid_session,
        post_market: data.post_market,
      });
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to load preferences.";
      Alert.alert("Error", msg);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadPreferences();
  }, [loadPreferences]);

  const setPref = (key: PrefKey, value: boolean) => {
    setPrefs((prev) => ({ ...prev, [key]: value }));
  };

  const onSave = async () => {
    if (!token) return;
    setSaving(true);
    try {
      await updateNotificationPreferences(token, {
        ...prefs,
        whatsapp_enabled: false,
        slack_enabled: false,
      });
      Alert.alert("Success", "Your notification preferences have been saved.");
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to save. Please try again.";
      Alert.alert("Error", msg);
    } finally {
      setSaving(false);
    }
  };

  const header = (
    <View style={styles.header}>
      <Pressable style={styles.backBtn} onPress={() => router.back()} hitSlop={10}>
        <ChevronLeft size={22} color={colors.primary} strokeWidth={2} />
      </Pressable>
      <Text style={styles.headerTitle}>Alert Settings</Text>
      <Text style={styles.headerLogo}>FinMate</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      {header}

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : (
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.introCard}>
            <Text style={styles.introTitle}>Configure Your Pulse</Text>
            <Text style={styles.introSub}>
              Stay ahead of the market with precision notifications across your
              favorite platforms.
            </Text>
          </View>

          <SettingsCard Icon={Bell} title="Notification Channels">
            <PreferenceToggle
              title="In App Notifications"
              subtitle="Alerts and updates inside FinMate"
              value={prefs.in_app_enabled}
              onValueChange={(v) => setPref("in_app_enabled", v)}
              Icon={Smartphone}
            />
            <View style={styles.divider} />
            <PreferenceToggle
              title="Slack"
              subtitle="Coming soon — workspace alerts"
              value={false}
              onValueChange={() => {}}
              Icon={Hash}
              disabled
            />
            <View style={styles.divider} />
            <PreferenceToggle
              title="WhatsApp"
              subtitle="Coming soon — real-time trade confirmations"
              value={false}
              onValueChange={() => {}}
              Icon={MessageCircle}
              disabled
            />
          </SettingsCard>

          <SettingsCard
            Icon={Clock}
            title="Market Session Alerts"
            headerTint={colors.bgTertiaryLight}
          >
            <PreferenceToggle
              title="Pre-Market Summary"
              subtitle="8:30 AM EST forecasts"
              value={prefs.pre_market}
              onValueChange={(v) => setPref("pre_market", v)}
              Icon={Sunrise}
            />
            <View style={styles.divider} />
            <PreferenceToggle
              title="Mid-Session Updates"
              subtitle="12:30 PM EST volatility check"
              value={prefs.mid_session}
              onValueChange={(v) => setPref("mid_session", v)}
              Icon={Sun}
            />
            <View style={styles.divider} />
            <PreferenceToggle
              title="Post-Market Wrap-up"
              subtitle="4:30 PM EST performance wrap"
              value={prefs.post_market}
              onValueChange={(v) => setPref("post_market", v)}
              Icon={Moon}
            />
          </SettingsCard>

          <Pressable
            style={[styles.saveButton, saving && styles.saveButtonDisabled]}
            onPress={onSave}
            disabled={saving}
          >
            {saving ? (
              <ActivityIndicator color={colors.background} size="small" />
            ) : (
              <>
                <Save size={16} color={colors.background} strokeWidth={2} />
                <Text style={styles.saveButtonText}>Save Preferences</Text>
              </>
            )}
          </Pressable>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },

  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: colors.background,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  backBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontFamily: fonts.heading,
    fontSize: 16,
    color: colors.text,
    letterSpacing: -0.3,
  },
  headerLogo: {
    fontFamily: fonts.heading,
    fontSize: 13,
    color: colors.primary,
    letterSpacing: -0.2,
    minWidth: 56,
    textAlign: "right",
  },

  scroll: { flex: 1 },
  scrollContent: {
    padding: 16,
    gap: 12,
    paddingBottom: 80,
  },

  introCard: {
    marginBottom: 4,
    gap: 4,
  },
  introTitle: {
    fontFamily: fonts.heading,
    fontSize: 15,
    color: colors.primary,
    letterSpacing: -0.2,
  },
  introSub: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
    lineHeight: 17,
  },

  card: {
    backgroundColor: colors.background,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderLight,
    overflow: "hidden",
  },
  cardSectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.bgIconLight,
  },
  cardSectionIcon: {
    width: 34,
    height: 34,
    borderRadius: 9,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.bgIconLight,
    alignItems: "center",
    justifyContent: "center",
  },
  cardSectionTitle: {
    fontFamily: fonts.heading,
    fontSize: 15,
    color: colors.primary,
    letterSpacing: -0.2,
  },
  cardBody: {
    paddingHorizontal: 16,
    paddingBottom: 4,
  },

  divider: {
    height: 1,
    backgroundColor: colors.borderLight,
  },

  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 14,
    gap: 12,
  },
  toggleRowDisabled: {
    opacity: 0.55,
  },
  toggleLeft: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  rowIconWrap: {
    width: 28,
    height: 28,
    borderRadius: 8,
    backgroundColor: colors.bgPrimaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  rowIconWrapDisabled: {
    backgroundColor: colors.bgLight,
  },
  toggleTextWrap: {
    flex: 1,
    gap: 3,
  },
  toggleTextNoIcon: {
    paddingLeft: 0,
  },
  channelTitle: {
    fontFamily: fonts.heading,
    fontSize: 15,
    color: colors.text,
    letterSpacing: -0.15,
  },
  channelTitleDisabled: {
    color: colors.mutedText,
  },
  channelDesc: {
    fontFamily: fonts.body,
    fontSize: 10,
    color: colors.mutedText,
    lineHeight: 14,
    letterSpacing: 0.1,
  },
  channelDescDisabled: {
    color: colors.borderMuted,
  },

  saveButton: {
    marginTop: 6,
    height: 46,
    borderRadius: 10,
    backgroundColor: colors.primary,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  saveButtonDisabled: {
    opacity: 0.7,
  },
  saveButtonText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: colors.background,
  },
});
