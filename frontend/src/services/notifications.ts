import Constants from "expo-constants";

const metroHost = Constants.expoConfig?.hostUri?.split(":")[0];
const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  (metroHost ? `http://${metroHost}:3100/api/v1` : "http://localhost:3100/api/v1");

export type NotificationPreferences = {
  id: string;
  in_app_enabled: boolean;
  email_enabled: boolean;
  whatsapp_enabled: boolean;
  slack_enabled: boolean;
  pre_market: boolean;
  mid_session: boolean;
  post_market: boolean;
};

export type NotificationPreferencesInput = Omit<NotificationPreferences, "id">;

function extractError(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const d = data as Record<string, unknown>;
  if (typeof d.detail === "string") return d.detail;
  const firstVal = Object.values(d)[0];
  if (Array.isArray(firstVal) && firstVal.length > 0) return String(firstVal[0]);
  return fallback;
}

export async function fetchNotificationPreferences(
  token: string,
): Promise<NotificationPreferences> {
  const response = await fetch(`${API_BASE}/users/notifications/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error("Failed to load notification preferences.");
  }
  return response.json();
}

export async function updateNotificationPreferences(
  token: string,
  data: NotificationPreferencesInput,
): Promise<NotificationPreferences> {
  const response = await fetch(`${API_BASE}/users/notifications/`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const json = await response.json().catch(() => null);
    throw new Error(extractError(json, "Failed to save notification preferences."));
  }
  return response.json();
}
