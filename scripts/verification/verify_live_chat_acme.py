"""Test AI Chat assistant with Acme Textiles profile on live Render deployment."""

import sys
import time
import httpx

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND_URL = "https://ursbiz-backend.onrender.com"

def test_chat():
    client = httpx.Client(base_url=BACKEND_URL, timeout=30.0)

    # 1. Login Acme Textiles
    login = client.post("/api/v1/auth/login", json={
        "email": "acme.textiles@example.com",
        "password": "AcmeDemoPass1!"
    })
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Chat Session
    session = client.post("/api/v1/chat", headers=headers, json={"title": "Acme Live Evaluation"}).json()
    session_id = session["id"]
    print(f"Created Chat Session: ID {session_id}")

    test_queries = [
        ("What is our current revenue?", "Revenue Inquiry (English)"),
        ("What is our biggest business risk?", "Risk Analysis (English)"),
        ("How can we increase revenue?", "Growth & Strategy (English)"),
        ("Which government schemes are relevant to us?", "Schemes (English)"),
        ("Should we diversify our suppliers?", "Operations (English)"),
        ("ನಮ್ಮ ಪ್ರಸ್ತುತ ಆದಾಯ ಎಷ್ಟು?", "Revenue Inquiry (Kannada)"),
        ("ನಮ್ಮ ದೊಡ್ಡ ವ್ಯವಹಾರ ಅಪಾಯ ಯಾವುದು?", "Risk Analysis (Kannada)"),
        ("Revenue ಎಷ್ಟು ಇದೆ?", "Bilingual Code-mixed (Kanglish)")
    ]

    passes = 0
    for q, desc in test_queries:
        t0 = time.time()
        sub_sess = client.post("/api/v1/chat", headers=headers, json={"title": desc}).json()["id"]
        res = client.post(
            f"/api/v1/chat/{sub_sess}/message",
            headers=headers,
            json={"content": q, "mode": "open"}
        )
        elapsed = round(time.time() - t0, 2)
        if res.status_code == 200:
            passes += 1
            data = res.json()
            content = data.get("assistant_message", {}).get("content", "")
            preview = content[:100].replace("\n", " ")
            print(f"  [PASS] ({elapsed}s) {desc:32} | Query: {q}")
            print(f"         Preview: {preview}...")
        else:
            print(f"  [FAIL] ({elapsed}s) HTTP {res.status_code} | {desc:32} | Query: {q}")

    print(f"\n=======================================================")
    print(f"FINAL RESULT: {passes}/{len(test_queries)} Evaluation Tests PASSED on Live Render!")
    print(f"=======================================================")

if __name__ == "__main__":
    test_chat()
