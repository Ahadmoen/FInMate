import { useAuth } from "@/context/AuthContext";
import { updateUserProfile } from "@/services/auth";
import { colors, fonts, globalStyles } from "@/styles/global";
import {
  formatCnicInput,
  formatPhoneInput,
  formatPostalCodeInput,
  isValidPhone,
  isValidPostalCode,
} from "@/utils/signupValidation";
import DateTimePicker, { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import DropDownPicker from "react-native-dropdown-picker";
import { useRouter } from "expo-router";
import {
  Badge,
  CalendarDays,
  ChevronDown,
  ChevronLeft,
  Mail,
  Phone,
  Save,
  ShieldCheck,
  User,
} from "lucide-react-native";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function intlToLocal(phone: string): string {
  if (phone.startsWith("+92") && phone.length >= 12) {
    const digits = "0" + phone.slice(3);
    if (digits.length === 11) {
      return `${digits.slice(0, 4)}-${digits.slice(4)}`;
    }
  }
  return phone;
}

function localToIntl(phone: string): string {
  const digits = phone.replace(/\D/g, "");
  if (digits.length === 11 && digits.startsWith("0")) {
    return `+92${digits.slice(1)}`;
  }
  return phone;
}

// ─── Types ────────────────────────────────────────────────────────────────────

type EditableForm = {
  firstName: string;
  lastName: string;
  phone: string;
  dateOfBirth: string;
  gender: string;
  city: string;
  province: string;
  postalCode: string;
};

type FieldErrors = Partial<Record<keyof EditableForm, string>>;

// ─── Stable constants (defined outside component to avoid re-render loops) ────

const GENDER_ITEMS = [
  { label: "Male", value: "male" },
  { label: "Female", value: "female" },
  { label: "Other", value: "other" },
];

const ArrowDown = () => <ChevronDown color={colors.mutedText} size={16} />;
const ArrowUp = () => <ChevronDown color={colors.mutedText} size={16} />;

// ─── Screen ───────────────────────────────────────────────────────────────────

export default function PersonalInfoScreen() {
  const router = useRouter();
  const { token, user, refreshUser } = useAuth();

  const [email, setEmail] = useState("");
  const [cnic, setCnic] = useState("");
  const [form, setForm] = useState<EditableForm>({
    firstName: "",
    lastName: "",
    phone: "",
    dateOfBirth: "",
    gender: "",
    city: "",
    province: "",
    postalCode: "",
  });

  const scrollRef = useRef<ScrollView>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [isSaving, setIsSaving] = useState(false);

  const [isGenderOpen, setIsGenderOpen] = useState(false);
  const [genderValue, setGenderValue] = useState<string | null>(null);
  const [showDatePicker, setShowDatePicker] = useState(false);

  // ─── Populate form from centralized user store ────────────────────────────

  useEffect(() => {
    if (!user) return;
    const kyc = user.kyc_profile;
    setEmail(user.email ?? "");
    setCnic(formatCnicInput(kyc?.cnic ?? ""));
    const localPhone = intlToLocal(user.phone_number ?? "");
    const gender = kyc?.gender?.toLowerCase() ?? "";
    setGenderValue(gender || null);
    setForm({
      firstName: user.first_name ?? "",
      lastName: user.last_name ?? "",
      phone: localPhone,
      dateOfBirth: kyc?.date_of_birth ?? "",
      gender,
      city: kyc?.city ?? "",
      province: kyc?.province ?? "",
      postalCode: kyc?.postal_code ?? "",
    });
  }, [user]);

  // ─── Form helpers ────────────────────────────────────────────────────────

  const updateField = <K extends keyof EditableForm>(field: K, value: EditableForm[K]) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setFieldErrors((prev) => ({ ...prev, [field]: "" }));
  };

  const dateLabel = useMemo(() => {
    if (!form.dateOfBirth) return "";
    const parsed = new Date(form.dateOfBirth);
    if (Number.isNaN(parsed.getTime())) return "";
    return parsed.toLocaleDateString();
  }, [form.dateOfBirth]);

  const onDateChange = (event: DateTimePickerEvent, selectedDate?: Date) => {
    if (Platform.OS !== "ios") setShowDatePicker(false);
    if (event.type === "dismissed" || !selectedDate) return;
    const year = selectedDate.getFullYear();
    const month = String(selectedDate.getMonth() + 1).padStart(2, "0");
    const day = String(selectedDate.getDate()).padStart(2, "0");
    updateField("dateOfBirth", `${year}-${month}-${day}`);
  };

  // ─── Inline errors ───────────────────────────────────────────────────────

  const phoneInlineError =
    fieldErrors.phone ||
    (form.phone.length > 0 && !isValidPhone(form.phone) ? "Format: 0307-1745632" : "");

  const postalInlineError =
    fieldErrors.postalCode ||
    (form.postalCode.length > 0 && !isValidPostalCode(form.postalCode)
      ? "Postal code must be 5 digits."
      : "");

  // ─── Validation ──────────────────────────────────────────────────────────

  const validate = (): FieldErrors => {
    const errors: FieldErrors = {};
    if (!form.firstName.trim()) errors.firstName = "First name is required.";
    if (!form.lastName.trim()) errors.lastName = "Last name is required.";
    if (!form.phone.trim()) errors.phone = "Phone number is required.";
    else if (!isValidPhone(form.phone)) errors.phone = "Format: 0307-1745632";
    if (!form.dateOfBirth) errors.dateOfBirth = "Date of birth is required.";
    if (!form.gender) errors.gender = "Please select a gender.";
    if (!form.city.trim()) errors.city = "City is required.";
    if (!form.province.trim()) errors.province = "Province is required.";
    if (!form.postalCode.trim()) errors.postalCode = "Postal code is required.";
    else if (!isValidPostalCode(form.postalCode)) errors.postalCode = "Postal code must be 5 digits.";
    return errors;
  };

  // ─── Save ────────────────────────────────────────────────────────────────

  const onSave = async () => {
    Keyboard.dismiss();

    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    if (!token) return;

    setIsSaving(true);
    try {
      await updateUserProfile(token, {
        first_name: form.firstName.trim(),
        last_name: form.lastName.trim(),
        phone_number: localToIntl(form.phone),
        date_of_birth: form.dateOfBirth,
        gender: form.gender,
        city: form.city.trim(),
        province: form.province.trim(),
        postal_code: form.postalCode.trim(),
      });
      await refreshUser();
      Alert.alert("Success", "Your profile has been updated.", [
        { text: "OK", onPress: () => scrollRef.current?.scrollTo({ y: 0, animated: true }) },
      ]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save. Please try again.";
      Alert.alert("Error", msg);
    } finally {
      setIsSaving(false);
    }
  };

  // ─── Render ──────────────────────────────────────────────────────────────

  if (!user) {
    return (
      <SafeAreaView style={styles.safe} edges={["top"]}>
        <View style={styles.header}>
          <Pressable style={styles.backBtn} onPress={() => router.back()} hitSlop={10}>
            <ChevronLeft size={22} color={colors.primary} strokeWidth={2} />
          </Pressable>
          <Text style={styles.headerTitle}>Personal Info</Text>
          <Text style={styles.headerLogo}>FinMate</Text>
        </View>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable style={styles.backBtn} onPress={() => router.back()} hitSlop={10}>
          <ChevronLeft size={22} color={colors.primary} strokeWidth={2} />
        </Pressable>
        <Text style={styles.headerTitle}>Personal Info</Text>
        <Text style={styles.headerLogo}>FinMate</Text>
      </View>

      <KeyboardAvoidingView
        style={styles.keyboardAvoid}
        behavior="padding"
      >
      <ScrollView
        ref={scrollRef}
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        showsVerticalScrollIndicator={false}
      >
        {/* Main card */}
        <View style={styles.card}>
          {/* Card header */}
          <View style={styles.cardHeader}>
            <Text style={styles.cardTitle}>Identity Details</Text>
            <Text style={styles.cardSubtitle}>
              Update your information to keep your profile current.
            </Text>
          </View>

          {/* Email — read-only */}
          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Email</Text>
            <View style={[styles.inputWrap, styles.inputWrapDisabled]}>
              <Mail size={16} color={colors.mutedText} />
              <Text style={[styles.inputText, styles.disabledText]} numberOfLines={1}>
                {email}
              </Text>
            </View>
          </View>

          {/* CNIC — read-only */}
          <View style={styles.fieldGroup}>
            <Text style={styles.label}>CNIC</Text>
            <View style={[styles.inputWrap, styles.inputWrapDisabled]}>
              <Badge size={16} color={colors.mutedText} />
              <Text style={[styles.inputText, styles.disabledText]} numberOfLines={1}>
                {cnic}
              </Text>
            </View>
          </View>

          {/* First Name */}
          <View style={styles.fieldGroup}>
            <Text style={styles.label}>First Name</Text>
            <View style={styles.inputWrap}>
              <User size={16} color={colors.mutedText} />
              <TextInput
                style={styles.input}
                placeholder="First name"
                placeholderTextColor={colors.mutedText}
                value={form.firstName}
                onChangeText={(v) => updateField("firstName", v)}
              />
            </View>
            {fieldErrors.firstName ? (
              <Text style={styles.inlineError}>{fieldErrors.firstName}</Text>
            ) : null}
          </View>

          {/* Last Name */}
          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Last Name</Text>
            <View style={styles.inputWrap}>
              <User size={16} color={colors.mutedText} />
              <TextInput
                style={styles.input}
                placeholder="Last name"
                placeholderTextColor={colors.mutedText}
                value={form.lastName}
                onChangeText={(v) => updateField("lastName", v)}
              />
            </View>
            {fieldErrors.lastName ? (
              <Text style={styles.inlineError}>{fieldErrors.lastName}</Text>
            ) : null}
          </View>

          {/* Phone Number */}
          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Phone Number</Text>
            <View style={styles.inputWrap}>
              <Phone size={16} color={colors.mutedText} />
              <TextInput
                style={styles.input}
                placeholder="0307-1745632"
                placeholderTextColor={colors.mutedText}
                keyboardType="phone-pad"
                maxLength={12}
                value={form.phone}
                onChangeText={(v) => updateField("phone", formatPhoneInput(v))}
              />
            </View>
            {phoneInlineError ? (
              <Text style={styles.inlineError}>{phoneInlineError}</Text>
            ) : null}
          </View>

          {/* Date of Birth */}
          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Date of Birth</Text>
            <Pressable style={styles.inputWrap} onPress={() => setShowDatePicker(true)}>
              <CalendarDays size={16} color={colors.mutedText} />
              <Text style={[styles.inputText, !dateLabel && styles.placeholderText]}>
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
            {fieldErrors.dateOfBirth ? (
              <Text style={styles.inlineError}>{fieldErrors.dateOfBirth}</Text>
            ) : null}
          </View>

          {/* Gender */}
          <View style={[styles.fieldGroup, isGenderOpen && styles.fieldGroupExpanded]}>
            <Text style={styles.label}>Gender</Text>
            <View style={styles.dropdownWrap}>
              <User size={16} color={colors.mutedText} />
              <View style={styles.dropdownContainer}>
                <DropDownPicker
                  open={isGenderOpen}
                  value={genderValue}
                  items={GENDER_ITEMS}
                  setOpen={setIsGenderOpen}
                  setValue={setGenderValue}
                  onChangeValue={(value) => updateField("gender", value ?? "")}
                  placeholder="Select Gender"
                  style={styles.dropdown}
                  dropDownContainerStyle={styles.dropdownList}
                  textStyle={styles.dropdownText}
                  placeholderStyle={styles.dropdownPlaceholder}
                  listMode="SCROLLVIEW"
                  ArrowDownIconComponent={ArrowDown}
                  ArrowUpIconComponent={ArrowUp}
                  zIndex={3000}
                  zIndexInverse={1000}
                />
              </View>
            </View>
            {fieldErrors.gender ? (
              <Text style={styles.inlineError}>{fieldErrors.gender}</Text>
            ) : null}
          </View>

          {/* City */}
          <View style={styles.fieldGroup}>
            <Text style={styles.label}>City</Text>
            <View style={styles.simpleInputWrap}>
              <TextInput
                style={styles.input}
                placeholder="e.g. Islamabad"
                placeholderTextColor={colors.mutedText}
                value={form.city}
                onChangeText={(v) => updateField("city", v)}
              />
            </View>
            {fieldErrors.city ? (
              <Text style={styles.inlineError}>{fieldErrors.city}</Text>
            ) : null}
          </View>

          {/* Province */}
          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Province</Text>
            <View style={styles.simpleInputWrap}>
              <TextInput
                style={styles.input}
                placeholder="e.g. Punjab"
                placeholderTextColor={colors.mutedText}
                value={form.province}
                onChangeText={(v) => updateField("province", v)}
              />
            </View>
            {fieldErrors.province ? (
              <Text style={styles.inlineError}>{fieldErrors.province}</Text>
            ) : null}
          </View>

          {/* Postal Code */}
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
                onChangeText={(v) => updateField("postalCode", formatPostalCodeInput(v))}
              />
            </View>
            {postalInlineError ? (
              <Text style={styles.inlineError}>{postalInlineError}</Text>
            ) : null}
          </View>

          {/* Save button */}
          <Pressable
            style={[styles.saveButton, isSaving && styles.saveButtonDisabled]}
            onPress={onSave}
            disabled={isSaving}
          >
            {isSaving ? (
              <ActivityIndicator color={colors.background} size="small" />
            ) : (
              <>
                <Save size={16} color={colors.background} strokeWidth={2} />
                <Text style={styles.saveButtonText}>Save</Text>
              </>
            )}
          </Pressable>
        </View>

        {/* Data Security footer */}
        <View style={styles.securityFooter}>
          <ShieldCheck size={20} color={colors.primary} strokeWidth={1.8} />
          <View style={styles.securityTextWrap}>
            <Text style={styles.securityTitle}>Data Security</Text>
            <Text style={styles.securitySub}>Encrypted with AES-256 standards</Text>
          </View>
        </View>
      </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },

  // Header
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: colors.background,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  backBtn: {
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
  headerLogo: {
    fontFamily: fonts.heading,
    fontSize: 13,
    color: colors.primary,
    letterSpacing: -0.2,
  },

  // Keyboard / Scroll
  keyboardAvoid: {
    flex: 1,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    gap: 12,
    paddingBottom: 80,
  },

  // Card
  card: {
    backgroundColor: colors.background,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderLight,
    padding: 16,
  },
  cardHeader: {
    marginBottom: 16,
    paddingBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  cardTitle: {
    fontFamily: fonts.heading,
    fontSize: 15,
    color: colors.text,
    letterSpacing: -0.2,
    marginBottom: 3,
  },
  cardSubtitle: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
    lineHeight: 17,
  },

  // Field
  fieldGroup: {
    marginBottom: 14,
  },
  fieldGroupExpanded: {
    marginBottom: 100,
  },
  label: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.textQuaternary,
    marginBottom: 6,
    letterSpacing: 0.2,
  },

  // Input wraps
  inputWrap: {
    height: 44,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderMutedLight,
    backgroundColor: colors.background,
    paddingHorizontal: 11,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  inputWrapDisabled: {
    backgroundColor: colors.bgLight,
    borderColor: colors.borderLight,
  },
  simpleInputWrap: {
    height: 44,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderMutedLight,
    backgroundColor: colors.background,
    paddingHorizontal: 11,
    justifyContent: "center",
  },
  input: {
    flex: 1,
    fontFamily: fonts.body,
    fontSize: 14,
    color: colors.text,
    paddingVertical: 0,
  },
  inputText: {
    flex: 1,
    fontFamily: fonts.body,
    fontSize: 14,
    color: colors.text,
  },
  disabledText: {
    color: colors.mutedText,
  },
  placeholderText: {
    color: colors.mutedText,
  },

  // Dropdown
  dropdownWrap: {
    height: 44,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderMutedLight,
    backgroundColor: colors.background,
    paddingHorizontal: 11,
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
    minHeight: 40,
    paddingHorizontal: 0,
    backgroundColor: "transparent",
  },
  dropdownList: {
    borderColor: colors.borderMutedLight,
    borderRadius: 10,
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

  // Errors
  inlineError: {
    ...globalStyles.text,
    color: colors.error,
    fontSize: 12,
    marginTop: 5,
  },

  // Save button
  saveButton: {
    marginTop: 6,
    height: 46,
    borderRadius: 10,
    backgroundColor: colors.primary,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  saveButtonDisabled: {
    opacity: 0.7,
  },
  saveButtonText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: colors.background,
  },

  // Security footer
  securityFooter: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: colors.background,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderLight,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  securityTextWrap: {
    gap: 1,
  },
  securityTitle: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.text,
  },
  securitySub: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
  },
});
