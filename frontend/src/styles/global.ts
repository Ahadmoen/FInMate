import { StyleSheet } from "react-native";

export const colors = {
  background: "#FFFFFF",
  text: "#000000",
  primary: "#0D4954",
  secondary: "#0D4954",
  border: "#E5E7EB",
  borderLight: "#ECECEC",
  mutedText: "#6B7280",
  textSecondary: "#495057",
  divider: "#B8C0CC",
  error: "#B00020",
  // SignUp Flow Colors
  primaryAccent: "#0D4954",
  textMuted: "#5D6473",
  textTertiary: "#4F5868",
  textQuaternary: "#3D4655",
  textQuinary: "#3C475D",
  textSenary: "#212937",
  textSepternary: "#1F2937",
  textOctonary: "#111827",
  textNonary: "#0D4954",
  textDecenary: "#4E5768",
  borderMuted: "#D8DEE8",
  borderMutedLight: "#CED5DF",
  borderMutedDark: "#D6DDE9",
  bgLight: "#F5F7FB",
  bgLighter: "#F8FAFD",
  bgLightest: "#FBFCFF",
  bgPrimaryLight: "#EAF2F5",
  bgSecondaryLight: "#E3E8EB",
  bgTertiaryLight: "#DCE6E9",
  bgIconLight: "#D4DFE2",
  headerBorder: "#E3E8EF",
  stepTrackActive: "#255B65",
  stepTrackFill: "#3D6D76",
  radioBorder: "#B6BFCE",
  recommendationBorder: "#C7CEDA",
  bgRecommendation: "#F7F9FC",
  stepBarInactive: "#C8CFDB",
  // Theme Shades
  themeLight: "#557F87",
  themeMedium: "#3D6D76",
  themeDark: "#255B65",
  themeDarkest: "#0D4954",
};

export const fonts = {
  heading: "Inter_600SemiBold",
  body: "Montserrat_400Regular",
  bodyMedium: "Montserrat_500Medium",
};

export const globalStyles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  heading: {
    fontFamily: fonts.heading,
    letterSpacing: -1.5,
    color: colors.text,
  },
  text: {
    fontFamily: fonts.body,
    color: colors.text,
  },
});
