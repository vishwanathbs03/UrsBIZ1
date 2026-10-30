"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  authService,
  AuthServiceError,
  type LoginPayload,
  type RegisterPayload,
} from "@/services/auth-service";
import type { User } from "@/types/auth";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  /**
   * Sprint 23 — local setter used by the active-business switcher.
   * ``refresh()`` is unchanged: it still re-fetches from the
   * server. ``setUser`` is the surgical update when the panel
   * already has the new User payload in hand (returned by
   * ``PATCH /auth/me``).
   */
  setUser: (user: User | null) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Provider that:
 *   1. On mount, asks the backend who the current user is. This
 *      re-establishes the session from the HTTP-only cookie so a
 *      page refresh keeps the user signed in.
 *   2. Exposes login / register / logout helpers.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<User | null>(null);

  const refresh = useCallback(async () => {
    try {
      const me = await authService.me();
      setUser(me);
      setStatus("authenticated");
    } catch (error) {
      // Sprint 9 Part 2 — every AuthServiceError (including the
      // new timedOut case and any other network error) now moves
      // us to the ``unauthenticated`` state so the UI never sits
      // forever on "Checking your session…". 401 is treated the
      // same path (no session), but other errors are also fine
      // to surface as unauthenticated so the login screen is
      // reachable and the user can retry.
      setUser(null);
      setStatus("unauthenticated");
      if (error instanceof AuthServiceError) {
        if (error.timedOut) {
          // Logged once so an operator watching the console
          // knows the backend was unreachable, then dropped.
          // eslint-disable-next-line no-console
          console.warn("auth refresh: request timed out");
        } else if (error.status !== 401) {
          // eslint-disable-next-line no-console
          console.warn("auth refresh: status=" + error.status);
        }
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (payload: LoginPayload) => {
    const result = await authService.login(payload);
    setUser(result.user);
    setStatus("authenticated");
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    const result = await authService.register(payload);
    setUser(result.user);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } finally {
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      login,
      register,
      logout,
      refresh,
      setUser,
    }),
    [status, user, login, register, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>.");
  }
  return ctx;
}
