export type ChatCitation = {
  docId: string;
  ticker: string;
  docType: string;
  source: string;
  publishedAt: string;
  score: number;
  faviconLetter: string;
  faviconColor: string;
};

export type StockInsight = {
  symbol: string;
  companyName: string;
  open: number;
  currentPrice: number;
  high: number;
  low: number;
  volume: number;
  currency: string;
  updatedAt: string;
};

export type UserMessage = {
  id: string;
  role: "user";
  text: string;
};

export type AssistantMessage = {
  id: string;
  role: "assistant";
  text: string;
  insight?: StockInsight;
  citations?: ChatCitation[];
};

export type ChatMessage = UserMessage | AssistantMessage;

export type ChatListItem =
  | { type: "day"; id: string; label: string }
  | { type: "user"; id: string; message: UserMessage }
  | { type: "assistant"; id: string; message: AssistantMessage }
  | { type: "typing"; id: string };
