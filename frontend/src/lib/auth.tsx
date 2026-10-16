"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, LOGOUT_EVENT, TOKEN_KEY } from "@/lib/api";
import type { Me } from "@/lib/types";

type AuthState = {
  user: Me | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {}
    setToken(null);
    setUser(null);
  }, []);

  const refreshMe = useCallback(async () => {
    setUser(await api<Me>("/me"));
  }, []);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(TOKEN_KEY);
    } catch {}
    (stored ? api<Me>("/me") : Promise.resolve(null))
      .then((me) => {
        setToken(me ? stored : null);
        setUser(me);
      })
      .catch(() => logout())
      .finally(() => setLoading(false));
  }, [logout]);

  useEffect(() => {
    window.addEventListener(LOGOUT_EVENT, logout);
    return () => window.removeEventListener(LOGOUT_EVENT, logout);
  }, [logout]);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api<{ access_token: string; user: Me }>("/auth/login", { json: { username, password } });
    try {
      localStorage.setItem(TOKEN_KEY, res.access_token);
    } catch {}
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, refreshMe }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/** Use only below the (app) layout, where a user is guaranteed. */
export function useMe(): Me {
  const { user } = useAuth();
  if (!user) throw new Error("Not logged in");
  return user;
}
