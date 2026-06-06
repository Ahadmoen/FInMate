import Constants from "expo-constants";
import { Platform } from "react-native";

const metroHost = Constants.expoConfig?.hostUri?.split(":")[0];
const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  (metroHost ? `http://${metroHost}:8000/api/v1` : "http://localhost:8000/api/v1");

export async function registerDeviceToken(
  authToken: string,
  pushToken: string,
): Promise<void> {
  const response = await fetch(`${API_BASE}/users/device-tokens/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify({
      token: pushToken,
      platform: Platform.OS,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to register device push token.");
  }
}
