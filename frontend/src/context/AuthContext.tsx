import AsyncStorage from "@react-native-async-storage/async-storage";
import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { getUserDetails, UserDetails, verifyToken } from "@/services/auth";

const TOKEN_KEY = "@finmate_auth_token";

type AuthContextType = {
  token: string | null;
  user: UserDetails | null;
  isLoading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchAndStoreUser = useCallback(async (activeToken: string) => {
    try {
      const details = await getUserDetails(activeToken);
      setUser(details);
    } catch {
      // Non-fatal — user details will be null until next refresh
    }
  }, []);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const stored = await AsyncStorage.getItem(TOKEN_KEY);
        if (!stored) {
          setToken(null);
          return;
        }
        const valid = await verifyToken(stored);
        if (valid) {
          setToken(stored);
          await fetchAndStoreUser(stored);
        } else {
          await AsyncStorage.removeItem(TOKEN_KEY);
          setToken(null);
        }
      } catch {
        setToken(null);
      } finally {
        setIsLoading(false);
      }
    };

    bootstrap();
  }, [fetchAndStoreUser]);

  const login = async (newToken: string) => {
    await AsyncStorage.setItem(TOKEN_KEY, newToken);
    setToken(newToken);
    await fetchAndStoreUser(newToken);
  };

  const logout = async () => {
    await AsyncStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  const refreshUser = useCallback(async () => {
    if (!token) return;
    await fetchAndStoreUser(token);
  }, [token, fetchAndStoreUser]);

  return (
    <AuthContext.Provider value={{ token, user, isLoading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
