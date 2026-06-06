import { ReactNode } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleProp,
  StyleSheet,
  Text,
  View,
  ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { colors, fonts } from "@/styles/global";
import { ArrowLeft } from "lucide-react-native";

type Props = {
  onBack: () => void;
  children: ReactNode;
  contentContainerStyle?: StyleProp<ViewStyle>;
};

export default function SignUpScreenWrapper({
  onBack,
  children,
  contentContainerStyle,
}: Props) {
  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <Pressable onPress={onBack} style={styles.iconButton}>
          <ArrowLeft color={colors.primaryAccent} size={20} strokeWidth={2.5} />
        </Pressable>
        <Text style={styles.headerTitle}>Account Setup</Text>
        <View style={styles.headerRightPlaceholder} />
      </View>

      <KeyboardAvoidingView
        style={styles.keyboardContainer}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <ScrollView
          contentContainerStyle={[styles.content, contentContainerStyle]}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {children}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.bgLight,
  },
  keyboardContainer: {
    flex: 1,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 22,
  },
  iconButton: {
    width: 34,
    height: 34,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 17,
  },
  headerTitle: {
    fontFamily: fonts.heading,
    fontSize: 18,
    color: colors.primaryAccent,
  },
  headerRightPlaceholder: {
    width: 34,
    height: 34,
  },
  content: {
    paddingHorizontal: 22,
    paddingTop: 22,
    paddingBottom: 22,
  },
});
