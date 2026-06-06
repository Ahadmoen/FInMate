import { chatColors } from "@/components/chat/chatTheme";
import { colors, fonts } from "@/styles/global";
import {
  Activity,
  Bot,
  FileText,
  LucideIcon,
  Shield,
} from "lucide-react-native";
import { Pressable, StyleSheet, Text, View } from "react-native";

const SUGGESTION_ROW1 = [
  { id: "predict", Icon: Activity, label: "Predict price" },
  { id: "news", Icon: FileText, label: "Explain news" },
] as const;

const SUGGESTION_ROW2 = [
  { id: "risk", Icon: Shield, label: "Portfolio risk" },
] as const;

type Props = {
  onSuggestion: (label: string) => void;
};

function SuggestionChip({
  Icon,
  label,
  onPress,
}: {
  Icon: LucideIcon;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable style={styles.chip} onPress={onPress}>
      <Icon size={14} color={colors.text} strokeWidth={1.9} />
      <Text style={styles.chipText}>{label}</Text>
    </Pressable>
  );
}

export default function ChatEmptyState({ onSuggestion }: Props) {
  return (
    <View style={styles.content}>
      <View style={styles.introSection}>
        <View style={styles.avatarBox}>
          <Bot size={42} color="#FFFFFF" strokeWidth={1.4} />
        </View>
        <Text style={styles.meetText}>Meet AIVA</Text>
        <Text style={styles.greetText}>
          Hello! I'm AIVA, your financial assistant.{"\n"}How can I help you
          today?
        </Text>
      </View>

      <View style={styles.chipsSection}>
        <View style={styles.chipsRow}>
          {SUGGESTION_ROW1.map(({ id, Icon, label }) => (
            <SuggestionChip
              key={id}
              Icon={Icon}
              label={label}
              onPress={() => onSuggestion(label)}
            />
          ))}
        </View>
        <View style={styles.chipsCenterRow}>
          {SUGGESTION_ROW2.map(({ id, Icon, label }) => (
            <SuggestionChip
              key={id}
              Icon={Icon}
              label={label}
              onPress={() => onSuggestion(label)}
            />
          ))}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  content: {
    flex: 1,
    alignItems: "center",
    justifyContent: "space-between",
    paddingTop: 68,
    paddingBottom: 28,
    paddingHorizontal: 24,
  },
  introSection: {
    alignItems: "center",
    gap: 10,
  },
  avatarBox: {
    width: 82,
    height: 82,
    borderRadius: 22,
    backgroundColor: chatColors.teal,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 8,
    shadowColor: chatColors.teal,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 8,
  },
  meetText: {
    fontFamily: fonts.heading,
    fontSize: 20,
    color: colors.text,
    letterSpacing: -0.3,
  },
  greetText: {
    fontFamily: fonts.body,
    fontSize: 14,
    color: colors.mutedText,
    textAlign: "center",
    lineHeight: 22,
  },
  chipsSection: {
    width: "100%",
    gap: 12,
    alignItems: "center",
  },
  chipsRow: {
    flexDirection: "row",
    gap: 12,
  },
  chipsCenterRow: {
    flexDirection: "row",
    justifyContent: "center",
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: "#D6DCE5",
    borderRadius: 26,
    paddingVertical: 10,
    paddingHorizontal: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 1,
  },
  chipText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.text,
  },
});
