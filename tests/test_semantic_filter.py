"""Tests du filtre OpenAI anonymisé et de son repli local."""

import json
from types import SimpleNamespace

from app.config import Settings
from app.search_engine import SearchCandidate, SearchCriteria, score_candidate
from app.semantic_filter import (
    SemanticDecision,
    SemanticDecisionBatch,
    apply_semantic_filter,
    build_anonymized_payload,
    sanitize_external_text,
)


def _ranked(identifier: str, text: str, score_hint: float = 80):
    criteria = SearchCriteria(description=text)
    result = score_candidate(
        criteria,
        SearchCandidate(
            identifier=identifier,
            text=text,
            url=f"https://facebook.com/{identifier}",
            contact="70 12 34 56",
        ),
    )
    assert result is not None
    return result


def test_sanitizer_removes_contact_email_and_link() -> None:
    cleaned = sanitize_external_text(
        "Contact +226 70 12 34 56, test@example.com, https://facebook.com/post/1"
    )
    assert "70 12 34 56" not in cleaned
    assert "test@example.com" not in cleaned
    assert "facebook.com" not in cleaned
    assert "[contact retire]" in cleaned


def test_payload_never_contains_identifiers_links_or_contacts() -> None:
    criteria = SearchCriteria(
        description="Parcelle à Saaba, écrire à client@example.com",
        neighborhood="Saaba",
    )
    result = _ranked(
        "secret-post-id",
        "Parcelle Saaba. Contact 70 12 34 56 https://facebook.com/private",
    )
    payload, key_map = build_anonymized_payload(
        criteria,
        [result],
        candidate_limit=30,
    )
    rendered = json.dumps(payload, ensure_ascii=False)

    assert list(key_map) == ["c1"]
    assert "secret-post-id" not in rendered
    assert "facebook.com" not in rendered
    assert "70 12 34 56" not in rendered
    assert "client@example.com" not in rendered


class _FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.arguments = None

    def parse(self, **kwargs):
        self.arguments = kwargs
        return SimpleNamespace(output_parsed=self.parsed)


class _FakeClient:
    def __init__(self, parsed):
        self.responses = _FakeResponses(parsed)


def test_llm_filters_and_reorders_candidates() -> None:
    criteria = SearchCriteria(description="parcelle à Saaba")
    first = _ranked("real-1", "parcelle à Saaba")
    second = _ranked("real-2", "parcelle ailleurs")
    client = _FakeClient(
        SemanticDecisionBatch(
            decisions=[
                SemanticDecision(
                    candidate_key="c1",
                    pertinent=False,
                    score_pertinence=20,
                    raison="La demande n'est pas respectée.",
                ),
                SemanticDecision(
                    candidate_key="c2",
                    pertinent=True,
                    score_pertinence=91,
                    raison="Le sens de la demande est respecté.",
                ),
            ]
        )
    )
    settings = Settings(
        openai_api_key="test-key",
        llm_model="gpt-4o-mini",
        llm_relevance_threshold=55,
    )

    outcome = apply_semantic_filter(
        criteria,
        [first, second],
        settings=settings,
        client=client,
    )

    assert outcome.used is True
    assert outcome.fallback is False
    assert outcome.model == "gpt-4o-mini"
    assert [item.candidate.identifier for item in outcome.results] == ["real-2"]
    sent = client.responses.arguments
    assert sent["model"] == "gpt-4o-mini"
    assert sent["text_format"] is SemanticDecisionBatch


def test_missing_key_keeps_local_results_without_external_call() -> None:
    result = _ranked("real-1", "terrain à Karpala")
    outcome = apply_semantic_filter(
        SearchCriteria(description="terrain à Karpala"),
        [result],
        settings=Settings(openai_api_key=None),
    )

    assert outcome.results == [result]
    assert outcome.used is False
    assert outcome.fallback is True


def test_remote_failure_keeps_local_results() -> None:
    class BrokenResponses:
        def parse(self, **_kwargs):
            raise RuntimeError("service unavailable")

    result = _ranked("real-1", "terrain à Karpala")
    client = SimpleNamespace(responses=BrokenResponses())
    outcome = apply_semantic_filter(
        SearchCriteria(description="terrain à Karpala"),
        [result],
        settings=Settings(openai_api_key="test-key"),
        client=client,
    )

    assert outcome.results == [result]
    assert outcome.used is False
    assert outcome.fallback is True


def test_sanitizer_limits_default_announcement_length() -> None:
    cleaned = sanitize_external_text("a" * 1_200)

    assert len(cleaned) == 900



def test_sanitization_keeps_explicit_amounts_and_masks_phones():
    from app.semantic_filter import sanitize_external_text
    text='Budget maximum 12 000 000 FCFA. Contact 70 12 34 56, tél. 70123456.'
    safe=sanitize_external_text(text)
    assert '12 000 000 FCFA' in safe
    assert '70 12 34 56' not in safe
    assert '70123456' not in safe
    assert sanitize_external_text('prix_fcfa: 12000000') == 'prix_fcfa: 12000000'
    assert sanitize_external_text('id: a123456789abcdef') == 'id: a123456789abcdef'



def test_semantic_filter_preserves_completeness_before_price():
    from app.search_engine import parse_search_description
    criteria=parse_search_description('Bonne affaire parcelle à Saaba de 300 m² budget maximum 6 millions')
    bare=score_candidate(criteria,SearchCandidate(identifier='bare',text='Parcelle à Saaba avec PUH mentionné.',property_type='parcelle',neighborhood='Saaba',price_fcfa=100_000,area_m2=300))
    complete=score_candidate(criteria,SearchCandidate(identifier='complete',text='PUH disponible. Eau et électricité disponibles. Proche du goudron.',property_type='parcelle',neighborhood='Saaba',price_fcfa=6_000_000,area_m2=300))
    client=_FakeClient(SemanticDecisionBatch(decisions=[
        SemanticDecision(candidate_key='c1',pertinent=True,score_pertinence=100,raison='Petit prix.'),
        SemanticDecision(candidate_key='c2',pertinent=True,score_pertinence=70,raison='Annonce complète.'),
    ]))
    outcome=apply_semantic_filter(criteria,[bare,complete],settings=Settings(openai_api_key='test-key',llm_relevance_threshold=55),client=client)
    assert outcome.used is True
    assert outcome.fallback is False
    assert [item.candidate.identifier for item in outcome.results]==['complete','bare']
