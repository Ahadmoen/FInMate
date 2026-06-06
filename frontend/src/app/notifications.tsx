import { useAuth } from "@/context/AuthContext";
import {
  fetchNotifications,
  formatNotificationTime,
  markAllNotificationsRead,
  type FeedNotification,
} from "@/services/alertFeed";
import { colors, fonts } from "@/styles/global";
import { useFocusEffect, useRouter } from "expo-router";
import { Bell, ChevronLeft } from "lucide-react-native";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

const FEED_DAYS = 10;

function NotificationCard({
  item,
  onPress,
}: {
  item: FeedNotification;
  onPress: () => void;
}) {
  const unread = item.read_at == null;

  return (
    <Pressable
      style={[styles.card, unread && styles.cardUnread]}
      onPress={onPress}
      accessibilityRole="button"
    >
      {unread ? <View style={styles.unreadDot} /> : null}
      <View style={[styles.cardTop, unread && styles.cardTopUnread]}>
        <Text style={styles.cardTitle} numberOfLines={2}>
          {item.title || item.ticker || "Notification"}
        </Text>
        <Text style={styles.cardTime}>{formatNotificationTime(item.created_at)}</Text>
      </View>
      <Text style={styles.cardBody} numberOfLines={2}>
        {item.body || item.reason || "Tap to read the full alert."}
      </Text>
    </Pressable>
  );
}

export default function NotificationsScreen() {
  const router = useRouter();
  const { token } = useAuth();

  const [items, setItems] = useState<FeedNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);

  const load = useCallback(
    async (isRefresh = false) => {
      if (!token) return;
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      setError(null);
      try {
        const data = await fetchNotifications(token, FEED_DAYS);
        setItems(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load notifications.");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [token],
  );

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const handleMarkAllRead = async () => {
    if (!token || clearing) return;
    setClearing(true);
    try {
      await markAllNotificationsRead(token);
      setItems((prev) => prev.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })));
    } catch {
      /* ignore — list still usable */
    } finally {
      setClearing(false);
    }
  };

  const hasUnread = Array.isArray(items) && items.some((n) => n.read_at == null);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <Pressable style={styles.backBtn} onPress={() => router.back()} hitSlop={10}>
          <ChevronLeft size={22} color={colors.primary} strokeWidth={2} />
        </Pressable>
        <Text style={styles.headerTitle}>Notifications</Text>
        {hasUnread ? (
          <Pressable
            style={styles.clearBtn}
            onPress={handleMarkAllRead}
            disabled={clearing}
            hitSlop={8}
          >
            <Text style={styles.clearBtnText}>{clearing ? "…" : "Clear all"}</Text>
          </Pressable>
        ) : (
          <View style={styles.backBtn} />
        )}
      </View>

      <Text style={styles.subtitle}>Last {FEED_DAYS} days</Text>

      {loading && !refreshing ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : error ? (
        <View style={styles.centered}>
          <Text style={styles.errorText}>{error}</Text>
          <Pressable style={styles.retryBtn} onPress={() => load()}>
            <Text style={styles.retryText}>Try again</Text>
          </Pressable>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => load(true)} />
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <View style={styles.emptyIcon}>
                <Bell size={28} color={colors.mutedText} strokeWidth={1.6} />
              </View>
              <Text style={styles.emptyTitle}>No notifications yet</Text>
              <Text style={styles.emptyBody}>
                Alerts from the last {FEED_DAYS} days will show up here when FinMate sends
                top picks, digests, or position alerts.
              </Text>
            </View>
          }
          renderItem={({ item }) => (
            <NotificationCard
              item={item}
              onPress={() => router.push(`/notification/${item.id}`)}
            />
          )}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  backBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    flex: 1,
    fontFamily: fonts.heading,
    fontSize: 18,
    color: colors.text,
    textAlign: "center",
  },
  clearBtn: {
    minWidth: 40,
    paddingHorizontal: 4,
    alignItems: "flex-end",
    justifyContent: "center",
  },
  clearBtnText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.primary,
  },
  subtitle: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
    paddingHorizontal: 20,
    paddingTop: 10,
    paddingBottom: 4,
  },
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 24,
    paddingTop: 8,
    flexGrow: 1,
  },
  card: {
    backgroundColor: colors.bgLight,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderLight,
    padding: 14,
    marginBottom: 10,
    position: "relative",
  },
  cardUnread: {
    borderColor: colors.themeLight,
    backgroundColor: colors.bgPrimaryLight,
  },
  cardTop: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 10,
    marginBottom: 8,
  },
  cardTopUnread: {
    paddingLeft: 10,
  },
  cardTitle: {
    flex: 1,
    fontFamily: fonts.heading,
    fontSize: 15,
    color: colors.text,
    lineHeight: 20,
  },
  cardTime: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: colors.mutedText,
  },
  cardBody: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 19,
  },
  unreadDot: {
    position: "absolute",
    top: 12,
    left: 8,
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.primary,
  },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  errorText: {
    fontFamily: fonts.body,
    fontSize: 14,
    color: colors.error,
    textAlign: "center",
    marginBottom: 12,
  },
  retryBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: colors.primary,
  },
  retryText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: "#FFFFFF",
  },
  empty: {
    alignItems: "center",
    paddingTop: 48,
    paddingHorizontal: 24,
  },
  emptyIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.bgLight,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  emptyTitle: {
    fontFamily: fonts.heading,
    fontSize: 17,
    color: colors.text,
    marginBottom: 8,
  },
  emptyBody: {
    fontFamily: fonts.body,
    fontSize: 14,
    color: colors.mutedText,
    textAlign: "center",
    lineHeight: 20,
  },
});
