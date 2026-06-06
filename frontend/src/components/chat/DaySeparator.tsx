import { chatColors } from "@/components/chat/chatTheme";
import { fonts } from "@/styles/global";
import { StyleSheet, Text, View } from "react-native";

type Props = {
  label?: string;
};

export default function DaySeparator({ label = "Today" }: Props) {
  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignSelf: "center",
    backgroundColor: "rgba(255,255,255,0.5)",
    paddingVertical: 4,
    paddingHorizontal: 12,
    borderRadius: 999,
    marginVertical: 2,
  },
  label: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    color: chatColors.muted2,
    letterSpacing: 0.2,
  },
});
