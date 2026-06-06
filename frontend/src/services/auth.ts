import Constants from "expo-constants";

// In Expo Go the Metro bundler host == the dev machine hosting the backend.
// EXPO_PUBLIC_API_BASE_URL overrides this for any other setup.
const metroHost = Constants.expoConfig?.hostUri?.split(":")[0];
const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  (metroHost ? `http://${metroHost}:3100/api/v1` : "http://localhost:3100/api/v1");

async function post(path: string, body: object): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function verifyToken(token: string): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/users/profile/`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.ok;
  } catch {
    // Network error — treat token as valid so we don't log out on poor connectivity
    return true;
  }
}

function extractError(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const d = data as Record<string, unknown>;
  if (typeof d.detail === "string") return d.detail;
  if (typeof d.message === "string") return d.message;
  if (typeof d.error === "string") return d.error;
  const firstVal = Object.values(d)[0];
  if (Array.isArray(firstVal) && firstVal.length > 0) return String(firstVal[0]);
  return fallback;
}

export type LoginInput = {
  email: string;
  password: string;
};

export type SignUpInput = {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  password: string;
  cnic: string;
  dateOfBirth: string;
  gender: string;
  city: string;
  province: string;
  postalCode: string;
  investmentExperience: "Beginner" | "Intermediate" | "Expert";
  riskTolerance: "Low" | "Medium" | "High";
  investmentGoal: "Short-term" | "Long-term" | "Trading" | "Dividend income";
  monthlyIncome: string;
};

export async function checkEmailTaken(email: string): Promise<boolean> {  
  try {
    const response = await post("/users/check-email/", { email });
    const data = await response.json();
    return data?.taken === true;
  } catch {
    return false;
  }
}

export async function loginUser(payload: LoginInput): Promise<{ token: string }> {
  let response: Response;
  try {
    response = await post("/login/", { email: payload.email, password: payload.password });
  } catch {
    throw new Error("Network error. Make sure the backend is running.");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Invalid credentials."));
  }

  const data = await response.json();
  if (!data?.access) throw new Error("Server did not return a token.");
  return { token: data.access };
}

export type UserDetails = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  whatsapp_number: string;
  slack_webhook: string;
  kyc_profile: {
    cnic: string;
    date_of_birth: string;
    gender: string;
    city: string;
    province: string;
    postal_code: string;
  };
  investment_profile: {
    investment_experience: string;
    risk_tolerance: string;
    investment_goals: string[];
    income_range: string;
  };
};

export async function getUserDetails(token: string): Promise<UserDetails> {
  const response = await fetch(`${API_BASE}/users/details/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Failed to fetch user details.");
  return response.json();
}

export type UserProfileData = {
  email: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  cnic: string;
  date_of_birth: string;
  gender: string;
  city: string;
  province: string;
  postal_code: string;
};

export async function updateUserProfile(
  token: string,
  data: Partial<Omit<UserProfileData, "email" | "cnic">>
): Promise<void> {
  const response = await fetch(`${API_BASE}/users/edit/`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const json = await response.json().catch(() => null);
    throw new Error(extractError(json, "Failed to update profile."));
  }
}

export type InvestmentProfileData = {
  investment_experience: string;
  risk_tolerance: string;
  investment_goals: string[];
  income_range: string;
};

export async function updateInvestmentProfile(
  token: string,
  data: Partial<InvestmentProfileData>
): Promise<void> {
  const response = await fetch(`${API_BASE}/users/investment-profile/`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const json = await response.json().catch(() => null);
    throw new Error(extractError(json, "Failed to update investment profile."));
  }
}

export async function signUpUser(payload: SignUpInput): Promise<{ token: string }> {
  const digits = payload.phone.replace(/\D/g, "");
  const phoneNumber =
    digits.length === 11 && digits.startsWith("0")
      ? `+92${digits.slice(1)}`
      : payload.phone.trim();

  const experienceMap: Record<SignUpInput["investmentExperience"], string> = {
    Beginner: "beginner",
    Intermediate: "intermediate",
    Expert: "expert",
  };
  const riskMap: Record<SignUpInput["riskTolerance"], string> = {
    Low: "low",
    Medium: "medium",
    High: "high",
  };
  const goalMap: Record<SignUpInput["investmentGoal"], string> = {
    "Short-term": "short_term",
    "Long-term": "long_term",
    Trading: "trading",
    "Dividend income": "dividend_income",
  };

  let response: Response;
  try {
    response = await post("/users/register/", {
      email: payload.email.trim(),
      password: payload.password,
      first_name: payload.firstName.trim(),
      last_name: payload.lastName.trim(),
      phone_number: phoneNumber,
      cnic: payload.cnic.trim(),
      date_of_birth: payload.dateOfBirth,
      gender: payload.gender.trim().toLowerCase(),
      city: payload.city.trim(),
      province: payload.province.trim(),
      postal_code: payload.postalCode.trim(),
      investment_experience: experienceMap[payload.investmentExperience],
      risk_tolerance: riskMap[payload.riskTolerance],
      investment_goals: [goalMap[payload.investmentGoal]],
      income_range: payload.monthlyIncome.trim(),
    });
  } catch {
    throw new Error("Network error. Make sure the backend is running.");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(extractError(data, "Signup failed."));
  }

  const data = await response.json();
  // Backend returns the JWT as top-level `access` (same as /login/);
  // keep the legacy tokens.access as a fallback just in case.
  const token = data?.access ?? data?.tokens?.access;
  if (!token) throw new Error("Server did not return an access token.");
  return { token };
}
