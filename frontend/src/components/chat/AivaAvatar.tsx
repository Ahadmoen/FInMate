import { chatColors } from "@/components/chat/chatTheme";
import { Bot } from "lucide-react-native";
import { StyleSheet, View } from "react-native";

type Props = {
  size?: number;
};

export default function AivaAvatar({ size = 34 }: Props) {
  const radius = size <= 34 ? 10 : 12;
  const iconSize = size <= 34 ? 19 : 22;

  return (
    <View
      style={[
        styles.avatar,
        {
          width: size,
          height: size,
          borderRadius: radius,
        },
      ]}
    >
      <Bot size={iconSize} color={chatColors.bg} strokeWidth={1.7} />
    </View>
  );
}

const styles = StyleSheet.create({
  avatar: {
    backgroundColor: chatColors.teal,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: chatColors.teal,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.28,
    shadowRadius: 12,
    elevation: 4,
  },
});
