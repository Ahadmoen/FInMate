import type { AssistantMessage, ChatCitation, StockInsight } from "@/components/chat/types";
import { resolveChatApiBase } from "@/services/resolveChatApiBase";

export const CHAT_API_BASE = resolveChatApiBase();

// ─── API types ────────────────────────────────────────────────────────────────

export type ChatInsightCardApi = {
  symbol: string;
  company_name: string;
  open: number;
  current_price: number;
  high: number;
  low: number;
  volume: number;
  currency: string;
  updated_at: string;
};

export type ChatCitationApi = {
  ticker: string;
  doc_id: string;
  doc_type: string;
  source: string;
  published_at: string;
  score: number;
};

export type ChatAskResponseApi = {
  answer: string;
  session_id: string;
  insight_card: ChatInsightCardApi | null;
  citations: ChatCitationApi[];
};

export type ChatAskResult = {
  message: AssistantMessage;
  sessionId: string;
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

const FAVICON_COLORS = [
  "#1A4A4A",
  "#2F6B66",
  "#1E9E6A",
  "#C0413F",
  "#255B65",
  "#5FB8AC",
];

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash << 5) - hash + value.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

export function sourceInitials(source: string): string {
  const cleaned = source.replace(/[^a-zA-Z]/g, " ");
  const words = cleaned.trim().split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  const compact = source.replace(/[^a-zA-Z]/g, "");
  if (compact.length >= 2) return compact.slice(0, 2).toUpperCase();
  return (compact[0] ?? "?").toUpperCase();
}

function faviconColorForSource(source: string): string {
  return FAVICON_COLORS[hashString(source) % FAVICON_COLORS.length];
}

export function mapInsightCard(card: ChatInsightCardApi): StockInsight {
  return {
    symbol: card.symbol,
    companyName: card.company_name,
    open: card.open,
    currentPrice: card.current_price,
    high: card.high,
    low: card.low,
    volume: card.volume,
    currency: card.currency,
    updatedAt: card.updated_at,
  };
}

export function mapCitation(c: ChatCitationApi): ChatCitation {
  return {
    docId: c.doc_id,
    ticker: c.ticker,
    docType: c.doc_type,
    source: c.source,
    publishedAt: c.published_at,
    score: c.score,
    faviconLetter: sourceInitials(c.source),
    faviconColor: faviconColorForSource(c.source),
  };
}

export function mapChatResponse(
  res: ChatAskResponseApi,
  messageId: string,
): ChatAskResult {
  const citations = [...(res.citations ?? [])]
    .sort((a, b) => b.score - a.score)
    .map(mapCitation);

  const message: AssistantMessage = {
    id: messageId,
    role: "assistant",
    text: res.answer,
    ...(res.insight_card ? { insight: mapInsightCard(res.insight_card) } : {}),
    ...(citations.length > 0 ? { citations } : {}),
  };

  return {
    message,
    sessionId: res.session_id ?? "",
  };
}

// ─── API ──────────────────────────────────────────────────────────────────────

export async function askChat(
  token: string,
  message: string,
  sessionId: string,
  messageId: string,
): Promise<ChatAskResult> {
  const url = `${CHAT_API_BASE}/v1/chat/ask`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        message,
        session_id: sessionId,
      }),
    });
  } catch (err) {
    const reason =
      err instanceof Error ? err.message : "Network request failed";
    throw new Error(
      `${reason} (URL: ${url}). ` +
        "Start the chat service on port 8000 bound to 0.0.0.0, e.g. " +
        "uvicorn main:app --host 0.0.0.0 --port 8000",
    );
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const errBody = await response.json();
      if (typeof errBody?.detail === "string") detail = errBody.detail;
      else if (typeof errBody?.message === "string") detail = errBody.message;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }

  const data = (await response.json()) as ChatAskResponseApi;
  return mapChatResponse(data, messageId);
}
