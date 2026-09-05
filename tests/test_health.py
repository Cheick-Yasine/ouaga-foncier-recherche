"""Tests du socle FastAPI."""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


client = TestClient(app)


def test_root_serves_conversational_interface() -> None:
    from html.parser import HTMLParser
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="assistant-form"' in response.text
    assert 'id="search-form"' not in response.text
    assert 'data-view=' not in response.text
    assert 'id="sidebar-expand"' in response.text
    assert 'id="history-list"' in response.text
    assert 'id="saved-list"' in response.text
    assert 'id="alerts-list"' in response.text
    class Headers(HTMLParser):
        def __init__(self):
            super().__init__(); self.in_th=False; self.columns=[]
        def handle_starttag(self, tag, attrs):
            self.in_th = tag == "th"
        def handle_endtag(self,tag):
            if tag=="th": self.in_th=False
        def handle_data(self,data):
            if self.in_th: self.columns.append(data)
    parser=Headers(); parser.feed(response.text)
    assert parser.columns == ["Rang","Localisation","Superficie","Prix","Prix / m²","Document","Contact","Actions"]
    sidebar=response.text.split('<aside',1)[1].split('</aside>',1)[0]
    assert 'id="saved-list"' not in sidebar
    assert 'id="alerts-list"' not in sidebar
    assert 'HAKIMO' in response.text
    assert 'id="theme-mode"' in response.text
    assert 'Votre recherche, en résumé' not in response.text
    assert 'id="detail-dialog"' not in response.text
    assert 'minlength="4"' in response.text
    assert 'Adresse e-mail' not in response.text


def test_api_information() -> None:
    response = client.get("/api")

    assert response.status_code == 200
    assert response.json()["documentation"] == "/docs"


def test_static_assets_are_available() -> None:
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/hakilab-logo.png").status_code == 200


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_database_health_without_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    response = client.get("/health/database")

    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]
    get_settings.cache_clear()
