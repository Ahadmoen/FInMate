import { chatColors, chatShadow } from "@/components/chat/chatTheme";
import { fonts } from "@/styles/global";
import { StyleSheet, Text, View } from "react-native";

type Props = {
  text: string;
};

export default function UserBubble({ text }: Props) {
  return (
    <View style={styles.row}>
      <View style={styles.bubble}>
        <Text style={styles.text}>{text}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    justifyContent: "flex-end",
  },
  bubble: {
    maxWidth: "78%",
    backgroundColor: chatColors.teal,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 6,
    ...chatShadow.userBubble,
  },
  text: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14.5,
    lineHeight: 21,
    color: chatColors.bubbleUserText,
    letterSpacing: 0.1,
  },
});

export function AivaTextBubble({ text }: Props) {
  return (
    <View style={stylesAiva.bubble}>
      <Text style={stylesAiva.text}>{text}</Text>
    </View>
  );
}

const stylesAiva = StyleSheet.create({
  bubble: {
    backgroundColor: chatColors.card,
    borderTopLeftRadius: 6,
    borderTopRightRadius: 20,
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 20,
    paddingVertical: 14,
    paddingHorizontal: 16,
    ...chatShadow.card,
  },
  text: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14.5,
    lineHeight: 22,
    color: chatColors.aivaText,
  },
});
