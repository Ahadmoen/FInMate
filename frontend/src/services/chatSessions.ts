import type { ChatMessage } from "@/components/chat/types";
import Constants from "expo-constants";
import type { ChatCitationApi, ChatInsightCardApi } from "@/services/chat";
import { mapCitation, mapInsightCard } from "@/services/chat";

const metroHost = Constants.expoConfig?.hostUri?.split(":")[0];
const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  (metroHost ? `http://${metroHost}:3100/api/v1` : "http://localhost:3100/api/v1");

// ─── API types ────────────────────────────────────────────────────────────────

export type ChatSessionSummary = {
  sessionId: string;
  title: string;
  updatedAt: string;
  messageCount: number;
};

type ChatSessionApi = {
  session_id: string;
  title: string;
  updated_at: string;
  message_count: number;
};

type ChatSessionsListApi = {
  sessions: ChatSessionApi[];
};

type ChatMessageApi = {
  id: string;
  role: string;
  content: string;
  created_at: string;
  insight_card?: ChatInsightCardApi | null;
  citations?: ChatCitationApi[];
};

type ChatMessagesApi = {
  session_id: string;
  messages: ChatMessageApi[];
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function extractError(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const d = data as Record<string, unknown>;
  if (typeof d.detail === "string") return d.detail;
  const firstVal = Object.values(d)[0];
  if (Array.isArray(firstVal) && firstVal.length > 0) return String(firstVal[0]);
  return fallback;
}

function mapSessionSummary(s: ChatSessionApi): ChatSessionSummary {
  return {
    sessionId: s.session_id,
    title: s.title?.trim() || "Chat",
    updatedAt: s.updated_at,
    messageCount: s.message_count ?? 0,
  };
}

function mapApiMessage(m: ChatMessageApi): ChatMessage {
  if (m.role === "user") {
    return {
      id: m.id,
      role: "user",
      text: m.content,
    };
  }

  const citations = [...(m.citations ?? [])]
    .sort((a, b) => b.score - a.score)
    .map(mapCitation);

  return {
    id: m.id,
    role: "assistant",
    text: m.content,
    ...(m.insight_card ? { insight: mapInsightCard(m.insight_card) } : {}),
    ...(citations.length > 0 ? { citations } : {}),
  };
}

async function authFetch(
  path: string,
  token: string,
  init?: RequestInit,
): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  });
}

// ─── API ──────────────────────────────────────────────────────────────────────

export async function fetchChatSessions(
  token: string,
  limit = 30,
  offset = 0,
): Promise<ChatSessionSummary[]> {
  const qs = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const response = await authFetch(`/chat/sessions/?${qs}`, token);

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(
      extractError(data, `Failed to load chats (${response.status})`),
    );
  }

  const data = (await response.json()) as ChatSessionsListApi;
  return (data.sessions ?? []).map(mapSessionSummary);
}

export async function fetchChatMessages(
  token: string,
  sessionId: string,
): Promise<{ sessionId: string; messages: ChatMessage[] }> {
  const response = await authFetch(
    `/chat/sessions/${encodeURIComponent(sessionId)}/messages/`,
    token,
  );

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(
      extractError(data, `Failed to load messages (${response.status})`),
    );
  }

  const data = (await response.json()) as ChatMessagesApi;
  return {
    sessionId: data.session_id,
    messages: (data.messages ?? []).map(mapApiMessage),
  };
}

export async function deleteChatSessionApi(
  token: string,
  sessionId: string,
): Promise<void> {
  const response = await authFetch(
    `/chat/sessions/${encodeURIComponent(sessionId)}/`,
    token,
    { method: "DELETE" },
  );

  if (!response.ok && response.status !== 204) {
    const data = await response.json().catch(() => null);
    throw new Error(
      extractError(data, `Failed to delete chat (${response.status})`),
    );
  }
}
