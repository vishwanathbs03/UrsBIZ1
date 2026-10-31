/**
 * Typed fetch-based API client.
 *
 * Used by all services to talk to the Atlas AI backend. Throws an
 * `ApiError` on non-2xx responses so callers can handle failures in a
 * single place. This is a placeholder; per-endpoint helpers are added
 * in later milestones.
 */

import { env } from "@/lib/env";

export class ApiError extends Error {
  public readonly status: number;
  public readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }

  /** Network-level failure — DNS, refused connection, unreachable host.
   *  Signalled with ``status === 0``. */
  get isNetworkError(): boolean {
    return this.status === 0;
  }

  /** The request exceeded the client-side timeout budget. */
  get isTimeout(): boolean {
    const b = this.body as { type?: unknown } | null;
    return this.status === 0 && b?.type === "AbortError";
  }

  /** 401 — session missing/invalid/expired. */
  get isUnauthenticated(): boolean {
    return this.status === 401;
  }

  /** 422 — request body failed server-side validation. */
  get isValidationError(): boolean {
    return this.status === 422;
  }

  /** 409 — conflict (duplicate resource, already-exists). */
  get isConflict(): boolean {
    return this.status === 409;
  }

  /** 5xx — the backend itself failed. */
  get isServerError(): boolean {
    return this.status >= 500;
  }
}

export type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  timeoutMs?: number;
};

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const base = env.apiBaseUrl.replace(/\/+$/, "");
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

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function apiRequest<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, query, headers, timeoutMs: customTimeoutMs, ...rest } = options;
  const url = buildUrl(path, query);

  // Temporary request/response trace for the business wizard. DEV ONLY —
  // compiled out of production bundles. Never add secrets here.
  const traceBusReq =
    process.env.NODE_ENV !== "production" && path.startsWith("/api/v1/business");
  if (traceBusReq) {
    // eslint-disable-next-line no-console
    console.log("[BUSREQ-REQ]", rest.method ?? "?", url, {
      body,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
    });
  }

  // Network-level timeout. Defaults to 15s for standard requests, or
  // caller-specified budget (e.g. 150s for LLM generation).
  const timeoutMs = customTimeoutMs ?? 15000;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  // If the caller passed their own signal, link it through.
  if (rest.signal) {
    const userSignal = rest.signal as AbortSignal;
    if (userSignal.aborted) {
      ctrl.abort(userSignal.reason);
    } else {
      userSignal.addEventListener(
        "abort",
        () => ctrl.abort(userSignal.reason),
        { once: true },
      );
    }
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...rest,
      signal: ctrl.signal,
      // The backend issues the JWT as an HTTP-only cookie. Browsers
      // refuse to attach it on cross-origin requests unless the
      // request opts in via `credentials: "include"`. Without this,
      // POST /business, GET /auth/me and every other protected
      // endpoint return 401 after login even though the cookie is
      // present in the browser jar.
      credentials: rest.credentials ?? "include",
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (cause) {
    clearTimeout(timer);
    // Network failure (DNS, refused, IPv6 unreachable, etc.).
    // Convert the raw TypeError into an ApiError so callers can
    // recognise the failure mode uniformly instead of guessing on
    // `err instanceof TypeError`.
    if (cause instanceof Error && cause.name === "AbortError") {
      throw new ApiError(
        "Request timed out. Please check your connection and try again.",
        0,
        { detail: "Network error: request timed out", type: "AbortError" },
      );
    }
    const message = cause instanceof Error ? cause.message : "Network error";
    throw new ApiError(
      `Could not reach the server. ${message}. ` +
        "If the backend is running on a different host or port, set NEXT_PUBLIC_API_URL.",
      0,
      { detail: "Network error", type: "NetworkError", cause: message },
    );
  }
  clearTimeout(timer);

  const parsed = await parseBody(response);

  if (traceBusReq) {
    // H7.1 Part 5 — log only the status code, not the response body. The
    // body is the user's full business profile (employee count, revenue,
    // products, certifications, etc.) — never log that, even in dev.
    // eslint-disable-next-line no-console
    console.log("[BUSREQ-RES]", rest.method ?? "?", url, response.status);
  }

  if (!response.ok) {
    const message =
      (parsed && typeof parsed === "object" && "detail" in parsed
        ? String((parsed as { detail: unknown }).detail)
        : null) ?? `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, parsed);
  }

  return parsed as T;
}

export const apiClient = {
  get: <T = unknown>(path: string, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: "GET" }),
  post: <T = unknown>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: "POST", body }),
  put: <T = unknown>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: "PUT", body }),
  patch: <T = unknown>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: "PATCH", body }),
  delete: <T = unknown>(path: string, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: "DELETE" }),
};
