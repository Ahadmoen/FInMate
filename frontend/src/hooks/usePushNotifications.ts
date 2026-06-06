import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { useEffect, useRef } from "react";
import { Platform } from "react-native";

import { useAuth } from "@/context/AuthContext";
import { registerDeviceToken } from "@/services/deviceTokens";

// Must be called at module level — controls how notifications behave while the
// app is in the foreground. Runs once when this module is first imported.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export function usePushNotifications() {
  const { token } = useAuth();
  const notificationListener = useRef<Notifications.EventSubscription | null>(null);
  const responseListener = useRef<Notifications.EventSubscription | null>(null);

  useEffect(() => {
    if (!token) return;

    registerForPushAsync().then((pushToken) => {
      if (!pushToken) return;
      // Fire-and-forget — registration failure must never crash the app
      registerDeviceToken(token, pushToken).catch(() => undefined);
    });

    // Fires when a notification arrives while the app is open
    notificationListener.current =
      Notifications.addNotificationReceivedListener((_notification) => {
        // Banner is already shown by setNotificationHandler above
      });

    // Fires when the user taps a notification from any app state
    responseListener.current =
      Notifications.addNotificationResponseReceivedListener((response) => {
        const data = response.notification.request.content.data as {
          alert_id?: string;
          ticker?: string;
          type?: string;
        };
        // TODO: navigate to relevant screen, e.g. router.push(`/stock-insight/${data.ticker}`)
        void data;
      });

    return () => {
      notificationListener.current?.remove();
      responseListener.current?.remove();
    };
  }, [token]);
}

async function registerForPushAsync(): Promise<string | null> {
  // Expo push tokens are not issued on simulators or emulators
  if (!Device.isDevice) return null;

  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("default", {
      name: "FinMate Alerts",
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: "#208AEF",
    });
  }

  const { status: existing } = await Notifications.getPermissionsAsync();
  const finalStatus =
    existing === "granted"
      ? existing
      : (await Notifications.requestPermissionsAsync()).status;

  if (finalStatus !== "granted") return null;

  const projectId =
    Constants.expoConfig?.extra?.eas?.projectId ??
    Constants.easConfig?.projectId;

  if (!projectId) {
    console.warn("[usePushNotifications] EAS projectId not found in app.json");
    return null;
  }

  const { data: pushToken } = await Notifications.getExpoPushTokenAsync({ projectId });
  return pushToken;
}
