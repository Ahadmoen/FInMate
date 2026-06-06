import AivaAvatar from "@/components/chat/AivaAvatar";
import { chatColors, chatShadow } from "@/components/chat/chatTheme";
import { fonts } from "@/styles/global";
import { useEffect, useRef } from "react";
import { Animated, Easing, StyleSheet, Text, View } from "react-native";

type Props = {
  exiting?: boolean;
  onExitComplete?: () => void;
};

function Dot({ delay }: { delay: number }) {
  const opacity = useRef(new Animated.Value(0.35)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.delay(delay),
        Animated.timing(opacity, {
          toValue: 1,
          duration: 500,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(opacity, {
          toValue: 0.35,
          duration: 500,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [delay, opacity]);

  return <Animated.View style={[styles.dot, { opacity }]} />;
}

export default function TypingIndicator({
  exiting = false,
  onExitComplete,
}: Props) {
  const containerOpacity = useRef(new Animated.Value(0)).current;
  const containerTranslateY = useRef(new Animated.Value(6)).current;
  const hasEntered = useRef(false);

  useEffect(() => {
    if (hasEntered.current) return;
    hasEntered.current = true;

    Animated.parallel([
      Animated.timing(containerOpacity, {
        toValue: 1,
        duration: 300,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
      Animated.timing(containerTranslateY, {
        toValue: 0,
        duration: 300,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
    ]).start();
  }, [containerOpacity, containerTranslateY]);

  useEffect(() => {
    if (!exiting) return;

    Animated.parallel([
      Animated.timing(containerOpacity, {
        toValue: 0,
        duration: 300,
        easing: Easing.in(Easing.cubic),
        useNativeDriver: true,
      }),
      Animated.timing(containerTranslateY, {
        toValue: 4,
        duration: 300,
        easing: Easing.in(Easing.cubic),
        useNativeDriver: true,
      }),
    ]).start(({ finished }) => {
      if (finished) onExitComplete?.();
    });
  }, [containerOpacity, containerTranslateY, exiting, onExitComplete]);

  return (
    <Animated.View
      style={[
        styles.group,
        {
          opacity: containerOpacity,
          transform: [{ translateY: containerTranslateY }],
        },
      ]}
    >
      <AivaAvatar />
      <View style={styles.bubble}>
        <View style={styles.dots}>
          <Dot delay={0} />
          <Dot delay={160} />
          <Dot delay={320} />
        </View>
        <Text style={styles.analyzingText}>Analyzing market data…</Text>
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  group: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
  },
  bubble: {
    backgroundColor: chatColors.card,
    borderTopLeftRadius: 6,
    borderTopRightRadius: 20,
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 20,
    paddingVertical: 14,
    paddingHorizontal: 16,
    ...chatShadow.card,
  },
  dots: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: chatColors.tealAccent,
  },
  analyzingText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11.5,
    color: chatColors.muted2,
    marginTop: 10,
  },
});
