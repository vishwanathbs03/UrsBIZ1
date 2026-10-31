"""Master E2E test suite for all 6 Chat API HTTP endpoints and question matrix."""

import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ["APP_ENV"] = "test"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["DATABASE_URL"] = "sqlite:///" + str(BACKEND / "atlas_ai.db").replace("\\", "/")
os.environ["JWT_SECRET_KEY"] = "test-secret-32-bytes-long-key-12345"

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.utils.database import Base, engine

Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="module")
def auth_context():
    client = TestClient(app)
    ts = str(int(time.time() * 1000))
    email = f"chat_e2e_{ts}@example.com"
    password = "Password123!"

    # 1. Register
    r_reg = client.post("/api/v1/auth/register", json={
        "full_name": "Apex Test Owner",
        "email": email,
        "password": password,
    })
    assert r_reg.status_code == 201
    cookies = r_reg.cookies

    # 2. Create Minimal Business Profile
    r_biz = client.post("/api/v1/business/minimal", json={
        "legal_name": "Apex Manufacturing Ltd",
        "industry": "Manufacturing",
        "established_year": 2018,
        "employee_count": 55,
        "annual_revenue": 24000000.0,
        "revenue_currency": "INR"
    }, cookies=cookies)
    assert r_biz.status_code == 201

    # 3. Create Session
    r_sess = client.post("/api/v1/chat", json={"title": "Master E2E Chat Session"}, cookies=cookies)
    assert r_sess.status_code == 201
    session_id = r_sess.json()["id"]

    return client, cookies, session_id


def test_endpoint_1_get_provider_status(auth_context):
    """GET /api/v1/chat/provider-status returns provider status and modes."""
    client, cookies, _ = auth_context
    res = client.get("/api/v1/chat/provider-status", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert "configured_provider" in data
    assert "runtime_provider" in data
    assert "modes" in data
    assert "grounded" in data["modes"]
    assert "open" in data["modes"]


def test_endpoint_2_create_session(auth_context):
    """POST /api/v1/chat creates a new session."""
    client, cookies, _ = auth_context
    res = client.post("/api/v1/chat", json={"title": "Q&A Session"}, cookies=cookies)
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Q&A Session"
    assert "id" in data
    assert "messages" in data


def test_endpoint_3_list_sessions(auth_context):
    """GET /api/v1/chat lists sessions."""
    client, cookies, _ = auth_context
    res = client.get("/api/v1/chat", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert "sessions" in data
    assert len(data["sessions"]) >= 1


def test_endpoint_4_get_session_detail(auth_context):
    """GET /api/v1/chat/{session_id} gets session detail with messages."""
    client, cookies, session_id = auth_context
    res = client.get(f"/api/v1/chat/{session_id}", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == session_id
    assert data["title"] == "Master E2E Chat Session"


@pytest.mark.parametrize(
    "question,mode",
    [
        ("What is our current revenue?", "grounded"),
        ("What is working capital?", "open"),
        ("What is our biggest business risk?", "grounded"),
        ("How much revenue do we need to reach ₹3 Cr?", "grounded"),
        ("What happens if revenue grows 20%?", "grounded"),
        ("Which government schemes am I eligible for?", "grounded"),
        ("Give me a 12-month roadmap.", "grounded"),
        ("Should we diversify suppliers?", "grounded"),
    ],
)
def test_endpoint_5_message_append_question(auth_context, question, mode):
    """POST /api/v1/chat/{session_id}/message answers each question category."""
    client, cookies, session_id = auth_context
    r = client.post(f"/api/v1/chat/{session_id}/message", json={
        "content": question,
        "mode": mode,
    }, cookies=cookies)
    assert r.status_code == 200, f"Error on question '{question}': {r.text}"
    data = r.json()
    assert "assistant_message" in data
    assert "user_message" in data
    assert "session" in data
    body = data["assistant_message"]["content"]
    assert len(body) > 20
    assert "[object Object]" not in body
    assert "undefined" not in body


def test_endpoint_6_delete_session(auth_context):
    """DELETE /api/v1/chat/{session_id} deletes a session."""
    client, cookies, _ = auth_context
    create_res = client.post("/api/v1/chat", json={"title": "Delete Test"}, cookies=cookies)
    session_id = create_res.json()["id"]

    del_res = client.delete(f"/api/v1/chat/{session_id}", cookies=cookies)
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # Confirm 404
    get_res = client.get(f"/api/v1/chat/{session_id}", cookies=cookies)
    assert get_res.status_code == 404
