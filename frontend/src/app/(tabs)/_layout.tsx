import { tabScreenOptions } from "@/navigation/transitions";
import { colors, fonts } from "@/styles/global";
import type { BottomTabBarProps } from "@react-navigation/bottom-tabs";
import { Tabs } from "expo-router";
import {
  Bot,
  LayoutGrid,
  Newspaper,
  PieChart,
  TrendingUp,
} from "lucide-react-native";
import { useEffect, useRef } from "react";
import { LayoutChangeEvent, Pressable, StyleSheet, Text, View } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSpring,
} from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

// ─── Constants ────────────────────────────────────────────────────────────────

const ACTIVE_COLOR = "#4ECDC4";
const INACTIVE_COLOR = "rgba(255,255,255,0.5)";
const INDICATOR_SPRING = { damping: 18, stiffness: 220, mass: 0.8 };
const PRESS_SPRING = { damping: 15, stiffness: 400 };

type TabName = "portfolio" | "chatbot" | "dashboard" | "news" | "insights";

type TabLayout = { x: number; width: number };

const TAB_CONFIG: Record<
  TabName,
  {
    label: string;
    Icon: React.ComponentType<{
      size: number;
      color: string;
      strokeWidth: number;
    }>;
  }
> = {
  portfolio: { label: "Analytics", Icon: PieChart },
  chatbot: { label: "Chat", Icon: Bot },
  dashboard: { label: "Dashboard", Icon: LayoutGrid },
  news: { label: "News", Icon: Newspaper },
  insights: { label: "Insights", Icon: TrendingUp },
};

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

// ─── Animated tab item ────────────────────────────────────────────────────────

function AnimatedTabItem({
  label,
  Icon,
  isFocused,
  onPress,
  onLayout,
}: {
  label: string;
  Icon: (typeof TAB_CONFIG)[TabName]["Icon"];
  isFocused: boolean;
  onPress: () => void;
  onLayout: (event: LayoutChangeEvent) => void;
}) {
  const scale = useSharedValue(isFocused ? 1 : 0.92);
  const pressed = useSharedValue(0);

  useEffect(() => {
    scale.value = withSpring(isFocused ? 1 : 0.92, PRESS_SPRING);
  }, [isFocused, scale]);

  const animatedContentStyle = useAnimatedStyle(() => ({
    transform: [
      {
        scale: scale.value * (1 - pressed.value * 0.08),
      },
    ],
  }));

  const iconColor = isFocused ? ACTIVE_COLOR : INACTIVE_COLOR;

  return (
    <AnimatedPressable
      onPress={onPress}
      onPressIn={() => {
        pressed.value = withSpring(1, PRESS_SPRING);
      }}
      onPressOut={() => {
        pressed.value = withSpring(0, PRESS_SPRING);
      }}
      onLayout={onLayout}
      style={styles.tabItem}
      android_ripple={{ color: "transparent" }}
    >
      <Animated.View style={[styles.tabContent, animatedContentStyle]}>
        <Icon
          size={22}
          color={iconColor}
          strokeWidth={isFocused ? 2.2 : 1.6}
        />
        <Text
          style={[
            styles.tabLabel,
            { color: iconColor, opacity: isFocused ? 1 : 0.85 },
            isFocused && styles.tabLabelActive,
          ]}
        >
          {label}
        </Text>
      </Animated.View>
    </AnimatedPressable>
  );
}

// ─── Custom Floating Pill Tab Bar ─────────────────────────────────────────────

function CustomTabBar({ state, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const tabLayouts = useRef<Record<number, TabLayout>>({});
  const indicatorX = useSharedValue(0);
  const indicatorWidth = useSharedValue(0);
  const indicatorReady = useSharedValue(0);

  const moveIndicator = (index: number) => {
    const layout = tabLayouts.current[index];
    if (!layout) return;
    indicatorX.value = withSpring(layout.x, INDICATOR_SPRING);
    indicatorWidth.value = withSpring(layout.width, INDICATOR_SPRING);
    indicatorReady.value = 1;
  };

  useEffect(() => {
    moveIndicator(state.index);
  }, [state.index]);

  const indicatorStyle = useAnimatedStyle(() => ({
    opacity: indicatorReady.value,
    transform: [{ translateX: indicatorX.value }],
    width: indicatorWidth.value,
  }));

  const visibleRoutes = state.routes
    .map((route, index) => ({ route, index }))
    .filter(({ route }) => TAB_CONFIG[route.name as TabName]);

  return (
    <View
      style={[
        styles.outerContainer,
        { paddingBottom: Math.max(insets.bottom, 10) + 4 },
      ]}
    >
      <View style={styles.pill}>
        <Animated.View style={[styles.indicator, indicatorStyle]} />
        {visibleRoutes.map(({ route, index }) => {
          const isFocused = state.index === index;
          const config = TAB_CONFIG[route.name as TabName];
          const { Icon, label } = config;

          const onPress = () => {
            const event = navigation.emit({
              type: "tabPress",
              target: route.key,
              canPreventDefault: true,
            });
            if (!isFocused && !event.defaultPrevented) {
              navigation.navigate(route.name);
            }
          };

          return (
            <AnimatedTabItem
              key={route.key}
              label={label}
              Icon={Icon}
              isFocused={isFocused}
              onPress={onPress}
              onLayout={(event) => {
                const { x, width } = event.nativeEvent.layout;
                tabLayouts.current[index] = { x, width };
                if (state.index === index) {
                  moveIndicator(index);
                }
              }}
            />
          );
        })}
      </View>
    </View>
  );
}

// ─── Layout ───────────────────────────────────────────────────────────────────

export default function TabsLayout() {
  return (
    <Tabs
      tabBar={(props) => <CustomTabBar {...props} />}
      screenOptions={tabScreenOptions}
    >
      <Tabs.Screen name="portfolio" />
      <Tabs.Screen name="chatbot" />
      <Tabs.Screen name="dashboard" />
      <Tabs.Screen name="news" />
      <Tabs.Screen name="insights" />
      <Tabs.Screen name="profile" options={{ href: null }} />
      <Tabs.Screen name="rising-stars" options={{ href: null }} />
    </Tabs>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  outerContainer: {
    backgroundColor: colors.background,
    paddingHorizontal: 18,
    paddingTop: 10,
  },
  pill: {
    flexDirection: "row",
    backgroundColor: colors.primary,
    borderRadius: 30,
    paddingVertical: 13,
    paddingHorizontal: 4,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4,
    shadowRadius: 14,
    elevation: 12,
  },
  indicator: {
    position: "absolute",
    top: 6,
    bottom: 6,
    left: 0,
    borderRadius: 22,
    backgroundColor: "rgba(78, 205, 196, 0.2)",
  },
  tabItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  tabContent: {
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
  },
  tabLabel: {
    fontFamily: fonts.body,
    fontSize: 10,
  },
  tabLabelActive: {
    fontFamily: fonts.bodyMedium,
  },
});
