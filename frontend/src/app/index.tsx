import { useAuth } from "@/context/AuthContext";
import { loginUser } from "@/services/auth";
import { colors, fonts, globalStyles } from "@/styles/global";
import { Link } from "expo-router";
import { Eye, EyeOff } from "lucide-react-native";
import { useState } from "react";
import {
  ActivityIndicator,
  Image,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import WhiteLogo from "../assets/finmate-white-logo.png";

export default function Index() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const onLogin = async () => {
    setError("");

    if (!email.trim() || !password.trim()) {
      setError("Please fill in all fields.");
      return;
    }

    try {
      setIsSubmitting(true);
      const { token } = await loginUser({ email: email.trim(), password });
      await login(token);
      // AuthGuard in _layout.tsx handles the redirect to /(tabs)
    } catch (loginError) {
      const message =
        loginError instanceof Error ? loginError.message : "Login failed.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.topPanel}>
        <View>
          <Image
            source={WhiteLogo}
            style={styles.logoImage}
            resizeMode="contain"
          />
        </View>
      </View>

      <View style={styles.card}>
        <Text style={[globalStyles.heading, styles.heading]}>LogIn</Text>

        <TextInput
          value={email}
          onChangeText={setEmail}
          placeholder="Email"
          placeholderTextColor={colors.mutedText}
          style={styles.input}
          autoCapitalize="none"
          keyboardType="email-address"
        />
        <View style={styles.passwordWrap}>
          <TextInput
            value={password}
            onChangeText={setPassword}
            placeholder="Password"
            placeholderTextColor={colors.mutedText}
            style={[styles.input, styles.passwordInput]}
            secureTextEntry={!showPassword}
          />
          <Pressable
            onPress={() => setShowPassword((p) => !p)}
            style={styles.eyeButton}
            hitSlop={8}
          >
            {showPassword
              ? <EyeOff color={colors.mutedText} size={18} />
              : <Eye color={colors.mutedText} size={18} />}
          </Pressable>
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          style={[styles.button, isSubmitting && styles.disabledButton]}
          onPress={onLogin}
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <ActivityIndicator color={colors.background} />
          ) : (
            <Text style={styles.buttonText}>Login</Text>
          )}
        </Pressable>

        <View style={styles.orRow}>
          <View style={styles.orLine} />
          <Text style={[globalStyles.text, styles.orText]}>Or</Text>
          <View style={styles.orLine} />
        </View>

        <Link href="/signup" style={[globalStyles.text, styles.link]}>
          Don&apos;t Have Any Account?{" "}
          <Text style={styles.linkStrong}>Sign Up</Text>
        </Link>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.secondary,
  },
  topPanel: {
    height: 180,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  logoImage: {
    width: 60,
    height: 60,
    marginTop: 30,
  },
  card: {
    flex: 1,
    borderTopLeftRadius: 34,
    borderTopRightRadius: 34,
    marginTop: -22,
    padding: 22,
    backgroundColor: colors.background,
  },
  heading: {
    fontSize: 28,
    letterSpacing: -1.5,
    marginBottom: 28,
    textAlign: "center",
  },
  input: {
    borderWidth: 1,
    borderColor: colors.borderLight,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontFamily: fonts.body,
    fontSize: 14,
    marginBottom: 14,
    color: colors.text,
  },
  passwordWrap: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.borderLight,
    borderRadius: 10,
    marginBottom: 14,
  },
  passwordInput: {
    flex: 1,
    borderWidth: 0,
    marginBottom: 0,
    borderRadius: 10,
  },
  eyeButton: {
    paddingHorizontal: 12,
    justifyContent: "center",
    alignItems: "center",
  },
  error: {
    fontFamily: fonts.body,
    color: colors.error,
    marginBottom: 8,
  },
  button: {
    height: 46,
    borderRadius: 10,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 6,
  },
  disabledButton: {
    opacity: 0.5,
  },
  buttonText: {
    color: colors.background,
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
  },
  orRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 26,
  },
  orLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.divider,
  },
  orText: {
    marginHorizontal: 10,
    color: colors.textSecondary,
    fontSize: 14,
  },
  link: {
    textAlign: "center",
    marginTop: 20,
    fontSize: 14,
  },
  linkStrong: {
    fontFamily: fonts.bodyMedium,
    color: colors.text,
  },
});
