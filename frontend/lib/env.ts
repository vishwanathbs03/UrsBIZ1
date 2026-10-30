/**
 * Type-safe environment loader.
 *
 * Reads `process.env.NEXT_PUBLIC_*` variables on the client and any
 * server-only vars on the server. Throws if a required variable is
 * missing at startup so misconfiguration fails fast.
 *
 * Cookie fix (H2): In the browser, API requests MUST go through the
 * Next.js rewrite proxy at `/api/v1/...` (same-origin as the frontend)
 * so the auth cookie is always included. Bypassing the proxy by
 * sending requests directly to `127.0.0.1:8001` causes `SameSite=lax`
 * cookie blocking because the browser page is on `localhost:3000` and
 * the API is on a different hostname.
 *
 * Server-side (SSR) requests can still hit the backend directly via
 * the NEXT_PUBLIC_API_URL env var because there is no browser cookie
 * jar involved — they use the Authorization header or skip auth.
 */

type EnvShape = {
  /** Backend base URL (no trailing slash). Empty string = use relative URLs (proxy). */
  apiBaseUrl: string;
  /** Public app name exposed to the client. */
  appName: string;
  /** Public app URL for canonical / OpenGraph references. */
  appUrl: string;
};

const DEFAULTS: EnvShape = {
  // Empty string → relative URL → requests go to /api/v1/... on the same
  // origin as the page → Next.js rewrites proxy them to the backend.
  // This is the correct behaviour for browser clients because it keeps
  // the auth cookie same-origin (SameSite=lax safe).
  apiBaseUrl: "",
  appName: "UrsBiz",
  appUrl: "http://localhost:3000",
};

function cleanUrl(url: string): string {
  return url.trim().replace(/\/+$/, "").replace(/\/api\/v1$/, "");
}

export const env: EnvShape = {
  // In the browser, ALWAYS use empty string so requests are relative (same-origin proxy).
  // This keeps the auth cookie on the frontend domain and avoids cross-origin cookie drops.
  apiBaseUrl:
    typeof window !== "undefined"
      ? ""
      : process.env.NEXT_PUBLIC_API_URL
        ? cleanUrl(process.env.NEXT_PUBLIC_API_URL)
        : process.env.NEXT_PUBLIC_API_BASE_URL
          ? cleanUrl(process.env.NEXT_PUBLIC_API_BASE_URL)
          : DEFAULTS.apiBaseUrl,
  appName:
    process.env.NEXT_PUBLIC_APP_NAME || DEFAULTS.appName,
  appUrl: cleanUrl(
    process.env.NEXT_PUBLIC_APP_URL || DEFAULTS.appUrl,
  ),
};
