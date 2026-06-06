import { colors, fonts, globalStyles } from "@/styles/global";
import { useRouter } from "expo-router";
import { ArrowRight as ArrowForward, BadgeCheck, ChartColumn, ChartLine, Shield } from "lucide-react-native";
import type { ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import SignUpScreenWrapper from "./SignUpScreenWrapper";

type Props = {
  onBack: () => void;
};

export default function SignUpStepFourVerified({ onBack }: Props) {
  const router = useRouter();

  return (
    <SignUpScreenWrapper onBack={onBack} contentContainerStyle={styles.content}>
      <ScrollView>
        <View style={styles.stepBlock}>
          <View style={styles.stepLabels}>
            <Text style={styles.stepCount}>STEP 4 OF 4</Text>
            <Text style={styles.stepName}>100%</Text>
          </View>
          <View style={styles.stepTrack}>
            <View style={[styles.stepFill, { width: "100%" }]} />
          </View>
        </View>

        <View style={styles.heroSection}>
          <View style={styles.heroCircle}>
            <View style={styles.heroBadge}>
              <BadgeCheck
                color={colors.primaryAccent}
                size={38}
                strokeWidth={2.25}
              />
            </View>
          </View>
          <Text style={styles.heroTitle}>Account Verified!</Text>
          <Text style={styles.heroSubtitle}>
            You&apos;re ready to start building your wealth with FinMate. Your
            professional-grade investment tools are now active.
          </Text>
        </View>

        <View style={styles.cardsBlock}>
          <FeatureCard
            title="Live Portfolio"
            description="Track your assets in real-time with Institutional-grade precision."
            icon={<ChartLine color={colors.primaryAccent} size={18} />}
          />
          <FeatureCard
            title="Market Insights"
            description="Daily curated signals to help you make informed investment decisions."
            icon={<ChartColumn color={colors.textSenary} size={18} />}
          />
          <FeatureCard
            title="Bank-Grade Security"
            description="Your assets are protected with multi-layered encryption protocols."
            icon={<Shield color={colors.primaryAccent} size={18} />}
          />
        </View>

        <Pressable
          style={styles.primaryButton}
          onPress={() => router.replace("/dashboard")}
        >
          <Text style={styles.primaryButtonText}>Go to Dashboard</Text>
          <ArrowForward color={colors.background} size={19} />
        </Pressable>

        <Text style={styles.legalText}>
          FinMate is a registered investment advisor. Market investments involve
          risk of loss. Terms and conditions apply.
        </Text>
      </ScrollView>
    </SignUpScreenWrapper>
  );
}

function FeatureCard({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon: ReactNode;
}) {
  return (
    <View style={styles.featureCard}>
      <View style={styles.featureIconWrap}>{icon}</View>
      <Text style={styles.featureTitle}>{title}</Text>
      <Text style={styles.featureDescription}>{description}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: 18,
  },
  stepBlock: {
    marginBottom: 22,
  },
  stepLabels: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  stepCount: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.textNonary,
    letterSpacing: 0.8,
  },
  stepName: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.textDecenary,
  },
  stepTrack: {
    height: 5,
    borderRadius: 10,
    backgroundColor: colors.borderMutedDark,
    overflow: "hidden",
  },
  stepFill: {
    height: "100%",
    backgroundColor: colors.stepTrackFill,
  },
  heroSection: {
    alignItems: "center",
    marginBottom: 24,
  },
  heroCircle: {
    width: 136,
    height: 136,
    borderRadius: 68,
    backgroundColor: colors.bgTertiaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  heroBadge: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "rgba(255,255,255,0.95)",
    alignItems: "center",
    justifyContent: "center",
  },
  heroTitle: {
    ...globalStyles.heading,
    fontSize: 52,
    letterSpacing: -0.8,
    textAlign: "center",
    marginBottom: 6,
  },
  heroSubtitle: {
    ...globalStyles.text,
    fontSize: 16,
    lineHeight: 23,
    color: colors.textTertiary,
    textAlign: "center",
    paddingHorizontal: 8,
  },
  cardsBlock: {
    gap: 12,
    marginBottom: 22,
  },
  featureCard: {
    borderWidth: 1,
    borderColor: colors.borderMuted,
    borderRadius: 12,
    padding: 14,
    backgroundColor: colors.background,
  },
  featureIconWrap: {
    width: 30,
    height: 30,
    borderRadius: 8,
    backgroundColor: colors.bgIconLight,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 8,
  },
  featureTitle: {
    fontFamily: fonts.heading,
    fontSize: 36,
    marginBottom: 4,
    color: colors.textSenary,
    letterSpacing: -0.3,
  },
  featureDescription: {
    ...globalStyles.text,
    color: colors.textTertiary,
    fontSize: 14,
    lineHeight: 20,
  },
  primaryButton: {
    height: 50,
    borderRadius: 10,
    backgroundColor: colors.primaryAccent,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginBottom: 18,
  },
  primaryButtonText: {
    fontFamily: fonts.heading,
    color: colors.background,
    fontSize: 30,
    letterSpacing: -0.2,
  },
  legalText: {
    ...globalStyles.text,
    textAlign: "center",
    color: colors.textTertiary,
    fontSize: 12,
    lineHeight: 18,
    paddingHorizontal: 14,
  },
});
