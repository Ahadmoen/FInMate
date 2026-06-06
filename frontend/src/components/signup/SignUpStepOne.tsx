import { colors, fonts, globalStyles } from "@/styles/global";
import { checkEmailTaken } from "@/services/auth";
import { Link, useRouter } from "expo-router";
import { ArrowRight, Eye, EyeOff, Lock, Mail, Phone, ShieldCheck, User } from "lucide-react-native";
import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import SignUpScreenWrapper from "@/components/signup/SignUpScreenWrapper";
import {
  MIN_PASSWORD_LENGTH,
  formatPhoneInput,
  isValidEmail,
  isValidPhone,
} from "@/utils/signupValidation";

const INITIAL_FORM = {
  firstName: "",
  lastName: "",
  email: "",
  phone: "",
  password: "",
  confirmPassword: "",
};

type FormErrors = Partial<Record<keyof typeof INITIAL_FORM, string>>;

export default function SignUpStepOne() {
  const router = useRouter();
  const [form, setForm] = useState(INITIAL_FORM);
  const [fieldErrors, setFieldErrors] = useState<FormErrors>({});
  const [isChecking, setIsChecking] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const updateField = <K extends keyof typeof INITIAL_FORM>(field: K, value: string) => {
    const next = field === "phone" ? formatPhoneInput(value) : value;
    setForm((prev) => ({ ...prev, [field]: next }));
    setFieldErrors((prev) => ({ ...prev, [field]: "" }));
  };

  const validate = (): FormErrors => {
    const errors: FormErrors = {};

    if (!form.firstName.trim()) errors.firstName = "First name is required.";
    if (!form.lastName.trim()) errors.lastName = "Last name is required.";

    if (!form.email.trim()) errors.email = "Email is required.";
    else if (!isValidEmail(form.email)) errors.email = "Enter a valid email address.";

    if (!form.phone.trim()) errors.phone = "Phone number is required.";
    else if (!isValidPhone(form.phone)) errors.phone = "Format: 0307-1745632";

    if (!form.password.trim()) errors.password = "Password is required.";
    else if (form.password.length < MIN_PASSWORD_LENGTH)
      errors.password = `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;

    if (!form.confirmPassword.trim()) errors.confirmPassword = "Please confirm your password.";
    else if (form.password !== form.confirmPassword)
      errors.confirmPassword = "Passwords do not match.";

    return errors;
  };

  const onNext = async () => {
    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setIsChecking(true);
    try {
      const taken = await checkEmailTaken(form.email.trim());
      if (taken) {
        setFieldErrors((prev) => ({ ...prev, email: "This email is already registered." }));
        return;
      }
    } catch {
      // Network error checking email — let it pass and backend will reject on register
    } finally {
      setIsChecking(false);
    }

    router.push({
      pathname: "/signup-flow",
      params: {
        firstName: form.firstName.trim(),
        lastName: form.lastName.trim(),
        email: form.email.trim(),
        phone: form.phone.trim(),
        password: form.password,
      },
    });
  };

  return (
    <SignUpScreenWrapper onBack={() => router.back()} contentContainerStyle={styles.content}>
      <View>
        <View style={styles.stepBlock}>
          <View style={styles.stepLabels}>
            <Text style={styles.stepCount}>STEP 1 OF 4</Text>
            <Text style={styles.stepName}>Personal Information</Text>
          </View>
          <View style={styles.stepTrack}>
            <View style={[styles.stepSegment, styles.stepSegmentActive]} />
            <View style={styles.stepSegment} />
            <View style={styles.stepSegment} />
            <View style={styles.stepSegment} />
          </View>
        </View>

        <View style={styles.card}>
          <Text style={[globalStyles.heading, styles.cardTitle]}>Join FinMate</Text>
          <Text style={styles.cardSubtitle}>Begin your journey to financial reliability.</Text>

          <View style={styles.nameRow}>
            <View style={[styles.fieldGroup, styles.nameField]}>
              <Text style={styles.label}>First Name</Text>
              <View style={styles.inputWrap}>
                <User color={colors.mutedText} size={18} />
                <TextInput
                  style={styles.input}
                  placeholder="John"
                  placeholderTextColor={colors.mutedText}
                  value={form.firstName}
                  onChangeText={(v) => updateField("firstName", v)}
                />
              </View>
              {fieldErrors.firstName ? (
                <Text style={styles.inlineError}>{fieldErrors.firstName}</Text>
              ) : null}
            </View>

            <View style={[styles.fieldGroup, styles.nameField]}>
              <Text style={styles.label}>Last Name</Text>
              <View style={styles.inputWrap}>
                <User color={colors.mutedText} size={18} />
                <TextInput
                  style={styles.input}
                  placeholder="Doe"
                  placeholderTextColor={colors.mutedText}
                  value={form.lastName}
                  onChangeText={(v) => updateField("lastName", v)}
                />
              </View>
              {fieldErrors.lastName ? (
                <Text style={styles.inlineError}>{fieldErrors.lastName}</Text>
              ) : null}
            </View>
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Email Address</Text>
            <View style={styles.inputWrap}>
              <Mail color={colors.mutedText} size={18} />
              <TextInput
                style={styles.input}
                placeholder="name@example.com"
                placeholderTextColor={colors.mutedText}
                autoCapitalize="none"
                keyboardType="email-address"
                value={form.email}
                onChangeText={(v) => updateField("email", v)}
              />
            </View>
            {fieldErrors.email ? (
              <Text style={styles.inlineError}>{fieldErrors.email}</Text>
            ) : null}
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Phone Number</Text>
            <View style={styles.inputWrap}>
              <Phone color={colors.mutedText} size={18} />
              <TextInput
                style={styles.input}
                placeholder="0307-1745632"
                placeholderTextColor={colors.mutedText}
                keyboardType="phone-pad"
                maxLength={12}
                value={form.phone}
                onChangeText={(v) => updateField("phone", v)}
              />
            </View>
            {fieldErrors.phone ? (
              <Text style={styles.inlineError}>{fieldErrors.phone}</Text>
            ) : null}
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Password</Text>
            <View style={styles.inputWrap}>
              <Lock color={colors.mutedText} size={18} />
              <TextInput
                style={styles.input}
                placeholder="••••••••"
                placeholderTextColor={colors.mutedText}
                secureTextEntry={!showPassword}
                value={form.password}
                onChangeText={(v) => updateField("password", v)}
              />
              <Pressable onPress={() => setShowPassword((p) => !p)} hitSlop={8}>
                {showPassword
                  ? <EyeOff color={colors.mutedText} size={18} />
                  : <Eye color={colors.mutedText} size={18} />}
              </Pressable>
            </View>
            {fieldErrors.password ? (
              <Text style={styles.inlineError}>{fieldErrors.password}</Text>
            ) : null}
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Confirm Password</Text>
            <View style={styles.inputWrap}>
              <ShieldCheck color={colors.mutedText} size={18} />
              <TextInput
                style={styles.input}
                placeholder="••••••••"
                placeholderTextColor={colors.mutedText}
                secureTextEntry={!showConfirmPassword}
                value={form.confirmPassword}
                onChangeText={(v) => updateField("confirmPassword", v)}
              />
              <Pressable onPress={() => setShowConfirmPassword((p) => !p)} hitSlop={8}>
                {showConfirmPassword
                  ? <EyeOff color={colors.mutedText} size={18} />
                  : <Eye color={colors.mutedText} size={18} />}
              </Pressable>
            </View>
            {fieldErrors.confirmPassword ? (
              <Text style={styles.inlineError}>{fieldErrors.confirmPassword}</Text>
            ) : null}
          </View>

          <Pressable
            style={[styles.primaryButton, isChecking && styles.primaryButtonDisabled]}
            onPress={onNext}
            disabled={isChecking}
          >
            {isChecking ? (
              <ActivityIndicator color={colors.background} size="small" />
            ) : (
              <>
                <Text style={styles.primaryButtonText}>Next</Text>
                <ArrowRight color={colors.background} size={18} strokeWidth={2.5} />
              </>
            )}
          </Pressable>

          <View style={styles.loginBlock}>
            <Text style={styles.loginHint}>Already have an account?</Text>
            <Link href="/" style={styles.loginLink}>
              Login
            </Link>
          </View>
        </View>
      </View>
    </SignUpScreenWrapper>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: 18,
  },
  stepBlock: {
    gap: 8,
    marginBottom: 22,
  },
  stepLabels: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  stepCount: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.textMuted,
    letterSpacing: 0.8,
  },
  stepName: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.textNonary,
    letterSpacing: 0.2,
  },
  stepTrack: {
    flexDirection: "row",
    gap: 6,
  },
  stepSegment: {
    flex: 1,
    height: 4,
    borderRadius: 4,
    backgroundColor: colors.borderMuted,
  },
  stepSegmentActive: {
    backgroundColor: colors.stepTrackActive,
  },
  card: {
    backgroundColor: colors.background,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderMuted,
    padding: 22,
  },
  cardTitle: {
    textAlign: "center",
    fontSize: 28,
    letterSpacing: -1.5,
    marginBottom: 6,
  },
  cardSubtitle: {
    ...globalStyles.text,
    textAlign: "center",
    color: colors.textMuted,
    fontSize: 14,
    marginBottom: 18,
  },
  nameRow: {
    flexDirection: "row",
    gap: 10,
  },
  nameField: {
    flex: 1,
  },
  fieldGroup: {
    marginBottom: 14,
  },
  label: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.textQuaternary,
    marginBottom: 6,
    letterSpacing: 0.35,
  },
  inputWrap: {
    height: 46,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderMutedLight,
    backgroundColor: colors.background,
    paddingHorizontal: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  input: {
    flex: 1,
    color: colors.text,
    fontFamily: fonts.body,
    fontSize: 14,
    paddingVertical: 0,
  },
  inlineError: {
    ...globalStyles.text,
    color: colors.error,
    fontSize: 12,
    marginTop: 6,
  },
  primaryButton: {
    marginTop: 6,
    height: 46,
    borderRadius: 10,
    backgroundColor: colors.primaryAccent,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  primaryButtonDisabled: {
    opacity: 0.7,
  },
  primaryButtonText: {
    fontFamily: fonts.bodyMedium,
    color: colors.background,
    fontSize: 14,
  },
  loginBlock: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: 6,
    marginTop: 18,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: colors.headerBorder,
  },
  loginHint: {
    ...globalStyles.text,
    color: colors.textMuted,
    fontSize: 14,
  },
  loginLink: {
    fontFamily: fonts.bodyMedium,
    color: colors.primary,
    fontSize: 14,
  },
  passwordHint: {
    ...globalStyles.text,
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 6,
  },
});
