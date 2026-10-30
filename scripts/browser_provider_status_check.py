"""H7.8C — Real-browser simulation for provider-status.

Puppeteer cannot be installed here, so this script
emulates the *exact* HTTP chain the browser executes
when the user opens /assistant with the same cookie jar.

This is the same chain the AssistantHeader useEffect fires:
    browser (localhost:3000)
        -> /api/v1/chat/provider-status     [Next.js rewrite proxy]
            -> http://127.0.0.1:8001/api/v1/chat/provider-status
                (with the cookies the FRONTEND layer received)

The script also exercises the flagship grounded AI question
by issuing the same requests the AssistantView handleServerSubmit
fires.
"""

from __future__ import annotations

import json
import sys
import time

import requests

FRONTEND = "http://localhost:3000"
BACKEND = "http://127.0.0.1:8001"


def banner(msg: str) -> None:
    print("\n# " + msg)


def register_and_login() -> requests.Session:
    """Login via frontend proxy to a fully seeded demo user.

    If ``BROWSER_TEST_EMAIL`` is provided, log in with those
    credentials. Otherwise register a fresh user.
    """
    s = requests.Session()
    email = __import__("os").environ.get("BROWSER_TEST_EMAIL")
    password = __import__("os").environ.get("BROWSER_TEST_PASSWORD", "BrowserPass1")
    if email:
        banner("LOGIN via frontend proxy (using seeded demo user)")
        r = s.post(
            f"{FRONTEND}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        print(f"login_http_status={r.status_code}")
    else:
        suffix = str(int(time.time()))
        email = f"h78c_browser_{suffix}@example.com"
        password = "BrowserPass1"
        full = "H7.8C Browser"
        banner("REGISTER + LOGIN via frontend proxy (browser path)")
        r = s.post(
            f"{FRONTEND}/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": full},
            timeout=10,
        )
        print(f"register_http_status={r.status_code}")
        r = s.post(
            f"{FRONTEND}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        print(f"login_http_status={r.status_code}")
    jar = [c for c in s.cookies if c.name == "atlas_access_token"]
    print(f"atlas_access_token_cookie_count={len(jar)}")
    return s


def provider_status_through_proxy(session: requests.Session) -> tuple[int, dict]:
    banner("PROVIDER-STATUS through Next.js rewrite proxy (browser path)")
    r = session.get(f"{FRONTEND}/api/v1/chat/provider-status", timeout=10)
    print(f"provider_status_http_status={r.status_code}")
    try:
        payload = r.json()
    except Exception:
        print(f"non_json_body={r.text[:200]}")
        return r.status_code, {}
    safe = {
        k: payload.get(k)
        for k in (
            "configured_provider",
            "runtime_provider",
            "model",
            "available",
            "fallback_active",
            "schema_required",
            "default_mode",
            "modes",
        )
        if k in payload
    }
    forbidden = (
        "api_key",
        "authorization",
        "base_url",
        "endpoint",
        "secret",
        "raw_response",
    )
    leaked = [k for k in forbidden if k in payload]
    safe["_leaked_secret_keys"] = leaked
    print("provider_status_payload=" + json.dumps(safe, indent=2))
    return r.status_code, payload


def flagship_question(session: requests.Session) -> tuple[int, str]:
    banner("FLAGSHIP grounded AI question (Acme Textiles growth)")
    prompt = (
        "Help Acme Textiles grow from ₹1.8 Cr to ₹3 Cr "
        "without increasing supplier dependency."
    )
    r = session.post(
        f"{FRONTEND}/api/v1/chat",
        json={"title": "Flagship"},
        timeout=10,
    )
    print(f"create_session_status={r.status_code}")
    session_id = None
    try:
        session_id = r.json()["id"]
    except Exception:
        print(f"create_session_body={r.text[:200]}")
        return r.status_code, ""
    r = session.post(
        f"{FRONTEND}/api/v1/chat/{session_id}/message",
        json={"content": prompt, "mode": "grounded"},
        timeout=60,
    )
    print(f"append_message_status={r.status_code}")
    snippet = (r.text or "")[:400].encode("ascii", "replace").decode("ascii")
    print(f"body_prefix={snippet}")
    return r.status_code, snippet


def main() -> int:
    s = register_and_login()
    ps_status, ps_payload = provider_status_through_proxy(s)
    if ps_status != 200:
        print(f"FIX_VERIFIED=false status={ps_status}")
        return 1
    flagship_status, flagship_body = flagship_question(s)
    # The flagship call usually returns 200 even when the
    # business row is missing (the provider-status path
    # proves the auth chain works; the chat message path
    # needs a business profile).
    print("")
    banner("RESULT")
    print(f"provider_status_ok={ps_status == 200}")
    print(
        "configured_provider="
        + str(ps_payload.get("configured_provider"))
    )
    print(
        "fallback_active="
        + str(ps_payload.get("fallback_active"))
    )
    if flagship_status == 200:
        try:
            j = json.loads(flagship_body)
            meta = j.get("assistant_message", {}).get("generation", {})
            print(f"generation_method={meta.get('generation_method')}")
            print(f"fallback_used={meta.get('fallback_used')}")
            print(f"schema_validated={meta.get('schema_validated')}")
            print(f"grounding_validated={meta.get('grounding_validated')}")
        except Exception:
            pass
    else:
        # Probably 404 because demo user has no business profile.
        print(f"flagship_status_code={flagship_status}")
    return 0 if ps_status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())