import { chatColors, chatShadow } from "@/components/chat/chatTheme";
import { fonts } from "@/styles/global";
import { Send } from "lucide-react-native";
import { RefObject } from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";

type Props = {
  value: string;
  onChangeText: (text: string) => void;
  onSend: () => void;
  disabled?: boolean;
  inputRef?: RefObject<TextInput | null>;
};

export default function ChatComposer({
  value,
  onChangeText,
  onSend,
  disabled = false,
  inputRef,
}: Props) {
  const canSend = value.trim().length > 0 && !disabled;

  return (
    <View style={styles.bar}>
      <TextInput
        ref={inputRef}
        style={styles.textInput}
        placeholder="Ask AIVA about a stock or the market…"
        placeholderTextColor={chatColors.muted}
        value={value}
        onChangeText={onChangeText}
        onSubmitEditing={canSend ? onSend : undefined}
        returnKeyType="send"
        editable={!disabled}
        multiline={false}
      />

      <Pressable
        style={[styles.sendBtn, !canSend && styles.sendBtnDim]}
        onPress={onSend}
        disabled={!canSend}
        accessibilityRole="button"
        accessibilityLabel="Send message"
      >
        <Send size={16} color="#FFFFFF" strokeWidth={2} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: chatColors.card,
    borderTopWidth: 1,
    borderTopColor: chatColors.composerBorder,
  },
  textInput: {
    flex: 1,
    height: 40,
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: chatColors.ink,
    paddingVertical: 0,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: chatColors.teal,
    alignItems: "center",
    justifyContent: "center",
    ...chatShadow.sendBtn,
  },
  sendBtnDim: {
    opacity: 0.45,
  },
});
