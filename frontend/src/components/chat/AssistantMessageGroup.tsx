import AivaAvatar from "@/components/chat/AivaAvatar";
import InsightCard from "@/components/chat/InsightCard";
import RevealIn from "@/components/chat/RevealIn";
import SourceChips from "@/components/chat/SourceChips";
import { AivaTextBubble } from "@/components/chat/UserBubble";
import type { AssistantMessage } from "@/components/chat/types";
import { StyleSheet, View } from "react-native";

const STAGGER_MS = 240;

type Props = {
  message: AssistantMessage;
};

export default function AssistantMessageGroup({ message }: Props) {
  let step = 0;
  const nextDelay = () => step++ * STAGGER_MS;

  return (
    <View style={styles.group}>
      <AivaAvatar />
      <View style={styles.stack}>
        <RevealIn delay={nextDelay()}>
          <AivaTextBubble text={message.text} />
        </RevealIn>

        {message.insight ? (
          <RevealIn delay={nextDelay()}>
            <InsightCard insight={message.insight} />
          </RevealIn>
        ) : null}

        {message.citations?.length ? (
          <RevealIn delay={nextDelay()}>
            <SourceChips citations={message.citations} />
          </RevealIn>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  group: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
  },
  stack: {
    flex: 1,
    minWidth: 0,
    gap: 10,
  },
});
