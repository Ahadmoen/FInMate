import { colors, fonts, globalStyles } from "@/styles/global";
import { Badge, CalendarDays, ChevronDown, ChevronRight, Lock, ShieldCheck, User } from "lucide-react-native";
import { useMemo, useState } from "react";
import DateTimePicker, { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import DropDownPicker from "react-native-dropdown-picker";
import { Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import SignUpScreenWrapper from "@/components/signup/SignUpScreenWrapper";
import {
  formatCnicInput,
  formatPostalCodeInput,
  isValidCnic,
  isValidPostalCode,
} from "@/utils/signupValidation";

type IdentityForm = {
  cnic: string;
  dateOfBirth: string;
  gender: string;
  city: string;
  province: string;
  postalCode: string;
};

type Props = {
  form: IdentityForm;
  error: string;
  fieldErrors: Partial<Record<keyof IdentityForm, string>>;
  onBack: () => void;
  onNext: () => void;
  updateField: <K extends keyof IdentityForm>(field: K, value: IdentityForm[K]) => void;
};

export default function SignUpStepTwoIdentity({
  form,
  error,
  fieldErrors,
  onBack,
  onNext,
  updateField,
}: Props) {
  const [isGenderOpen, setIsGenderOpen] = useState(false);
  const [genderValue, setGenderValue] = useState<string | null>(form.gender || null);
  const [showDatePicker, setShowDatePicker] = useState(false);

  const dateLabel = useMemo(() => {
    if (!form.dateOfBirth) return "";
    const parsed = new Date(form.dateOfBirth);
    if (Number.isNaN(parsed.getTime())) return "";
    return parsed.toLocaleDateString();
  }, [form.dateOfBirth]);

  const cnicInlineError = fieldErrors.cnic || (form.cnic.length > 0 && !isValidCnic(form.cnic) ? "CNIC format: 35202-5094174-9" : "");
  const postalInlineError =
    fieldErrors.postalCode ||
    (form.postalCode.length > 0 && !isValidPostalCode(form.postalCode) ? "Postal code must be 5 digits." : "");

  const onDateChange = (event: DateTimePickerEvent, selectedDate?: Date) => {
    if (Platform.OS !== "ios") {
      setShowDatePicker(false);
    }

    if (event.type === "dismissed" || !selectedDate) {
      return;
    }

    const year = selectedDate.getFullYear();
    const month = String(selectedDate.getMonth() + 1).padStart(2, "0");
    const day = String(selectedDate.getDate()).padStart(2, "0");
    updateField("dateOfBirth", `${year}-${month}-${day}`);
  };

  return (
    <SignUpScreenWrapper onBack={onBack} contentContainerStyle={styles.content}>
      <View>
        <View style={styles.stepBlock}>
          <View style={styles.stepLabels}>
            <Text style={styles.stepCount}>STEP 2 OF 4</Text>
            <Text style={styles.stepName}>Identity Verification</Text>
          </View>
          <View style={styles.stepTrack}>
            <View style={[styles.stepSegment, styles.stepSegmentActive]} />
            <View style={[styles.stepSegment, styles.stepSegmentActive]} />
            <View style={styles.stepSegment} />
            <View style={styles.stepSegment} />
          </View>
        </View>

        <View style={styles.titleBlock}>
          <Text style={styles.title}>Verify Your Identity</Text>
          <Text style={styles.subtitle}>
            We need a few more details to ensure your account remains secure and compliant with
            financial regulations.
          </Text>
        </View>

        <View style={styles.card}>
          <View style={styles.fieldGroup}>
            <Text style={styles.label}>CNIC / National ID Number</Text>
            <View style={styles.inputWrap}>
              <Badge color={colors.mutedText} size={17} />
              <TextInput
                style={styles.input}
                placeholder="35202-5094174-9"
                placeholderTextColor={colors.mutedText}
                keyboardType="number-pad"
                maxLength={15}
                value={form.cnic}
                onChangeText={(value) => updateField("cnic", formatCnicInput(value))}
              />
            </View>
            {cnicInlineError ? <Text style={styles.inlineError}>{cnicInlineError}</Text> : null}
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Date of Birth</Text>
            <Pressable style={styles.inputWrap} onPress={() => setShowDatePicker(true)}>
              <CalendarDays color={colors.mutedText} size={17} />
              <Text style={[styles.input, !dateLabel && styles.placeholderText]}>
                {dateLabel || "Select date of birth"}
              </Text>
            </Pressable>
            {showDatePicker ? (
              <DateTimePicker
                value={form.dateOfBirth ? new Date(form.dateOfBirth) : new Date(2000, 0, 1)}
                mode="date"
                display="default"
                maximumDate={new Date()}
                onChange={onDateChange}
              />
            ) : null}
            {fieldErrors.dateOfBirth ? <Text style={styles.inlineError}>{fieldErrors.dateOfBirth}</Text> : null}
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Gender</Text>
            <View style={styles.dropdownWrap}>
              <User color={colors.mutedText} size={17} />
              <View style={styles.dropdownContainer}>
                <DropDownPicker
                  open={isGenderOpen}
                  value={genderValue}
                  items={[
                    { label: "Male", value: "male" },
                    { label: "Female", value: "female" },
                    { label: "Other", value: "other" },
                  ]}
                  setOpen={setIsGenderOpen}
                  setValue={setGenderValue}
                  onChangeValue={(value) => updateField("gender", value ?? "")}
                  placeholder="Select Gender"
                  style={styles.dropdown}
                  dropDownContainerStyle={styles.dropdownList}
                  textStyle={styles.dropdownText}
                  placeholderStyle={styles.dropdownPlaceholder}
                  listMode="SCROLLVIEW"
                  ArrowDownIconComponent={() => <ChevronDown color={colors.mutedText} size={16} />}
                  ArrowUpIconComponent={() => <ChevronDown color={colors.mutedText} size={16} />}
                  zIndex={3000}
                  zIndexInverse={1000}
                />
              </View>
            </View>
            {fieldErrors.gender ? <Text style={styles.inlineError}>{fieldErrors.gender}</Text> : null}
          </View>

          <View style={styles.addressHeader}>
            <Text style={styles.addressHeaderText}>Permanent Address</Text>
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.label}>City</Text>
            <View style={styles.simpleInputWrap}>
              <TextInput
                style={styles.input}
                placeholder="e.g. Islamabad"
                placeholderTextColor={colors.mutedText}
                value={form.city}
                onChangeText={(value) => updateField("city", value)}
              />
            </View>
            {fieldErrors.city ? <Text style={styles.inlineError}>{fieldErrors.city}</Text> : null}
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Province</Text>
            <View style={styles.simpleInputWrap}>
              <TextInput
                style={styles.input}
                placeholder="e.g. Punjab"
                placeholderTextColor={colors.mutedText}
                value={form.province}
                onChangeText={(value) => updateField("province", value)}
              />
            </View>
            {fieldErrors.province ? <Text style={styles.inlineError}>{fieldErrors.province}</Text> : null}
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Postal Code</Text>
            <View style={styles.simpleInputWrap}>
              <TextInput
                style={styles.input}
                placeholder="e.g. 44000"
                placeholderTextColor={colors.mutedText}
                keyboardType="number-pad"
                maxLength={5}
                value={form.postalCode}
                onChangeText={(value) => updateField("postalCode", formatPostalCodeInput(value))}
              />
            </View>
            {postalInlineError ? <Text style={styles.inlineError}>{postalInlineError}</Text> : null}
          </View>

          <View style={styles.securityNotice}>
            <ShieldCheck color={colors.primaryAccent} size={16} />
            <Text style={styles.securityNoticeText}>
              Your data is encrypted and stored securely according to FinMate&apos;s privacy policy.
              We do not share your sensitive documents.
            </Text>
          </View>

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Pressable style={styles.primaryButton} onPress={onNext}>
            <Text style={styles.primaryButtonText}>Next</Text>
            <ChevronRight color={colors.background} size={18} />
          </Pressable>

          <Text style={styles.supportText}>
            Facing issues? <Text style={styles.supportLink}>Contact Support</Text>
          </Text>
        </View>

        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>Why verify?</Text>
          <Text style={styles.infoText}>
            Verification unlocks higher transaction limits, full portfolio access, and premium
            investment insights tailored to your region.
          </Text>
          <Lock color="rgba(255,255,255,0.2)" size={72} style={styles.infoLock} />
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
    color: colors.textDecenary,
  },
  stepTrack: {
    flexDirection: "row",
    gap: 6,
  },
  stepSegment: {
    flex: 1,
    height: 5,
    borderRadius: 4,
    backgroundColor: colors.borderMuted,
  },
  stepSegmentActive: {
    backgroundColor: colors.stepTrackActive,
  },
  titleBlock: {
    marginTop: 2,
  },
  title: {
    ...globalStyles.heading,
    fontSize: 28,
    letterSpacing: -1.5,
    marginBottom: 6,
  },
  subtitle: {
    ...globalStyles.text,
    color: colors.textTertiary,
    fontSize: 14,
    lineHeight: 20,
  },
  card: {
    backgroundColor: colors.background,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderMuted,
    padding: 18,
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
  simpleInputWrap: {
    height: 46,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderMutedLight,
    backgroundColor: colors.background,
    paddingHorizontal: 10,
    justifyContent: "center",
  },
  input: {
    flex: 1,
    color: colors.text,
    fontFamily: fonts.body,
    fontSize: 14,
    paddingVertical: 0,
  },
  placeholderText: {
    color: colors.mutedText,
  },
  dropdownWrap: {
    height: 46,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderMutedLight,
    backgroundColor: colors.background,
    paddingHorizontal: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    zIndex: 3000,
  },
  dropdownContainer: {
    flex: 1,
  },
  dropdown: {
    borderWidth: 0,
    minHeight: 42,
    paddingHorizontal: 0,
  },
  dropdownList: {
    borderColor: colors.borderMutedLight,
  },
  dropdownText: {
    fontFamily: fonts.body,
    fontSize: 14,
    color: colors.text,
  },
  dropdownPlaceholder: {
    color: colors.mutedText,
    fontFamily: fonts.body,
  },
  inlineError: {
    ...globalStyles.text,
    color: colors.error,
    fontSize: 12,
    marginTop: 6,
  },
  addressHeader: {
    marginTop: 4,
    marginBottom: 11,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderMuted,
    paddingBottom: 6,
  },
  addressHeaderText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 17,
    color: colors.textSenary,
  },
  securityNotice: {
    marginTop: 2,
    marginBottom: 10,
    borderRadius: 10,
    backgroundColor: colors.bgSecondaryLight,
    padding: 11,
    flexDirection: "row",
    gap: 8,
  },
  securityNoticeText: {
    ...globalStyles.text,
    flex: 1,
    fontSize: 13,
    color: colors.textQuinary,
    lineHeight: 18,
  },
  error: {
    ...globalStyles.text,
    color: colors.error,
    fontSize: 13,
    marginBottom: 10,
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
  primaryButtonText: {
    fontFamily: fonts.bodyMedium,
    color: colors.background,
    fontSize: 14,
  },
  supportText: {
    ...globalStyles.text,
    textAlign: "center",
    color: "#5D6473",
    fontSize: 13,
    marginTop: 12,
  },
  supportLink: {
    color: "#17499D",
    fontFamily: fonts.bodyMedium,
  },
  infoCard: {
    marginTop: 6,
    borderRadius: 12,
    backgroundColor: colors.primaryAccent,
    paddingHorizontal: 16,
    paddingVertical: 14,
    overflow: "hidden",
  },
  infoTitle: {
    fontFamily: fonts.bodyMedium,
    color: "#FFFFFF",
    fontSize: 20,
    marginBottom: 4,
  },
  infoText: {
    ...globalStyles.text,
    color: "#E4EDFF",
    fontSize: 14,
    lineHeight: 20,
    maxWidth: "90%",
  },
  infoLock: {
    position: "absolute",
    right: -8,
    bottom: -8,
  },
});
