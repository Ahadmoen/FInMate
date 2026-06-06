import Constants from "expo-constants";
import { Platform } from "react-native";

/**
 * Resolves the chat microservice base URL (port 8000).
 *
 * In Expo Go, Metro's host is the dev machine LAN IP — prefer that in dev so
 * physical devices reach the same machine as the bundler.
 *
 * The chat process must listen on 0.0.0.0:8000 (not only 127.0.0.1) for
 * phones on the same Wi‑Fi to connect.
 */
export function resolveChatApiBase(): string {
  // An explicit env override always wins (e.g. the deployed cloud chat service),
  // even in dev — otherwise the Metro-host fallback below would shadow it.
  const fromEnv = process.env.EXPO_PUBLIC_CHAT_API_BASE_URL?.replace(/\/$/, "");
  if (fromEnv) return fromEnv;

  // No override: in dev, prefer the Metro host (chat service runs on the dev machine).
  const metroHost = Constants.expoConfig?.hostUri?.split(":")[0];
  if (__DEV__ && metroHost) {
    return `http://${metroHost}:8000`;
  }

  const mainApi = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (mainApi) {
    try {
      const { hostname } = new URL(mainApi);
      return `http://${hostname}:8000`;
    } catch {
      // ignore invalid URL
    }
  }

  if (Platform.OS === "android") {
    return "http://10.0.2.2:8000";
  }

  return "http://localhost:8000";
}
