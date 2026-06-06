import SignUpScreenWrapper from "@/components/signup/SignUpScreenWrapper";
import { colors, fonts, globalStyles } from "@/styles/global";
import { ArrowRight, BookOpen, ChartLine, CircleCheck, Flag, ShieldCheck, Wallet } from "lucide-react-native";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

type Props = {
  form: {
    investmentExperience: "Beginner" | "Intermediate" | "Expert";
    riskTolerance: "Low" | "Medium" | "High";
    investmentGoal: "Short-term" | "Long-term" | "Trading" | "Dividend income";
    monthlyIncome: string;
  };
  error: string;
  fieldErrors: Partial<Record<"monthlyIncome", string>>;
  isSubmitting: boolean;
  onBack: () => void;
  onComplete: () => void;
  updateField: <
    K extends
      | "investmentExperience"
      | "riskTolerance"
      | "investmentGoal"
      | "monthlyIncome",
  >(
    field: K,
    value: Props["form"][K],
  ) => void;
};

const INCOME_RANGES: { label: string; description: string; value: string }[] = [
  { label: "Under 50,000", description: "Entry-level income bracket", value: "under_50k" },
  { label: "50,000 – 100,000", description: "Mid-range salary band", value: "50k_100k" },
  { label: "100,000 – 250,000", description: "Upper-mid income tier", value: "100k_250k" },
  { label: "250,000 – 500,000", description: "High income bracket", value: "250k_500k" },
  { label: "500,000 – 1,000,000", description: "Senior / executive range", value: "500k_1m" },
  { label: "Over 1,000,000", description: "Ultra-high income tier", value: "over_1m" },
];

export default function SignUpStepThreeFinancial({
  form,
  error,
  fieldErrors,
  isSubmitting,
  onBack,
  onComplete,
  updateField,
}: Props) {

  return (
    <SignUpScreenWrapper onBack={onBack} contentContainerStyle={styles.content}>
      <View>
        <View style={styles.stepBlock}>
          <View style={styles.stepTopRow}>
            <View>
              <Text style={styles.stepCount}>STEP 3 OF 4</Text>
              <Text style={styles.stepTitle}>Financial Profile</Text>
            </View>
            <View style={styles.stepBars}>
              <View style={styles.stepBarActive} />
              <View style={styles.stepBarActive} />
              <View style={styles.stepBarActive} />
              <View style={styles.stepBarInactive} />
            </View>
          </View>
          <Text style={styles.stepDescription}>
            Help us tailor your investment experience by detailing your current
            status and future objectives.
          </Text>
        </View>

        <View style={[styles.card, styles.cardPrimaryAccent]}>
          <Text style={styles.cardTitle}>
            <BookOpen color={colors.primaryAccent} size={16} /> Investment
            Experience
          </Text>
          <SelectRow
            label="Beginner"
            description="New to investing, looking to learn the basics."
            selected={form.investmentExperience === "Beginner"}
            onPress={() => updateField("investmentExperience", "Beginner")}
          />
          <SelectRow
            label="Intermediate"
            description="Some experience with stocks or funds."
            selected={form.investmentExperience === "Intermediate"}
            onPress={() => updateField("investmentExperience", "Intermediate")}
          />
          <SelectRow
            label="Expert"
            description="Active trader with deep market knowledge."
            selected={form.investmentExperience === "Expert"}
            onPress={() => updateField("investmentExperience", "Expert")}
          />
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>
            <ChartLine color={colors.primaryAccent} size={16} /> Risk Tolerance
          </Text>
          <View style={styles.riskRow}>
            <RiskCard
              tone="Conservative"
              level="Low"
              text="Capital preservation is priority."
              selected={form.riskTolerance === "Low"}
              onPress={() => updateField("riskTolerance", "Low")}
            />
            <RiskCard
              tone="Balanced"
              level="Medium"
              text="Stable growth with some volatility."
              selected={form.riskTolerance === "Medium"}
              onPress={() => updateField("riskTolerance", "Medium")}
            />
            <RiskCard
              tone="Aggressive"
              level="High"
              text="Focus on maximizing returns."
              selected={form.riskTolerance === "High"}
              onPress={() => updateField("riskTolerance", "High")}
            />
          </View>
          <View style={styles.recommendationBox}>
            <Text style={styles.recommendationText}>
              &quot;Based on your profile, we&apos;ll recommend a diversified
              portfolio with 60% equities and 40% fixed income.&quot;
            </Text>
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>
            <Flag color={colors.primaryAccent} size={16} /> Investment Goals
          </Text>
          <View style={styles.goalGrid}>
            <GoalTile
              label="Short-term"
              desc="Goals under 2 years"
              selected={form.investmentGoal === "Short-term"}
              onPress={() => updateField("investmentGoal", "Short-term")}
            />
            <GoalTile
              label="Long-term"
              desc="Retirement or 10+ years"
              selected={form.investmentGoal === "Long-term"}
              onPress={() => updateField("investmentGoal", "Long-term")}
            />
            <GoalTile
              label="Trading"
              desc="Active daily positions"
              selected={form.investmentGoal === "Trading"}
              onPress={() => updateField("investmentGoal", "Trading")}
            />
            <GoalTile
              label="Dividend income"
              desc="Passive cash flow"
              selected={form.investmentGoal === "Dividend income"}
              onPress={() => updateField("investmentGoal", "Dividend income")}
            />
          </View>

          <Text style={[styles.cardTitle, styles.incomeTitle]}>
            <Wallet color={colors.primaryAccent} size={16} /> Annual Income Range
          </Text>
          {INCOME_RANGES.map((range) => (
            <SelectRow
              key={range.value}
              label={range.label}
              description={range.description}
              selected={form.monthlyIncome === range.value}
              onPress={() => updateField("monthlyIncome", range.value)}
            />
          ))}
          {fieldErrors.monthlyIncome ? (
            <Text style={styles.inlineError}>{fieldErrors.monthlyIncome}</Text>
          ) : null}

          <View style={styles.securityBox}>
            <ShieldCheck color={colors.primaryAccent} size={16} />
            <View style={styles.securityTextWrap}>
              <Text style={styles.securityTitle}>Trust &amp; Security</Text>
              <Text style={styles.securityText}>
                We use this data only to comply with FINRA regulations and
                ensure investment suitability.
              </Text>
            </View>
          </View>
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          style={[styles.completeButton, isSubmitting && styles.disabled]}
          onPress={onComplete}
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <ActivityIndicator color={colors.background} size="small" />
          ) : (
            <>
              <Text style={styles.completeButtonText}>Complete Signup</Text>
              <ArrowRight color={colors.background} size={18} />
            </>
          )}
        </Pressable>
      </View>
    </SignUpScreenWrapper>
  );
}

function SelectRow({
  label,
  description,
  selected,
  onPress,
}: {
  label: string;
  description: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.selectRow, selected && styles.selectRowSelected]}
    >
      <View style={[styles.radioDot, selected && styles.radioDotSelected]} />
      <View style={styles.selectTextWrap}>
        <Text style={styles.selectLabel}>{label}</Text>
        <Text style={styles.selectDescription}>{description}</Text>
      </View>
    </Pressable>
  );
}

function RiskCard({
  tone,
  level,
  text,
  selected,
  onPress,
}: {
  tone: string;
  level: string;
  text: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.riskCard, selected && styles.riskCardSelected]}
    >
      {selected ? (
        <CircleCheck
          color={colors.primaryAccent}
          size={14}
          style={styles.riskCheck}
        />
      ) : null}
      <Text style={styles.riskTone}>{tone}</Text>
      <Text style={styles.riskLevel}>{level}</Text>
      <Text style={styles.riskText}>{text}</Text>
    </Pressable>
  );
}

function GoalTile({
  label,
  desc,
  selected,
  onPress,
}: {
  label: string;
  desc: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.goalTile, selected && styles.goalTileSelected]}
    >
      {selected ? (
        <CircleCheck
          color={colors.primaryAccent}
          size={14}
          style={styles.goalCheck}
        />
      ) : null}
      <Text style={styles.goalLabel}>{label}</Text>
      <Text style={styles.goalDesc}>{desc}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  content: { gap: 14 },
  stepBlock: { marginBottom: 4 },
  stepTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
  },
  stepCount: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    color: colors.textMuted,
    letterSpacing: 0.8,
  },
  stepTitle: {
    ...globalStyles.heading,
    fontSize: 28,
    color: colors.textNonary,
    letterSpacing: -1.5,
    marginTop: 2,
  },
  stepBars: { flexDirection: "row", gap: 4, marginBottom: 4 },
  stepBarActive: {
    width: 26,
    height: 4,
    borderRadius: 4,
    backgroundColor: colors.primaryAccent,
  },
  stepBarInactive: {
    width: 26,
    height: 4,
    borderRadius: 4,
    backgroundColor: colors.stepBarInactive,
  },
  stepDescription: {
    ...globalStyles.text,
    color: colors.textTertiary,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 8,
  },
  card: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.borderMuted,
    borderRadius: 10,
    padding: 14,
    marginBottom: 14,
  },
  cardPrimaryAccent: {
    borderLeftWidth: 4,
    borderLeftColor: colors.primaryAccent,
  },
  cardTitle: {
    fontFamily: fonts.bodyMedium,
    fontSize: 20,
    color: colors.textSepternary,
    marginBottom: 10,
  },
  selectRow: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.borderMuted,
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
  },
  selectRowSelected: {
    borderColor: colors.primaryAccent,
    borderWidth: 2,
    backgroundColor: colors.bgPrimaryLight,
  },
  radioDot: {
    width: 16,
    height: 16,
    borderRadius: 8,
    borderWidth: 1.5,
    borderColor: colors.radioBorder,
    marginRight: 10,
  },
  radioDotSelected: {
    borderColor: colors.primaryAccent,
    backgroundColor: colors.primaryAccent,
  },
  selectTextWrap: { flex: 1 },
  selectLabel: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: colors.textOctonary,
  },
  selectDescription: {
    ...globalStyles.text,
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },
  riskRow: { gap: 8 },
  riskCard: {
    borderWidth: 1,
    borderColor: colors.borderMuted,
    borderRadius: 8,
    padding: 10,
    alignItems: "center",
  },
  riskCardSelected: {
    borderColor: colors.primaryAccent,
    borderWidth: 2,
    backgroundColor: colors.bgPrimaryLight,
  },
  riskCheck: { position: "absolute", right: 8, top: 8 },
  riskTone: {
    fontFamily: fonts.bodyMedium,
    fontSize: 10,
    color: colors.textMuted,
    marginBottom: 6,
  },
  riskLevel: { fontFamily: fonts.bodyMedium, fontSize: 14, marginBottom: 4 },
  riskText: {
    ...globalStyles.text,
    color: colors.textMuted,
    fontSize: 11,
    textAlign: "center",
  },
  recommendationBox: {
    marginTop: 10,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: colors.recommendationBorder,
    borderRadius: 8,
    padding: 10,
    backgroundColor: colors.bgRecommendation,
  },
  recommendationText: {
    ...globalStyles.text,
    color: colors.mutedText,
    fontSize: 11,
    fontStyle: "italic",
    textAlign: "center",
  },
  goalGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  goalTile: {
    width: "48.5%",
    borderWidth: 1,
    borderColor: colors.borderMuted,
    borderRadius: 8,
    padding: 10,
    position: "relative",
  },
  goalTileSelected: {
    borderWidth: 2,
    borderColor: colors.primaryAccent,
    backgroundColor: colors.bgPrimaryLight,
  },
  goalCheck: { position: "absolute", right: 8, top: 8 },
  goalLabel: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.textOctonary,
    marginBottom: 2,
    marginTop: 4,
  },
  goalDesc: { ...globalStyles.text, color: colors.mutedText, fontSize: 11 },
  incomeTitle: { marginTop: 14, marginBottom: 10 },
  securityBox: {
    flexDirection: "row",
    gap: 8,
    borderWidth: 1,
    borderColor: colors.borderMuted,
    borderRadius: 8,
    padding: 10,
    backgroundColor: colors.bgLightest,
  },
  securityTextWrap: { flex: 1 },
  securityTitle: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.textSepternary,
    marginBottom: 2,
  },
  securityText: {
    ...globalStyles.text,
    color: colors.mutedText,
    fontSize: 11,
    lineHeight: 16,
  },
  error: {
    ...globalStyles.text,
    color: colors.error,
    fontSize: 13,
    marginTop: -4,
  },
  inlineError: {
    ...globalStyles.text,
    color: colors.error,
    fontSize: 12,
    marginBottom: 10,
  },
  completeButton: {
    marginTop: 4,
    height: 46,
    borderRadius: 10,
    backgroundColor: colors.primaryAccent,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
  },
  completeButtonText: {
    fontFamily: fonts.bodyMedium,
    color: colors.background,
    fontSize: 14,
  },
  disabled: { opacity: 0.6 },
});
