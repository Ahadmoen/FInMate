import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator } from "react-native";
import { useAuth } from "@/context/AuthContext";
import { SignUpInput, signUpUser } from "@/services/auth";
import SignUpStepTwoIdentity from "@/components/signup/SignUpStepTwoIdentity";
import SignUpStepThreeFinancial from "@/components/signup/SignUpStepThreeFinancial";
import { isValidCnic, isValidPostalCode } from "@/utils/signupValidation";

type StepKey = "kyc" | "risk";

const STEPS: StepKey[] = ["kyc", "risk"];

export default function SignUpFlowScreen() {
  const router = useRouter();
  const { login } = useAuth();
  const params = useLocalSearchParams<{ firstName?: string; lastName?: string; email?: string; phone?: string; password?: string }>();

  const [stepIndex, setStepIndex] = useState<number>(0);
  const [form, setForm] = useState<SignUpInput>({
    firstName: params.firstName ?? "",
    lastName: params.lastName ?? "",
    email: params.email ?? "",
    phone: params.phone ?? "",
    password: params.password ?? "",
    cnic: "",
    dateOfBirth: "",
    gender: "",
    city: "",
    province: "",
    postalCode: "",
    investmentExperience: "Beginner",
    riskTolerance: "Low",
    investmentGoal: "Long-term",
    monthlyIncome: "",
  });
  const [submitError, setSubmitError] = useState("");
  const [kycErrors, setKycErrors] = useState<Partial<Record<"cnic" | "dateOfBirth" | "gender" | "city" | "province" | "postalCode", string>>>({});
  const [riskErrors, setRiskErrors] = useState<Partial<Record<"monthlyIncome", string>>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const currentStep = STEPS[stepIndex];

  const updateField = <K extends keyof SignUpInput>(field: K, value: SignUpInput[K]) => {
    setForm((previous) => ({ ...previous, [field]: value }));
  };

  const validateKyc = () => {
    const errors: Partial<Record<"cnic" | "dateOfBirth" | "gender" | "city" | "province" | "postalCode", string>> = {};

    if (!form.cnic.trim()) errors.cnic = "CNIC is required.";
    else if (!isValidCnic(form.cnic)) errors.cnic = "CNIC must be in format 35202-5094174-9.";

    if (!form.dateOfBirth.trim()) errors.dateOfBirth = "Date of birth is required.";
    else if (!/^\d{4}-\d{2}-\d{2}$/.test(form.dateOfBirth)) {
      errors.dateOfBirth = "Please select date of birth from the date picker.";
    } else {
      const selectedDate = new Date(form.dateOfBirth);
      const now = new Date();
      if (Number.isNaN(selectedDate.getTime()) || selectedDate >= now) {
        errors.dateOfBirth = "Date of birth must be in the past.";
      }
    }

    if (!form.gender.trim()) errors.gender = "Gender is required.";
    if (!form.city.trim()) errors.city = "City is required.";
    if (!form.province.trim()) errors.province = "Province is required.";

    if (!form.postalCode.trim()) errors.postalCode = "Postal code is required.";
    else if (!isValidPostalCode(form.postalCode)) {
      errors.postalCode = "Postal code must be exactly 5 digits.";
    }

    return errors;
  };

  const validateRisk = () => {
    const errors: Partial<Record<"monthlyIncome", string>> = {};
    if (!form.monthlyIncome.trim()) {
      errors.monthlyIncome = "Please select annual income range.";
    } else if (
      !["under_50k", "50k_100k", "100k_250k", "250k_500k", "500k_1m", "over_1m"].includes(form.monthlyIncome)
    ) {
      errors.monthlyIncome = "Please select a valid income range.";
    }
    return errors;
  };

  const hasErrors = (errors: Record<string, string | undefined>) =>
    Object.values(errors).some(Boolean);

  const onNext = async () => {
    setSubmitError("");
    if (currentStep === "kyc") {
      const nextKycErrors = validateKyc();
      setKycErrors(nextKycErrors);
      if (hasErrors(nextKycErrors)) return;
      setStepIndex((previous) => previous + 1);
      return;
    }

    if (currentStep === "risk") {
      const nextRiskErrors = validateRisk();
      setRiskErrors(nextRiskErrors);
      if (hasErrors(nextRiskErrors)) return;
    } else {
      return;
    }

    try {
      setIsSubmitting(true);
      const { token } = await signUpUser(form);
      await login(token);
      // AuthGuard in _layout.tsx handles the redirect once the token is set
    } catch (signupError) {
      const message = signupError instanceof Error ? signupError.message : "Signup failed.";
      setSubmitError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const onBack = () => {
    setSubmitError("");
    setKycErrors({});
    setRiskErrors({});
    if (stepIndex === 0) {
      router.back();
      return;
    }
    setStepIndex((previous) => previous - 1);
  };

  if (currentStep === "kyc") {
    return (
      <SignUpStepTwoIdentity
        form={{
          cnic: form.cnic,
          dateOfBirth: form.dateOfBirth,
          gender: form.gender,
          city: form.city,
          province: form.province,
          postalCode: form.postalCode,
        }}
        error={submitError}
        fieldErrors={kycErrors}
        onBack={onBack}
        onNext={onNext}
        updateField={(field, value) => {
          type KycKey = "cnic" | "dateOfBirth" | "gender" | "city" | "province" | "postalCode";
          updateField(field as KycKey, value);
        }}
      />
    );
  }

  if (currentStep === "risk") {
    return (
      <SignUpStepThreeFinancial
        form={{
          investmentExperience: form.investmentExperience,
          riskTolerance: form.riskTolerance,
          investmentGoal: form.investmentGoal,
          monthlyIncome: form.monthlyIncome,
        }}
        error={submitError}
        fieldErrors={riskErrors}
        isSubmitting={isSubmitting}
        onBack={onBack}
        onComplete={onNext}
        updateField={(field, value) => {
          if (field === "investmentExperience") updateField("investmentExperience", value as SignUpInput["investmentExperience"]);
          if (field === "riskTolerance") updateField("riskTolerance", value as SignUpInput["riskTolerance"]);
          if (field === "investmentGoal") updateField("investmentGoal", value as SignUpInput["investmentGoal"]);
          if (field === "monthlyIncome") updateField("monthlyIncome", value);
        }}
      />
    );
  }

  return isSubmitting ? <ActivityIndicator /> : null;
}
