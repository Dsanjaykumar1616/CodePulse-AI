import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, onUnauthorized, tokenStore } from "../services/api";
import type { User } from "../types/api";

interface AuthState {
  user: User | null;
  status: "loading" | "authenticated" | "anonymous";
  login: (email: string, password: string, remember: boolean) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>(tokenStore.get() ? "loading" : "anonymous");

  useEffect(() => {
    if (!tokenStore.get()) return;
    let cancelled = false;
    api
      .me()
      .then((me) => {
        if (cancelled) return;
        setUser(me);
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        tokenStore.clear();
        setStatus("anonymous");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(
    () =>
      onUnauthorized(() => {
        setUser(null);
        setStatus("anonymous");
        queryClient.clear();
      }),
    [queryClient],
  );

  const login = useCallback(async (email: string, password: string, remember: boolean) => {
    const result = await api.login({ email, password });
    tokenStore.set(result.access_token, remember);
    setUser(result.user);
    setStatus("authenticated");
  }, []);

  const signup = useCallback(async (name: string, email: string, password: string) => {
    const result = await api.signup({ name, email, password });
    tokenStore.set(result.access_token, true);
    setUser(result.user);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(() => {
    api.logout().catch(() => undefined);
    tokenStore.clear();
    setUser(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo(() => ({ user, status, login, signup, logout }), [user, status, login, signup, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
