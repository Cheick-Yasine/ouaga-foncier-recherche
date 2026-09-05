"""Tests de la route HTTP de conversation."""

from fastapi.testclient import TestClient

from app import assistant_routes
from app.assistant_service import AssistantOutcome
from app.main import app


client = TestClient(app)


def test_assistant_message_returns_answer_and_public_results(monkeypatch) -> None:
    async def fake_run(message, history, *, max_age_days):
        assert message == "Je cherche une parcelle à Saaba"
        assert history[0].content == "Bonjour"
        assert max_age_days == 7
        return AssistantOutcome(
            answer="J’ai trouvé une annonce.",
            results=[{"id": "publique-1", "title": "Parcelle à Saaba"}],
            mcp_used=True,
            model="gpt-4o-mini",
        )

    monkeypatch.setattr(assistant_routes, "run_assistant", fake_run)
    response = client.post(
        "/assistant/message",
        json={
            "message": "Je cherche une parcelle à Saaba",
            "history": [{"role": "assistant", "content": "Bonjour"}],
            "max_age_days": 7,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mcp_used"] is True
    assert payload["results"][0]["id"] == "publique-1"


def test_assistant_rejects_unsupported_period() -> None:
    response = client.post(
        "/assistant/message",
        json={
            "message": "Je cherche une parcelle",
            "max_age_days": 14,
        },
    )
    assert response.status_code == 422
