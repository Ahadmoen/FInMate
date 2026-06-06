import { useAuth } from "@/context/AuthContext";
import { fetchUnreadNotificationCount } from "@/services/alertFeed";
import { useFocusEffect } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { AppState } from "react-native";

const POLL_MS = 30_000;

export function useUnreadNotificationCount(): number {
  const { token } = useAuth();
  const [count, setCount] = useState(0);

  const refresh = useCallback(async () => {
    if (!token) {
      setCount(0);
      return;
    }
    try {
      const n = await fetchUnreadNotificationCount(token);
      setCount(n);
    } catch {
      /* keep previous count */
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      refresh();
    }, [refresh]),
  );

  useEffect(() => {
    if (!token) {
      setCount(0);
      return;
    }

    refresh();

    const interval = setInterval(() => {
      if (AppState.currentState === "active") {
        refresh();
      }
    }, POLL_MS);

    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") {
        refresh();
      }
    });

    return () => {
      clearInterval(interval);
      sub.remove();
    };
  }, [token, refresh]);

  return count;
}
