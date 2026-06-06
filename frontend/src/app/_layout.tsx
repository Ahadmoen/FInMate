import "react-native-reanimated";

import LoadingScreen from "@/components/ui/LoadingScreen";
import { usePushNotifications } from "@/hooks/usePushNotifications";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import {
  stackFadeScreenOptions,
  stackScreenOptions,
} from "@/navigation/transitions";
import { Inter_600SemiBold } from "@expo-google-fonts/inter";
import { Montserrat_400Regular, Montserrat_500Medium } from "@expo-google-fonts/montserrat";
import { useFonts } from "expo-font";
import { Stack, useRouter, useSegments } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useEffect } from "react";
import { LogBox } from "react-native";

// Suppress deprecation warning emitted by @react-native-community/datetimepicker
// which internally still renders RN's own SafeAreaView on iOS. Our app correctly
// uses react-native-safe-area-context everywhere in first-party code.
LogBox.ignoreLogs([
  "SafeAreaView has been deprecated",
  // Expo dev wrapper calls useKeepAwake on Android; reopening the app before the
  // Activity is ready rejects with this message. Harmless in dev, absent in prod.
  "Unable to activate keep awake",
]);

SplashScreen.preventAutoHideAsync();

function AuthGuard() {
  const { token, isLoading } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;

    const firstSegment = segments[0] as string | undefined;

    const isProtectedRoute = firstSegment === "(tabs)";
    const isPublicRoute =
      !firstSegment ||
      firstSegment === "signup" ||
      firstSegment === "signup-flow";

    if (!token && isProtectedRoute) {
      router.replace("/");
    } else if (token && isPublicRoute) {
      router.replace("/(tabs)/dashboard");
    }
  }, [token, isLoading, segments]);

  return null;
}

function RootLayoutNav() {
  const { isLoading } = useAuth();
  usePushNotifications();

  if (isLoading) {
    return <LoadingScreen />;
  }

  return (
    <>
      <AuthGuard />
      <Stack screenOptions={stackScreenOptions}>
        <Stack.Screen name="index" options={stackFadeScreenOptions} />
        <Stack.Screen name="signup" options={stackFadeScreenOptions} />
        <Stack.Screen name="signup-flow" options={stackFadeScreenOptions} />
        <Stack.Screen
          name="(tabs)"
          options={{ ...stackFadeScreenOptions, animationDuration: 300 }}
        />
        <Stack.Screen name="personal-info" />
        <Stack.Screen name="alert-settings" />
        <Stack.Screen name="manage-portfolio" />
        <Stack.Screen
          name="buy-sell-stock"
          options={{ animation: "slide_from_bottom", animationDuration: 300 }}
        />
        <Stack.Screen name="financial-profile" />
        <Stack.Screen name="privacy-policy" />
        <Stack.Screen name="notifications" />
        <Stack.Screen name="notification/[id]" />
        <Stack.Screen name="stock-insight/[ticker]" />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    Inter_600SemiBold,
    Montserrat_400Regular,
    Montserrat_500Medium,
  });

  useEffect(() => {
    if (fontsLoaded) {
      SplashScreen.hideAsync();
    }
  }, [fontsLoaded]);

  if (!fontsLoaded) {
    return null;
  }

  return (
    <AuthProvider>
      <RootLayoutNav />
    </AuthProvider>
  );
}
