"""UI Verification and Screenshot Automation Script using Chrome DevTools Protocol (CDP)."""

import asyncio
import base64
import json
import os
import subprocess
import time
import urllib.request
import websockets

OUT_DIR = r"C:\Users\Dell\.gemini\antigravity\brain\d289edac-a711-41e0-893e-2e9d295b4654\screenshots"
USER_DIR = r"C:\Users\Dell\AppData\Local\Temp\chrome_verify_clean3"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

os.makedirs(OUT_DIR, exist_ok=True)

VIEWPORTS = [
    ("dashboard_desktop_1440.png", 1440, 900, False),
    ("dashboard_laptop_1280.png", 1280, 800, False),
    ("dashboard_tablet_768.png", 768, 1024, True),
    ("dashboard_mobile_390.png", 390, 844, True),
]

PAGES = [
    ("analytics.png", "http://localhost:3000/analytics", 1440, 900),
    ("forecast.png", "http://localhost:3000/predictive-analytics", 1440, 900),
    ("assistant.png", "http://localhost:3000/assistant", 1440, 900),
    ("reports.png", "http://localhost:3000/reports", 1440, 900),
    ("schemes.png", "http://localhost:3000/schemes", 1440, 900),
    ("business_profile.png", "http://localhost:3000/business", 1440, 900),
    ("action_board.png", "http://localhost:3000/action-board", 1440, 900),
    ("notifications.png", "http://localhost:3000/notifications", 1440, 900),
]


def get_auth_token():
    req = urllib.request.Request(
        "http://localhost:3000/api/v1/auth/login",
        data=json.dumps({"email": "acme.textiles@example.com", "password": "AcmeDemoPass1!"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["access_token"]


async def main():
    token = get_auth_token()
    print(f"[0] Acquired session token: {token[:25]}...", flush=True)

    print("[1] Starting Chrome in headless CDP mode...", flush=True)
    proc = subprocess.Popen([
        CHROME_PATH,
        "--headless=new",
        "--remote-debugging-port=9224",
        "--disable-gpu",
        "--disable-extensions",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={USER_DIR}"
    ])
    time.sleep(2.5)

    try:
        with urllib.request.urlopen("http://127.0.0.1:9224/json") as r:
            tabs = json.loads(r.read().decode("utf-8"))
            pages = [t for t in tabs if t.get("type") == "page"]
            ws_url = pages[0]["webSocketDebuggerUrl"]

        print(f"[2] Connecting to CDP WebSocket: {ws_url}", flush=True)
        async with websockets.connect(ws_url, max_size=25_000_000) as ws:
            msg_id = 0

            async def send(method, params=None):
                nonlocal msg_id
                msg_id += 1
                payload = {"id": msg_id, "method": method}
                if params:
                    payload["params"] = params
                await ws.send(json.dumps(payload))
                while True:
                    resp = json.loads(await ws.recv())
                    if resp.get("id") == msg_id:
                        return resp.get("result", {})

            await send("Page.enable")
            await send("Runtime.enable")
            await send("Network.enable")

            # Set the authenticated cookies in Chrome
            cookie_res = await send("Network.setCookie", {
                "name": "atlas_access_token",
                "value": token,
                "domain": "localhost",
                "path": "/",
                "httpOnly": True,
                "sameSite": "Lax"
            })
            print(f"[3] Set auth cookie: {cookie_res}", flush=True)

            # Navigate directly to Dashboard
            print("[4] Navigating to dashboard...", flush=True)
            await send("Page.navigate", {"url": "http://localhost:3000/dashboard"})
            await asyncio.sleep(4)

            loc_res = await send("Runtime.evaluate", {"expression": "window.location.href"})
            print(f"[5] Landed URL: {loc_res.get('result', {}).get('value')}", flush=True)

            # Capture Dashboard in all 4 viewports
            print("[6] Capturing Dashboard across responsive viewports...", flush=True)
            for fname, w, h, is_mobile in VIEWPORTS:
                await send("Emulation.setDeviceMetricsOverride", {
                    "width": w,
                    "height": h,
                    "deviceScaleFactor": 1,
                    "mobile": is_mobile
                })
                await asyncio.sleep(2)
                shot = await send("Page.captureScreenshot", {"format": "png"})
                out_path = os.path.join(OUT_DIR, fname)
                with open(out_path, "wb") as f:
                    f.write(base64.b64decode(shot["data"]))
                print(f"    Saved: {fname} ({w}x{h}, mobile={is_mobile})", flush=True)

            # Capture other core pages
            print("[7] Capturing other application pages...", flush=True)
            for fname, url, w, h in PAGES:
                await send("Emulation.setDeviceMetricsOverride", {
                    "width": w,
                    "height": h,
                    "deviceScaleFactor": 1,
                    "mobile": False
                })
                await send("Page.navigate", {"url": url})
                await asyncio.sleep(3)
                shot = await send("Page.captureScreenshot", {"format": "png"})
                out_path = os.path.join(OUT_DIR, fname)
                with open(out_path, "wb") as f:
                    f.write(base64.b64decode(shot["data"]))
                print(f"    Saved: {fname} from {url}", flush=True)

            # Language switcher test: switch to Kannada
            print("[8] Testing Language Switcher on Dashboard (EN -> Kannada)...", flush=True)
            await send("Page.navigate", {"url": "http://localhost:3000/dashboard"})
            await asyncio.sleep(2.5)
            toggle_kn_js = """
                (() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const knBtn = buttons.find(b => b.textContent && b.textContent.includes('ಕನ್ನಡ'));
                    if (knBtn) {
                        knBtn.click();
                        return 'kannada_clicked';
                    }
                    return 'kannada_btn_not_found';
                })()
            """
            kn_eval = await send("Runtime.evaluate", {"expression": toggle_kn_js})
            print(f"    Language toggle result: {kn_eval.get('result', {}).get('value')}", flush=True)
            await asyncio.sleep(2)
            shot = await send("Page.captureScreenshot", {"format": "png"})
            with open(os.path.join(OUT_DIR, "dashboard_kannada.png"), "wb") as f:
                f.write(base64.b64decode(shot["data"]))
            print("    Saved: dashboard_kannada.png", flush=True)

            print("\nAll verification screenshots captured successfully!", flush=True)

    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
