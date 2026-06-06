import { useAuth } from "@/context/AuthContext";
import { updateInvestmentProfile } from "@/services/auth";
import { colors, fonts } from "@/styles/global";
import DropDownPicker from "react-native-dropdown-picker";
import { useRouter } from "expo-router";
import {
  AlertCircle,
  BookOpen,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  Flag,
  RefreshCw,
  Rocket,
  Scale,
  Shield,
  TrendingUp,
  User,
  Users,
  Wallet,
} from "lucide-react-native";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

// ─── Stable constants (outside component to avoid re-render loops) ────────────

const INCOME_ITEMS = [
  { label: "Under Rs. 50,000 / month", value: "under_50k" },
  { label: "Rs. 50,000 – 100,000 / month", value: "50k_100k" },
  { label: "Rs. 100,000 – 250,000 / month", value: "100k_250k" },
  { label: "Rs. 250,000 – 500,000 / month", value: "250k_500k" },
  { label: "Rs. 500,000 – 1,000,000 / month", value: "500k_1m" },
  { label: "Over Rs. 1,000,000 / month", value: "over_1m" },
];

const IncomeArrowDown = () => <ChevronDown color={colors.mutedText} size={16} />;
const IncomeArrowUp = () => <ChevronDown color={colors.mutedText} size={16} />;

const EXPERIENCE_OPTIONS = [
  { value: "beginner", label: "Beginner", desc: "New to investing, focused on learning" },
  { value: "intermediate", label: "Intermediate", desc: "Comfortable with market dynamics" },
  { value: "expert", label: "Expert", desc: "Advanced knowledge and active trading" },
] as const;

const RISK_OPTIONS = [
  { value: "low", label: "Conservative", level: "Low Risk", Icon: Shield },
  { value: "medium", label: "Balanced", level: "Medium Risk", Icon: Scale },
  { value: "high", label: "Aggressive", level: "High Risk", Icon: Rocket },
] as const;

const GOAL_OPTIONS = [
  { value: "short_term", label: "Short-term" },
  { value: "long_term", label: "Long-term" },
  { value: "trading", label: "Trading" },
  { value: "dividend_income", label: "Dividend Income" },
] as const;

// ─── Screen ───────────────────────────────────────────────────────────────────

export default function FinancialProfileScreen() {
  const router = useRouter();
  const { token, user, refreshUser } = useAuth();

  const [experience, setExperience] = useState("intermediate");
  const [risk, setRisk] = useState("medium");
  const [goals, setGoals] = useState<string[]>([]);
  const [incomeRange, setIncomeRange] = useState<string | null>(null);
  const [incomeOpen, setIncomeOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // ─── Populate form from centralized user store ────────────────────────────

  useEffect(() => {
    if (!user?.investment_profile) return;
    const inv = user.investment_profile;
    setExperience(inv.investment_experience ?? "intermediate");
    setRisk(inv.risk_tolerance ?? "medium");
    setGoals(Array.isArray(inv.investment_goals) ? inv.investment_goals : []);
    setIncomeRange(inv.income_range ?? null);
  }, [user]);

  const toggleGoal = (value: string) => {
    setGoals((prev) =>
      prev.includes(value) ? prev.filter((g) => g !== value) : [...prev, value]
    );
  };

  const onSave = async () => {
    if (!token) return;
    if (!incomeRange) {
      Alert.alert("Validation", "Please select an income range.");
      return;
    }
    if (goals.length === 0) {
      Alert.alert("Validation", "Please select at least one investment goal.");
      return;
    }
    setIsSaving(true);
    try {
      await updateInvestmentProfile(token, {
        investment_experience: experience,
        risk_tolerance: risk,
        investment_goals: goals,
        income_range: incomeRange,
      });
      await refreshUser();
      Alert.alert("Success", "Your financial profile has been updated.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save. Please try again.";
      Alert.alert("Error", msg);
    } finally {
      setIsSaving(false);
    }
  };

  const header = (
    <View style={styles.header}>
      <Pressable style={styles.headerBtn} onPress={() => router.back()} hitSlop={10}>
        <ChevronLeft size={22} color={colors.primary} strokeWidth={2} />
      </Pressable>
      <Text style={styles.headerTitle}>Financial Profile</Text>
      <View style={styles.headerAvatar}>
        <User size={15} color={colors.primary} strokeWidth={1.5} />
      </View>
    </View>
  );

  if (!user) {
    return (
      <SafeAreaView style={styles.safe} edges={["top"]}>
        {header}
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      {header}

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {/* ── Top navigation / promo card ── */}
        <View style={styles.navCard}>
          <Pressable
            style={styles.navRow}
            onPress={() => router.push("/alert-settings" as never)}
          >
            <Text style={styles.navRowLabel}>Alert Settings</Text>
            <ChevronRight size={15} color={colors.mutedText} />
          </Pressable>
          <View style={styles.promoCard}>
            <Text style={styles.promoTitle}>Optimize Your Strategy</Text>
            <Text style={styles.promoSub}>
              Refine your preferences for accurate insights.
            </Text>
          </View>
          <View style={styles.navRow}>
            <Text style={[styles.navRowLabel, styles.navRowLabelActive]}>
              Financial Profile
            </Text>
            <ChevronRight size={15} color={colors.primary} />
          </View>
        </View>

        {/* ── Investment Experience ── */}
        <View style={styles.sectionBlock}>
          <View style={styles.sectionHeader}>
            <BookOpen size={15} color={colors.primary} strokeWidth={1.8} />
            <Text style={styles.sectionTitle}>Investment Experience</Text>
          </View>
          {EXPERIENCE_OPTIONS.map((opt) => {
            const selected = experience === opt.value;
            return (
              <Pressable
                key={opt.value}
                style={[styles.radioCard, selected && styles.radioCardSelected]}
                onPress={() => setExperience(opt.value)}
              >
                <View style={styles.radioTextWrap}>
                  <Text style={[styles.radioLabel, selected && styles.radioLabelSelected]}>
                    {opt.label}
                  </Text>
                  <Text style={styles.radioDesc}>{opt.desc}</Text>
                </View>
                <View style={[styles.radioCircle, selected && styles.radioCircleSelected]}>
                  {selected && <View style={styles.radioInner} />}
                </View>
              </Pressable>
            );
          })}
        </View>

        {/* ── Risk Tolerance ── */}
        <View style={styles.sectionBlock}>
          <View style={styles.sectionHeader}>
            <TrendingUp size={15} color={colors.primary} strokeWidth={1.8} />
            <Text style={styles.sectionTitle}>Risk Tolerance</Text>
          </View>
          {RISK_OPTIONS.map((opt) => {
            const selected = risk === opt.value;
            const IconComp = opt.Icon;
            return (
              <Pressable
                key={opt.value}
                style={[styles.riskCard, selected && styles.riskCardSelected]}
                onPress={() => setRisk(opt.value)}
              >
                {selected && (
                  <View style={styles.riskCheckWrap}>
                    <CircleCheck size={16} color={colors.primary} strokeWidth={2} />
                  </View>
                )}
                <View style={[styles.riskIconBox, selected && styles.riskIconBoxSelected]}>
                  <IconComp
                    size={22}
                    color={selected ? colors.primary : colors.mutedText}
                    strokeWidth={1.5}
                  />
                </View>
                <Text style={[styles.riskLabel, selected && styles.riskLabelSelected]}>
                  {opt.label}
                </Text>
                <Text style={styles.riskLevel}>{opt.level}</Text>
              </Pressable>
            );
          })}
        </View>

        {/* ── Investment Goals ── */}
        <View style={styles.sectionBlock}>
          <View style={styles.sectionHeader}>
            <Flag size={15} color={colors.primary} strokeWidth={1.8} />
            <Text style={styles.sectionTitle}>Investment Goals</Text>
          </View>
          {GOAL_OPTIONS.map((opt) => {
            const checked = goals.includes(opt.value);
            return (
              <Pressable
                key={opt.value}
                style={styles.checkRow}
                onPress={() => toggleGoal(opt.value)}
              >
                <View style={[styles.checkbox, checked && styles.checkboxChecked]}>
                  {checked && <Text style={styles.checkTick}>✓</Text>}
                </View>
                <Text style={[styles.checkLabel, checked && styles.checkLabelChecked]}>
                  {opt.label}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {/* ── Income Range ── */}
        <View style={[styles.sectionBlock, incomeOpen && styles.sectionBlockExpanded]}>
          <View style={styles.sectionHeader}>
            <Wallet size={15} color={colors.primary} strokeWidth={1.8} />
            <Text style={styles.sectionTitle}>Income Range</Text>
          </View>
          <DropDownPicker
            open={incomeOpen}
            value={incomeRange}
            items={INCOME_ITEMS}
            setOpen={setIncomeOpen}
            setValue={setIncomeRange}
            placeholder="Select income range"
            style={styles.dropdown}
            dropDownContainerStyle={styles.dropdownList}
            textStyle={styles.dropdownText}
            placeholderStyle={styles.dropdownPlaceholder}
            listMode="SCROLLVIEW"
            ArrowDownIconComponent={IncomeArrowDown}
            ArrowUpIconComponent={IncomeArrowUp}
            zIndex={3000}
            zIndexInverse={1000}
          />
        </View>

        {/* ── Info note ── */}
        <View style={styles.infoRow}>
          <AlertCircle size={13} color="#F59E0B" strokeWidth={1.8} />
          <Text style={styles.infoText}>
            These settings help AI/ML personalize your recommendations.
          </Text>
        </View>

        {/* ── Update Profile button ── */}
        <Pressable
          style={[styles.updateBtn, isSaving && styles.updateBtnDisabled]}
          onPress={onSave}
          disabled={isSaving}
        >
          {isSaving ? (
            <ActivityIndicator color={colors.background} size="small" />
          ) : (
            <>
              <Text style={styles.updateBtnText}>Update Profile</Text>
              <RefreshCw size={15} color={colors.background} strokeWidth={2.5} />
            </>
          )}
        </Pressable>

        {/* ── Consultation card ── */}
        <Pressable style={styles.consultCard}>
          <View style={styles.consultIconWrap}>
            <Users size={17} color={colors.primary} strokeWidth={1.5} />
          </View>
          <View style={styles.consultText}>
            <Text style={styles.consultTitle}>Need a deep dive?</Text>
            <Text style={styles.consultSub}>
              Book a 1:1 consultation with our wealth advisors.
            </Text>
          </View>
          <ChevronRight size={17} color={colors.mutedText} />
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },

  // Header
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
    backgroundColor: colors.background,
  },
  headerBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontFamily: fonts.heading,
    fontSize: 16,
    color: colors.text,
    letterSpacing: -0.3,
  },
  headerAvatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    borderWidth: 1.5,
    borderColor: colors.borderMutedLight,
    backgroundColor: colors.bgLight,
    alignItems: "center",
    justifyContent: "center",
  },

  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },

  // Scroll
  scroll: { flex: 1 },
  scrollContent: {
    padding: 16,
    gap: 18,
    paddingBottom: 36,
  },

  // Top nav / promo card
  navCard: {
    backgroundColor: colors.background,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderLight,
    overflow: "hidden",
  },
  navRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  navRowLabel: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.mutedText,
  },
  navRowLabelActive: {
    color: colors.primary,
    fontFamily: fonts.bodyMedium,
  },
  promoCard: {
    backgroundColor: colors.primary,
    marginHorizontal: 12,
    marginBottom: 4,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 14,
  },
  promoTitle: {
    fontFamily: fonts.heading,
    fontSize: 15,
    color: "#FFFFFF",
    letterSpacing: -0.3,
    marginBottom: 5,
  },
  promoSub: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: "rgba(255,255,255,0.72)",
    lineHeight: 17,
  },

  // Section blocks
  sectionBlock: {
    gap: 8,
  },
  sectionBlockExpanded: {
    marginBottom: 130,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    marginBottom: 2,
  },
  sectionTitle: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: colors.text,
    letterSpacing: -0.2,
  },

  // Radio cards — Investment Experience
  radioCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.background,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderMutedLight,
    paddingHorizontal: 14,
    paddingVertical: 13,
  },
  radioCardSelected: {
    borderColor: colors.primary,
    borderWidth: 2,
    backgroundColor: colors.bgPrimaryLight,
  },
  radioTextWrap: { flex: 1 },
  radioLabel: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.textOctonary,
  },
  radioLabelSelected: {
    color: colors.primary,
  },
  radioDesc: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: colors.mutedText,
    marginTop: 2,
    lineHeight: 15,
  },
  radioCircle: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 1.5,
    borderColor: colors.radioBorder,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: 10,
  },
  radioCircleSelected: {
    borderColor: colors.primary,
    borderWidth: 2,
  },
  radioInner: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.primary,
  },

  // Risk Tolerance cards
  riskCard: {
    backgroundColor: colors.background,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderMutedLight,
    paddingVertical: 18,
    paddingHorizontal: 14,
    alignItems: "center",
    position: "relative",
  },
  riskCardSelected: {
    borderColor: colors.primary,
    borderWidth: 2,
    backgroundColor: colors.bgPrimaryLight,
  },
  riskCheckWrap: {
    position: "absolute",
    top: 10,
    right: 10,
  },
  riskIconBox: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: colors.bgLight,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 9,
  },
  riskIconBoxSelected: {
    backgroundColor: colors.bgSecondaryLight,
  },
  riskLabel: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.textOctonary,
    marginBottom: 3,
  },
  riskLabelSelected: {
    color: colors.primary,
  },
  riskLevel: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: colors.mutedText,
  },

  // Checkbox rows — Investment Goals
  checkRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.background,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderMutedLight,
    paddingHorizontal: 14,
    paddingVertical: 13,
    gap: 12,
  },
  checkbox: {
    width: 18,
    height: 18,
    borderRadius: 4,
    borderWidth: 1.5,
    borderColor: colors.radioBorder,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
  checkboxChecked: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  checkTick: {
    color: "#FFFFFF",
    fontSize: 11,
    fontFamily: fonts.bodyMedium,
    lineHeight: 13,
  },
  checkLabel: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.textSenary,
  },
  checkLabelChecked: {
    fontFamily: fonts.bodyMedium,
    color: colors.text,
  },

  // Income dropdown
  dropdown: {
    borderRadius: 10,
    borderColor: colors.borderMutedLight,
    borderWidth: 1,
    minHeight: 46,
    backgroundColor: colors.background,
    paddingHorizontal: 12,
  },
  dropdownList: {
    borderColor: colors.borderMutedLight,
    borderRadius: 10,
  },
  dropdownText: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.text,
  },
  dropdownPlaceholder: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.mutedText,
  },

  // Info note
  infoRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 7,
  },
  infoText: {
    flex: 1,
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
    lineHeight: 17,
  },

  // Update Profile button
  updateBtn: {
    height: 48,
    borderRadius: 12,
    backgroundColor: colors.primary,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  updateBtnDisabled: { opacity: 0.7 },
  updateBtnText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: colors.background,
    letterSpacing: 0.1,
  },

  // Consultation card
  consultCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.background,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderLight,
    paddingHorizontal: 14,
    paddingVertical: 13,
    gap: 12,
  },
  consultIconWrap: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: colors.bgPrimaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  consultText: { flex: 1, gap: 2 },
  consultTitle: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.text,
  },
  consultSub: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: colors.mutedText,
    lineHeight: 15,
  },
});
