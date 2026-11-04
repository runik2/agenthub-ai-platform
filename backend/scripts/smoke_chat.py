"""End-to-end smoke check against a running backend.

Usage: .venv/Scripts/python.exe scripts/smoke_chat.py [base_url]
Logs in with the bootstrap administrator, picks the first active agent and
sends one real message to its provider (Ollama by default), then prints usage.
"""

from __future__ import annotations

import os
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@agenthub.local")
PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "admin12345")


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=180.0) as client:
        live = client.get("/health/live")
        print(f"health/live -> {live.status_code} {live.json()}")

        status = client.get("/api/v1/auth/setup-status").json()
        if status.get("needs_setup"):
            print("database has no users; open the UI and complete setup first")
            return 2

        login = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"login -> ok as {login.json()['user']['email']}")

        agents = client.get("/api/v1/agents", headers=headers).json()
        print(f"agents -> {agents['total']} total")
        active = [item for item in agents["items"] if item["status"] == "active"]
        if not active:
            print("no active agent to talk to")
            return 3
        agent = active[0]
        print(f"using agent: {agent['name']} model={agent['model_name']}")

        providers = client.get("/api/v1/providers", headers=headers).json()
        for provider in providers["items"]:
            print(
                f"provider: {provider['name']} kind={provider['kind']} "
                f"status={provider['last_check_status']}"
            )

        conversation = client.post(
            "/api/v1/conversations", headers=headers, json={"agent_id": agent["id"]}
        )
        conversation.raise_for_status()
        conversation_id = conversation.json()["id"]
        print(f"conversation created: {conversation_id}")

        reply = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "In one sentence: what can you help me with?"},
        )
        print(f"chat -> {reply.status_code}")
        if reply.status_code != 200:
            print(reply.text[:500])
            return 4
        payload = reply.json()
        print("answer:", payload["assistant_message"]["content"][:300].replace("\n", " "))
        print("usage:", payload["usage"])

        overview = client.get("/api/v1/analytics/overview?days=30", headers=headers).json()
        print("analytics totals:", overview["totals"])
        if payload["usage"]["total_tokens"] <= 0:
            print("FAIL: usage was not recorded")
            return 5
        print("OK: chat answered and usage recorded")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
