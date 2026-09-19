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
    assert 'id="history-toggle"' in response.text
    assert response.text.count('aria-controls="sidebar"') == 1
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
    for identifier in ('nav-home', 'nav-chat', 'open-settings', 'settings-form', 'weekly-count-chart', 'weekly-price-chart', 'weekly-property', 'deal-area-range', 'neighborhood-options'):
        assert f'id="{identifier}"' in response.text
    assert 'Détecter une arnaque' not in response.text
    assert 'Enregistrements' not in response.text
    assert 'Mes alertes' in response.text
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



def test_deal_document_multiselect_is_fully_initialized() -> None:
    script = client.get("/static/discovery.js").text
    assert "const documentOptions=[" in script
    assert "const selectedDocuments=[]" in script
    assert "const documentSearch=$('#deal-document-search')" in script
    assert "selectedDocuments.splice" in script



def test_deal_ranges_follow_visible_midpoint_scales() -> None:
    page = client.get("/").text
    script = client.get("/static/discovery.js").text

    assert 'class="deal-top-field deal-type-field"' in page
    assert 'class="deal-top-field deal-document-field"' in page
    assert '<span>20 M</span>' in page
    assert '<span>750 m²</span>' in page

    assert "minInput.step=maxInput.step='1'" in script
    assert "19_000_000,20_000_000" in script
    assert "Array.from({length:651},(_,index)=>100+index)" in script
    assert "startLabel:'≤ 100 m²'" in script
    assert '<span>100 m² et moins</span>' in page



def test_neighborhood_chart_uses_period_buttons_and_dynamic_fill() -> None:
    script = client.get("/static/discovery.js").text
    assert "['7d','7 j','7 derniers jours']" in script
    assert "['14d','14 j','14 derniers jours']" in script
    assert "['1m','1 m','Dernier mois']" in script
    assert "['1y','1 a','Dernière année']" in script
    assert "['max','Max','Toute la base']" in script
    assert "selectedAggregation==='week' && isSeven" in script
    assert "fill:isolatedNeighborhood ? 'tozeroy' : 'none'" in script
    assert "hexToRgba(color,0.16)" in script
    assert "data.aggregation" not in script



def test_project_chat_has_a_distinct_empty_state_and_no_header_new_button() -> None:
    page = client.get("/").text
    script = client.get("/static/app.js").text

    assert 'id="new-conversation"' not in page
    assert 'id="chat-intro"' in page
    assert 'id="chat-intro-greeting"' in page
    assert "if(n.dataset.page==='chat') startConversation();" in script
    assert "$('#welcome').hidden=chat;" in script
    assert "$('#chat-intro').hidden=!chat || hasMessages;" in script



def test_navigation_uses_query_selector_all_for_page_buttons() -> None:
    script = client.get("/static/app.js").text
    assert script.count("$('.nav-link[data-page]').forEach") == 2



def test_chat_intro_has_no_top_badge_or_kicker() -> None:
    page = client.get("/").text
    assert 'chat-intro-symbol' not in page
    assert 'chat-intro-kicker' not in page
