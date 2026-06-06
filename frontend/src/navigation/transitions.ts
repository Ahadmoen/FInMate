import type {
  BottomTabSceneStyleInterpolator,
  TransitionSpec,
} from "@react-navigation/bottom-tabs";
import type { NativeStackNavigationOptions } from "@react-navigation/native-stack";
import { Dimensions, Easing } from "react-native";

import { colors } from "@/styles/global";

const TAB_SLIDE_WIDTH = Dimensions.get("window").width;

/** Full-width horizontal slide; direction follows tab order (no fade). */
export const tabSceneStyleInterpolator: BottomTabSceneStyleInterpolator = ({
  current,
}) => ({
  sceneStyle: {
    opacity: 1,
    overflow: "hidden",
    transform: [
      {
        translateX: current.progress.interpolate({
          inputRange: [-1, 0, 1],
          outputRange: [-TAB_SLIDE_WIDTH, 0, TAB_SLIDE_WIDTH],
        }),
      },
    ],
  },
});

export const tabTransitionSpec: TransitionSpec = {
  animation: "timing",
  config: {
    duration: 320,
    easing: Easing.out(Easing.cubic),
  },
};

export const tabScreenOptions = {
  headerShown: false,
  animation: "shift" as const,
  transitionSpec: tabTransitionSpec,
  sceneStyleInterpolator: tabSceneStyleInterpolator,
  sceneStyle: { backgroundColor: colors.background },
};

export const stackScreenOptions: NativeStackNavigationOptions = {
  headerShown: false,
  animation: "slide_from_right",
  animationDuration: 280,
};

export const stackFadeScreenOptions: NativeStackNavigationOptions = {
  headerShown: false,
  animation: "fade",
  animationDuration: 240,
};
