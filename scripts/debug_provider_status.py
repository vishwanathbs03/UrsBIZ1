"""H7.8C — programmatic reproduction of the authenticated
``/api/v1/chat/provider-status`` request that the frontend
fires from the Assistant header.

WHAT THIS SCRIPT DOES
=====================

  1. Logs in as the demo user with email/password and saves
     the resulting ``atlas_access_token`` cookie to a
     ``requests.cookies`` jar.
  2. Prints ``has_atlas_access_token=true|false`` based on the
     cookie jar — NEVER the JWT value.
  3. Calls ``/api/v1/chat/provider-status`` via:
       a. the frontend proxy at ``http://localhost:3000`` (the
          path the browser uses)
       b. the backend direct at ``http://127.0.0.1:8001`` (the
          path the rewrites proxy forwards to)
  4. Prints ``provider_status_http_status=...`` for each call.
  5. Confirms the response payload is the canonical status
     shape (configures_provider / model / available /
     fallback_active / default_mode) without any secret leak.

The hard rule that scripts must NEVER print the JWT value is
enforced by redaction: the cookie value is logged as the byte
length only.
"""

from __future__ import annotations

import json
import os
import sys
import time
from urllib.parse import urlencode

import requests

FRONTEND_BASE = "http://localhost:3000"
BACKEND_BASE = "http://127.0.0.1:8001"


def _register_and_login() -> requests.cookies.RequestsCookieJar:
    """Register a fresh demo user, then log in and return the cookie jar."""
    session = requests.Session()
    suffix = str(int(time.time()))
    email = f"h78c_demo_{suffix}@example.com"
    password = "DemoPass123"
    full_name = "H7.8C Demo"
    # Register.
    reg = session.post(
        f"{BACKEND_BASE}/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
        timeout=8,
    )
    print(f"register_http_status={reg.status_code}")
    # Login via FRONTEND proxy (the path the Assistant page uses
    # for everything — same-origin via the rewrite).
    resp = session.post(
        f"{FRONTEND_BASE}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=8,
    )
    print(f"login_http_status={resp.status_code}")
    if resp.status_code != 200:
        # Try backend direct as fallback.
        resp2 = session.post(
            f"{BACKEND_BASE}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=8,
        )
        print(f"login_direct_http_status={resp2.status_code}")

    # Look up the cookie by NAME (not by domain) so multiple
    # same-name cookies from proxy + backend do not blow up.
    matching = [c for c in session.cookies if c.name == "atlas_access_token"]
    has_atlas = bool(matching)
    print(f"has_atlas_access_token={str(has_atlas).lower()}")
    print(f"atlas_access_token_cookie_count={len(matching)}")
    print(
        "atlas_access_token_domains="
        + ",".join(sorted({(c.domain or '') for c in matching}))
    )
    return session.cookies


def _trace_provider_status(label: str, base: str, cookie_jar) -> None:
    print(f"--- {label} ---")
    print(f"target={base}/api/v1/chat/provider-status")
    # We hand the cookies over to a fresh Session so we KNOW the
    # cookie is present in the jar. We re-attach with
    # ``cookies.set_cookie`` which permits multiple cookies with
    # the same name (the default ``requests.Session`` accessor
    # refuses them with a CookieConflictError).
    carry = requests.Session()
    for c in cookie_jar:
        carry.cookies.set_cookie(c)
    try:
        resp = carry.get(
            f"{base}/api/v1/chat/provider-status",
            timeout=10,
        )
    except requests.RequestException as exc:
        print(f"request_error={exc}")
        return
    print(f"provider_status_http_status={resp.status_code}")
    if resp.status_code == 200:
        try:
            payload = resp.json()
        except Exception:
            print(f"provider_status_payload=non-json raw={resp.text[:200]}")
            return
        # Print only the SAFE fields — never echo API keys or
        # upstream URLs.
        safe_keys = (
            "configured_provider",
            "runtime_provider",
            "model",
            "available",
            "fallback_active",
            "schema_required",
            "default_mode",
            "modes",
        )
        safe = {k: payload.get(k) for k in safe_keys if k in payload}
        # Sanity: the secret-bearing fields must NOT be in the
        # payload.
        forbidden = ("api_key", "authorization", "base_url", "endpoint")
        leaked = [k for k in forbidden if k in payload]
        safe["_leaked_secret_keys"] = leaked
        print("provider_status_payload=" + json.dumps(safe, indent=2))
    else:
        snippet = (resp.text or "")[:120]
        print(f"provider_status_body_snippet={snippet}")


def main() -> int:
    print("# H7.8C — provider-status diagnostic trace")
    print(f"# ts={int(time.time())}")
    jar = _register_and_login()
    # Existence check (multiple cookies may have the same name).
    if not [c for c in jar if c.name == "atlas_access_token"]:
        print("no_cookie_present_aborting_status_checks=true")
        return 1
    _trace_provider_status("FRONTEND_PROXY (browser path)", FRONTEND_BASE, jar)
    _trace_provider_status("DIRECT_BACKEND", BACKEND_BASE, jar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
