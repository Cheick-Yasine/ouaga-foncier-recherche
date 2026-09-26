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
    assert parser.columns == [
        "Localisation",
        "Date de publication",
        "Texte de publication",
        "Superficie",
        "Prix",
        "Prix / m²",
        "Document",
        "Contact",
        "Actions",
    ]
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
    assert "['3y','3 a','3 dernières années']" in script
    assert "['5y','5 a','5 dernières années']" in script
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



def test_results_table_shows_publication_date_and_text_without_rank() -> None:
    page = client.get("/").text
    script = client.get("/static/app.js").text

    assert "<th scope=\"col\">Rang</th>" not in page
    assert "Date de publication" in page
    assert "Texte de publication" in page
    assert "publicationDateText(r.date_publication)" in script
    assert "publicationTextCell(r)" in script
    assert "result.description" in script



def test_static_assets_are_not_served_from_stale_browser_cache() -> None:
    for path in ("/static/app.js", "/static/styles.css"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store, max-age=0"
        assert response.headers["pragma"] == "no-cache"



def test_contact_refresh_targets_contact_cell_not_a_fixed_column_index() -> None:
    script = client.get("/static/app.js").text
    assert "row.querySelector('.contact-cell')" in script
    assert "row.children[6].replaceWith" not in script
    assert "const documentCell=el('td','document-cell'" in script



def test_market_charts_can_enter_fullscreen() -> None:
    script = client.get("/static/discovery.js").text
    dashboard = client.get("/static/dashboard.css").text

    assert "enableChartFullscreen(" in script
    assert "$('#weekly-count-chart')?.closest('.weekly-card')" in script
    assert "$('#weekly-price-chart')?.closest('.weekly-card')" in script
    assert "enableChartFullscreen(neighborhoodCard" in script
    assert "enableChartFullscreen(rankingCard" in script
    assert "card.requestFullscreen || card.webkitRequestFullscreen" in script
    assert "document.addEventListener('fullscreenchange'" in script
    assert ".chart-fullscreen-card:fullscreen" in dashboard
    assert ".chart-fullscreen-card.is-fullscreen-fallback" in dashboard



def test_price_chart_has_mean_median_and_expert_boxplot_controls() -> None:
    page = client.get("/").text
    script = client.get("/static/discovery.js").text

    assert 'id="price-stat-mean"' in page
    assert 'id="price-stat-median"' in page
    assert 'id="price-expert-toggle"' in page
    assert "priceStatistic==='median' ? 'prix_m2_mediane' : 'prix_m2_moyen'" in script
    assert "type:'box'" in script
    assert "boxmean:true" in script
    assert "prix_m2_values" in script


def test_ranking_chart_has_an_independent_period_control() -> None:
    script = client.get("/static/discovery.js").text

    assert "let rankingTrends=null" in script
    assert "let selectedRankingPeriod='1m'" in script
    assert "button.dataset.rankingPeriod=value" in script
    assert "loadNeighborhoodRanking(true)" in script
    assert "period:selectedRankingPeriod" in script
    assert "aggregation:'week'" in script



def test_expert_boxplots_use_log_scale_and_hide_extreme_points() -> None:
    script = client.get("/static/discovery.js").text
    dashboard = client.get("/static/dashboard.css").text

    assert "boxpoints:false" in script
    assert "type:'log'" in script
    assert "FCFA / m² · échelle logarithmique" in script
    assert "valeurs extrêmes sont masquées" in script
    assert ".ranking-heading" in dashboard
    assert "grid-template-columns:minmax(0,1fr)" in dashboard
    assert ".ranking-period-control" in dashboard
    assert "border-top:1px solid var(--line)" in dashboard



def test_price_expert_toggle_purges_plotly_and_keeps_toggle_delegated() -> None:
    script = client.get("/static/discovery.js").text
    css = client.get("/static/dashboard.css").text

    assert "function clearPlotlyContainer(container)" in script
    assert "Plotly.purge(container)" in script
    assert "function togglePriceExpertMode()" in script
    assert "document.addEventListener('click',event=>" in script
    assert "closest('#price-expert-toggle')" in script
    assert ".chart-fullscreen-card:fullscreen #weekly-price-chart > svg" in css
    assert ".js-plotly-plot .plotly .modebar-btn svg" in css
    assert "max-width:16px !important" in css
