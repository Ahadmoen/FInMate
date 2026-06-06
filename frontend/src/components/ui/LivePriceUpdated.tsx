import { colors, fonts } from "@/styles/global";
import { formatLivePriceUpdated } from "@/utils/livePrice";
import { ArrowUpRight } from "lucide-react-native";
import {
  Pressable,
  StyleProp,
  StyleSheet,
  Text,
  View,
  type ViewStyle,
} from "react-native";

type Props = {
  at?: string | null;
  /** Use on dark backgrounds (e.g. primary hero card). */
  variant?: "default" | "onPrimary";
  /** When set, shows arrow-in-circle before the label and navigates on press. */
  onPress?: () => void;
  style?: StyleProp<ViewStyle>;
};

export default function LivePriceUpdated({
  at,
  variant = "default",
  onPress,
  style,
}: Props) {
  const label = formatLivePriceUpdated(at);
  if (!label) return null;

  const onPrimary = variant === "onPrimary";
  const muted = onPrimary ? "rgba(255, 255, 255, 0.72)" : colors.mutedText;
  const ringBorder = onPrimary ? "rgba(255, 255, 255, 0.45)" : colors.borderLight;
  const iconColor = onPrimary ? "rgba(255, 255, 255, 0.9)" : colors.primary;

  const rowStyle = [
    styles.row,
    onPress ? styles.rowSpaced : styles.rowCompact,
    styles.cardFooter,
    style,
  ];

  const content = (
    <>
      <Text
        style={[styles.label, { color: muted }, onPress && styles.labelStart]}
        numberOfLines={1}
      >
        {label}
      </Text>
      {onPress ? (
        <View style={[styles.iconRing, { borderColor: ringBorder }]}>
          <ArrowUpRight size={16} color={iconColor} strokeWidth={2.4} />
        </View>
      ) : null}
    </>
  );

  if (onPress) {
    return (
      <Pressable
        style={rowStyle}
        onPress={onPress}
        hitSlop={6}
        accessibilityRole="button"
        accessibilityLabel={`${label}, view stock details`}
      >
        {content}
      </Pressable>
    );
  }

  return <View style={rowStyle}>{content}</View>;
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "stretch",
    width: "100%",
  },
  rowSpaced: {
    justifyContent: "space-between",
  },
  rowCompact: {
    justifyContent: "flex-start",
    gap: 8,
  },
  cardFooter: {
    marginTop: 8,
  },
  iconRing: {
    width: 32,
    height: 32,
    borderRadius: 16,
    borderWidth: 1,
    backgroundColor: "transparent",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  label: {
    fontFamily: fonts.body,
    fontSize: 10,
    letterSpacing: 0.15,
    flexShrink: 1,
  },
  labelStart: {
    textAlign: "left",
    marginRight: 12,
    flex: 1,
  },
});
