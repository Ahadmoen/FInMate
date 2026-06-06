import AssistantMessageGroup from "@/components/chat/AssistantMessageGroup";
import ChatComposer from "@/components/chat/ChatComposer";
import ChatEmptyState from "@/components/chat/ChatEmptyState";
import ChatToolbar from "@/components/chat/ChatToolbar";
import RecentChatsDrawer from "@/components/chat/RecentChatsDrawer";
import { chatColors } from "@/components/chat/chatTheme";
import DaySeparator from "@/components/chat/DaySeparator";
import RevealIn from "@/components/chat/RevealIn";
import TypingIndicator from "@/components/chat/TypingIndicator";
import type { AssistantMessage, ChatListItem, ChatMessage } from "@/components/chat/types";
import UserBubble from "@/components/chat/UserBubble";
import ScreenHeader from "@/components/ui/ScreenHeader";
import { useAuth } from "@/context/AuthContext";
import { askChat } from "@/services/chat";
import {
  deleteChatSessionApi,
  fetchChatMessages,
  fetchChatSessions,
  type ChatSessionSummary,
} from "@/services/chatSessions";
import { colors, fonts } from "@/styles/global";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

const TYPING_SHOW_DELAY_MS = 630;
const TYPING_VISIBLE_MS = 1900;

function createId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function buildListItems(
  messages: ChatMessage[],
  showTyping: boolean,
): ChatListItem[] {
  if (messages.length === 0 && !showTyping) return [];

  const items: ChatListItem[] = [
    { type: "day", id: "day-today", label: "Today" },
  ];

  for (const message of messages) {
    if (message.role === "user") {
      items.push({ type: "user", id: message.id, message });
    } else {
      items.push({ type: "assistant", id: message.id, message });
    }
  }

  if (showTyping) {
    items.push({ type: "typing", id: "typing-indicator" });
  }

  return items;
}

export default function ChatbotTabScreen() {
  const { token } = useAuth();
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [savedSessions, setSavedSessions] = useState<ChatSessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [threadLoading, setThreadLoading] = useState(false);
  const [recentDrawerOpen, setRecentDrawerOpen] = useState(false);
  const [isTypingVisible, setIsTypingVisible] = useState(false);
  const [typingExiting, setTypingExiting] = useState(false);
  const [isAwaitingReply, setIsAwaitingReply] = useState(false);
  const inputRef = useRef<TextInput>(null);
  const listRef = useRef<FlatList<ChatListItem>>(null);
  const typingShowTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typingMinTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingReplyRef = useRef<AssistantMessage | null>(null);
  const apiDoneRef = useRef(false);
  const minTypingDoneRef = useRef(false);
  const sessionIdRef = useRef(sessionId);

  sessionIdRef.current = sessionId;

  const refreshSavedSessions = useCallback(async () => {
    if (!token) {
      setSavedSessions([]);
      return;
    }
    try {
      const list = await fetchChatSessions(token);
      setSavedSessions(list);
      setSessionsError(null);
    } catch (err) {
      setSessionsError(
        err instanceof Error ? err.message : "Could not load recent chats.",
      );
    }
  }, [token]);

  useEffect(() => {
    if (token) refreshSavedSessions();
    else setSavedSessions([]);
  }, [token, refreshSavedSessions]);

  const showTyping = isTypingVisible || typingExiting;
  const listItems = useMemo(
    () => buildListItems(messages, showTyping),
    [messages, showTyping],
  );

  const showEmptyState =
    messages.length === 0 && !showTyping && !threadLoading;
  const composerDisabled = isAwaitingReply || !token || threadLoading;
  const toolbarDisabled = !token || isAwaitingReply || threadLoading;

  const scrollToEnd = useCallback(() => {
    requestAnimationFrame(() => {
      listRef.current?.scrollToEnd({ animated: true });
    });
  }, []);

  useEffect(() => {
    if (!showEmptyState) scrollToEnd();
  }, [listItems, showEmptyState, scrollToEnd]);

  const clearTimers = useCallback(() => {
    if (typingShowTimerRef.current) {
      clearTimeout(typingShowTimerRef.current);
      typingShowTimerRef.current = null;
    }
    if (typingMinTimerRef.current) {
      clearTimeout(typingMinTimerRef.current);
      typingMinTimerRef.current = null;
    }
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  const tryStartTypingExit = useCallback(() => {
    if (!apiDoneRef.current || !minTypingDoneRef.current) return;
    setTypingExiting(true);
  }, []);

  const finishTypingExit = useCallback(() => {
    const reply = pendingReplyRef.current;
    pendingReplyRef.current = null;
    setTypingExiting(false);
    setIsTypingVisible(false);
    setIsAwaitingReply(false);
    apiDoneRef.current = false;
    minTypingDoneRef.current = false;

    if (reply) {
      setMessages((prev) => [...prev, reply]);
      void refreshSavedSessions();
    }
  }, [refreshSavedSessions]);

  const resetChatState = useCallback(() => {
    clearTimers();
    pendingReplyRef.current = null;
    apiDoneRef.current = false;
    minTypingDoneRef.current = false;
    setMessages([]);
    setSessionId("");
    sessionIdRef.current = "";
    setMessage("");
    setIsTypingVisible(false);
    setTypingExiting(false);
    setIsAwaitingReply(false);
    inputRef.current?.blur();
  }, [clearTimers]);

  const handleNewChat = useCallback(() => {
    if (isAwaitingReply) return;
    resetChatState();
  }, [isAwaitingReply, resetChatState]);

  const handleOpenRecent = useCallback(async () => {
    setRecentDrawerOpen(true);
    setSessionsLoading(true);
    setSessionsError(null);
    try {
      await refreshSavedSessions();
    } finally {
      setSessionsLoading(false);
    }
  }, [refreshSavedSessions]);

  const handleSelectSession = useCallback(
    async (session: ChatSessionSummary) => {
      if (!token || isAwaitingReply) return;

      setRecentDrawerOpen(false);
      setThreadLoading(true);
      setMessages([]);

      try {
        const thread = await fetchChatMessages(token, session.sessionId);
        sessionIdRef.current = thread.sessionId;
        setSessionId(thread.sessionId);
        setMessages(thread.messages);
        setMessage("");
      } catch (err) {
        const detail =
          err instanceof Error ? err.message : "Could not load this chat.";
        setMessages([
          {
            id: createId("assistant"),
            role: "assistant",
            text: `Sorry, I couldn't load that conversation.\n\n${detail}`,
          },
        ]);
        sessionIdRef.current = session.sessionId;
        setSessionId(session.sessionId);
      } finally {
        setThreadLoading(false);
      }
    },
    [isAwaitingReply, token],
  );

  const handleDeleteSession = useCallback(
    async (deletedSessionId: string) => {
      if (!token) return;

      try {
        await deleteChatSessionApi(token, deletedSessionId);
        if (sessionId === deletedSessionId) {
          resetChatState();
        }
        await refreshSavedSessions();
      } catch (err) {
        setSessionsError(
          err instanceof Error ? err.message : "Could not delete chat.",
        );
      }
    },
    [token, sessionId, resetChatState, refreshSavedSessions],
  );

  const dispatchMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isAwaitingReply) return;

      if (!token) return;

      clearTimers();

      const userMessage: ChatMessage = {
        id: createId("user"),
        role: "user",
        text: trimmed,
      };

      const assistantId = createId("assistant");
      pendingReplyRef.current = null;
      apiDoneRef.current = false;
      minTypingDoneRef.current = false;

      setMessages((prev) => [...prev, userMessage]);
      setMessage("");
      setIsAwaitingReply(true);
      setTypingExiting(false);
      setIsTypingVisible(false);

      typingShowTimerRef.current = setTimeout(() => {
        setIsTypingVisible(true);
        typingShowTimerRef.current = null;
      }, TYPING_SHOW_DELAY_MS);

      typingMinTimerRef.current = setTimeout(() => {
        minTypingDoneRef.current = true;
        typingMinTimerRef.current = null;
        tryStartTypingExit();
      }, TYPING_SHOW_DELAY_MS + TYPING_VISIBLE_MS);

      askChat(token, trimmed, sessionId, assistantId)
        .then((result) => {
          pendingReplyRef.current = result.message;
          sessionIdRef.current = result.sessionId;
          setSessionId(result.sessionId);
          apiDoneRef.current = true;
          tryStartTypingExit();
        })
        .catch((err: unknown) => {
          const detail =
            err instanceof Error ? err.message : "Something went wrong.";
          pendingReplyRef.current = {
            id: assistantId,
            role: "assistant",
            text: `Sorry, I couldn't reach AIVA right now.\n\n${detail}`,
          };
          apiDoneRef.current = true;
          tryStartTypingExit();
        });
    },
    [clearTimers, isAwaitingReply, sessionId, token, tryStartTypingExit],
  );

  const handleSend = () => dispatchMessage(message);

  const handleSuggestion = (label: string) => {
    setMessage(label);
    inputRef.current?.focus();
  };

  const renderItem = ({ item }: { item: ChatListItem }) => {
    switch (item.type) {
      case "day":
        return <DaySeparator label={item.label} />;
      case "user":
        return (
          <RevealIn>
            <UserBubble text={item.message.text} />
          </RevealIn>
        );
      case "assistant":
        return <AssistantMessageGroup message={item.message} />;
      case "typing":
        return (
          <TypingIndicator
            exiting={typingExiting}
            onExitComplete={finishTypingExit}
          />
        );
      default:
        return null;
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScreenHeader />

      {token ? (
        <ChatToolbar
          onRecentChats={handleOpenRecent}
          onNewChat={handleNewChat}
          disabled={toolbarDisabled}
          recentCount={savedSessions.length}
        />
      ) : null}

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        keyboardVerticalOffset={Platform.OS === "ios" ? 0 : 0}
      >
        <View style={styles.body}>
          {!token ? (
            <View style={styles.authBanner}>
              <Text style={styles.authBannerText}>
                Sign in to chat with AIVA.
              </Text>
            </View>
          ) : null}

          {threadLoading ? (
            <View style={styles.threadLoading}>
              <ActivityIndicator size="large" color={chatColors.teal} />
              <Text style={styles.threadLoadingText}>Loading conversation…</Text>
            </View>
          ) : showEmptyState ? (
            <ChatEmptyState onSuggestion={handleSuggestion} />
          ) : (
            <FlatList
              ref={listRef}
              data={listItems}
              keyExtractor={(item) => item.id}
              renderItem={renderItem}
              ItemSeparatorComponent={() => <View style={styles.separator} />}
              contentContainerStyle={styles.listContent}
              showsVerticalScrollIndicator={false}
              keyboardShouldPersistTaps="handled"
              onContentSizeChange={scrollToEnd}
            />
          )}
        </View>

        <ChatComposer
          inputRef={inputRef}
          value={message}
          onChangeText={setMessage}
          onSend={handleSend}
          disabled={composerDisabled}
        />
      </KeyboardAvoidingView>

      <RecentChatsDrawer
        visible={recentDrawerOpen}
        sessions={savedSessions}
        activeSessionId={sessionId || null}
        loading={sessionsLoading}
        error={sessionsError}
        onClose={() => setRecentDrawerOpen(false)}
        onSelect={handleSelectSession}
        onDelete={handleDeleteSession}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  flex: { flex: 1 },
  body: {
    flex: 1,
    backgroundColor: chatColors.bg,
  },
  authBanner: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    backgroundColor: chatColors.negSoftBg,
  },
  authBannerText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: chatColors.negSoftInk,
    textAlign: "center",
  },
  threadLoading: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
  threadLoadingText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: chatColors.muted,
  },
  listContent: {
    paddingHorizontal: 18,
    paddingTop: 6,
    paddingBottom: 22,
  },
  separator: {
    height: 18,
  },
});
