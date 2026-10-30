/**
 * Auth service — talks to the Atlas AI backend auth endpoints.
 *
 * Browser clients are authenticated via the HTTP-only `atlas_access_token`
 * cookie set by the backend. We still pass `credentials: "include"` so
 * the cookie is sent on every cross-origin request.
 *
 * Sprint 9 Part 2 — every request uses an AbortController with a
 * 5-second deadline. A network hang or a slow backend no longer
 * leaves the UI on the "Checking your session…" loading screen
 * indefinitely; the request rejects with an AuthServiceError whose
 * `status` is 0 and whose name is `AbortError`, and the hook
 * transitions to the `unauthenticated` state.
 */

import { env } from "@/lib/env";
import type { AuthSuccess, UpdateActiveBusinessPayload, User } from "@/types/auth";

const BASE = env.apiBaseUrl.replace(/\/+$/, "");
const DEFAULT_TIMEOUT_MS = 20000;

class AuthServiceError extends Error {
  public readonly status: number;
  public readonly fieldErrors: Record<string, string>;
  public readonly timedOut: boolean;

  constructor(
    message: string,
    status: number,
    fieldErrors: Record<string, string> = {},
    timedOut = false,
  ) {
    super(message);
    this.name = "AuthServiceError";
    this.status = status;
    this.fieldErrors = fieldErrors;
    this.timedOut = timedOut;
  }
}

type ValidationDetail = { loc?: string[]; msg?: string; type?: string };

function extractFieldErrors(detail: unknown): {
  message: string;
  fieldErrors: Record<string, string>;
} {
  if (typeof detail === "string") {
    return { message: detail, fieldErrors: {} };
  }
  if (Array.isArray(detail)) {
    const fieldErrors: Record<string, string> = {};
    for (const entry of detail as ValidationDetail[]) {
      const loc = entry.loc ?? [];
      // loc is e.g. ["body", "password"] — drop the leading "body".
      const field = loc.length > 1 ? String(loc[loc.length - 1]) : "form";
      if (!fieldErrors[field] && entry.msg) {
        fieldErrors[field] = entry.msg;
      }
    }
    const first = (detail as ValidationDetail[])[0];
    return {
      message: first?.msg ?? "Please check the form for errors.",
      fieldErrors,
    };
  }
  return { message: "Request failed.", fieldErrors: {} };
}

interface RequestOptions {
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  headers?: Record<string, string>;
  method?: string;
  signal?: AbortSignal;
  timeoutMs?: number;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const base = BASE;
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  if (!query) {
    return `${base}${cleanPath}`;
  }
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }
    params.append(key, String(value));
  });
  const qs = params.toString();
  return qs ? `${base}${cleanPath}?${qs}` : `${base}${cleanPath}`;
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const {
    body,
    query,
    headers,
    method = "GET",
    signal,
    timeoutMs = DEFAULT_TIMEOUT_MS,
  } = options;

  // Compose a deadline abort signal. If the caller already passed a
  // signal, link through AbortSignal.any() so the caller's abort
  // continues to work alongside our timeout.
  const timeoutController = new AbortController();
  const timeoutHandle = setTimeout(
    () => timeoutController.abort(new DOMException("Request timed out", "TimeoutError")),
    timeoutMs,
  );
  let combinedSignal: AbortSignal = timeoutController.signal;
  if (signal) {
    if (signal.aborted) {
      timeoutController.abort(signal.reason);
    } else {
      const combined = (AbortSignal as unknown as {
        any?: (signals: AbortSignal[]) => AbortSignal;
      }).any;
      if (typeof combined === "function") {
        combinedSignal = combined([signal, timeoutController.signal]);
      } else {
        signal.addEventListener(
          "abort",
          () => timeoutController.abort(signal.reason),
          { once: true },
        );
      }
    }
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      credentials: "include",
      signal: combinedSignal,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(headers ?? {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
  } catch (cause) {
    clearTimeout(timeoutHandle);
    if (cause instanceof Error && (cause.name === "AbortError" || cause.name === "TimeoutError")) {
      throw new AuthServiceError(
        "Request timed out. Please check your connection and try again.",
        0,
        {},
        true,
      );
    }
    if (cause instanceof Error && cause.name === "AbortError") {
      throw new AuthServiceError("Request was cancelled.", 0, {}, false);
    }
    const message = cause instanceof Error ? cause.message : "Network error";
    throw new AuthServiceError(message, 0, {}, false);
  }
  clearTimeout(timeoutHandle);

  // 204 — no body
  if (response.status === 204) {
    return undefined as T;
  }

  let parsed: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!response.ok) {
    const detail = (parsed as { detail?: unknown } | null)?.detail;
    const { message, fieldErrors } = extractFieldErrors(detail);
    throw new AuthServiceError(message, response.status, fieldErrors);
  }

  return parsed as T;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  full_name: string;
  email: string;
  password: string;
}

export const authService = {
  async register(payload: RegisterPayload): Promise<AuthSuccess> {
    return request<AuthSuccess>("/api/v1/auth/register", {
      method: "POST",
      body: payload,
    });
  },

  async login(payload: LoginPayload): Promise<AuthSuccess> {
    return request<AuthSuccess>("/api/v1/auth/login", {
      method: "POST",
      body: payload,
    });
  },

  async logout(): Promise<void> {
    await request<void>("/api/v1/auth/logout", { method: "POST" });
  },

  async me(): Promise<User> {
    return request<User>("/api/v1/auth/me", { method: "GET" });
  },

  /**
   * Sprint 23 — update fields on the authenticated user. Currently
   * only ``active_business_id`` is mutable; the route accepts a
   * payload with just that one field and returns the updated user.
   */
  async updateMe(payload: UpdateActiveBusinessPayload): Promise<User> {
    return request<User>("/api/v1/auth/me", {
      method: "PATCH",
      body: payload,
    });
  },
};

export { AuthServiceError };
