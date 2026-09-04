"""Tests du moteur de recherche hybride."""

from app.search_engine import (
    SearchCandidate,
    SearchCriteria,
    cosine_similarity,
    numeric_similarity,
    parse_search_description,
    rank_candidates,
    score_candidate,
)


def test_free_description_is_interpreted() -> None:
    criteria = parse_search_description(
        "Je cherche un terrain à Saaba de 300 m², budget maximum 5 millions, avec eau et PUH"
    )
    assert criteria.property_type == "terrain"
    assert criteria.neighborhood == "Saaba"
    assert criteria.area_m2 == 300
    assert criteria.price_fcfa == 5_000_000
    assert criteria.price_is_maximum is True
    assert criteria.viability == "eau"
    assert criteria.document_status == "puh"


def test_cosine_is_normalized() -> None:
    assert cosine_similarity("terrain à Saaba", "terrain à Saaba") == 1
    assert cosine_similarity("terrain à Saaba", "maison à Karpala") < 1
    assert cosine_similarity("", "terrain") == 0


def test_numeric_similarity_penalizes_large_distance() -> None:
    assert numeric_similarity(300, 300) == 1
    assert numeric_similarity(300, 600) == 0.5
    assert numeric_similarity(300, 3_000) == 0.1


def test_maximum_budget_is_a_hard_limit() -> None:
    criteria = SearchCriteria(
        description="parcelle à Saaba",
        price_fcfa=5_000_000,
        price_is_maximum=True,
    )
    candidate = SearchCandidate(
        identifier="expensive",
        text="parcelle à Saaba",
        price_fcfa=5_000_001,
    )
    assert score_candidate(criteria, candidate) is None


def test_missing_optional_value_is_kept_without_free_points() -> None:
    criteria = SearchCriteria(
        description="parcelle à Saaba de 300 m2 à 5 millions",
        price_fcfa=5_000_000,
        area_m2=300,
    )
    complete = SearchCandidate(
        identifier="complete",
        text=criteria.description,
        price_fcfa=5_000_000,
        area_m2=300,
    )
    missing_price = SearchCandidate(
        identifier="missing-price",
        text=criteria.description,
        price_fcfa=None,
        area_m2=300,
    )

    complete_result = score_candidate(criteria, complete)
    partial_result = score_candidate(criteria, missing_price)
    assert complete_result is not None
    assert partial_result is not None
    assert partial_result.score < complete_result.score
    assert partial_result.coverage < complete_result.coverage


def test_missing_required_value_excludes_candidate() -> None:
    criteria = SearchCriteria(
        description="parcelle de 300 m2",
        area_m2=300,
        required_fields=frozenset({"superficie"}),
    )
    candidate = SearchCandidate(
        identifier="missing-area",
        text="belle parcelle",
        area_m2=None,
    )
    assert score_candidate(criteria, candidate) is None


def test_required_neighborhood_rejects_mismatch() -> None:
    criteria = SearchCriteria(
        description="terrain à Saaba",
        neighborhood="Saaba",
        required_fields=frozenset({"quartier"}),
    )
    candidate = SearchCandidate(
        identifier="elsewhere",
        text="terrain à Karpala",
        neighborhood="Karpala",
    )
    assert score_candidate(criteria, candidate) is None


def test_ads_older_than_seven_days_are_excluded() -> None:
    criteria = SearchCriteria(description="terrain", max_age_days=7)
    old = SearchCandidate(
        identifier="old",
        text="terrain",
        age_days=8,
    )
    assert score_candidate(criteria, old) is None


def test_ranking_prefers_balanced_match() -> None:
    criteria = SearchCriteria(
        description="parcelle à Saaba de 300 m2",
        property_type="parcelle",
        neighborhood="Saaba",
        area_m2=300,
    )
    candidates = [
        SearchCandidate(
            identifier="far",
            text="parcelle disponible",
            property_type="parcelle",
            neighborhood="Karpala",
            area_m2=900,
            age_days=1,
        ),
        SearchCandidate(
            identifier="best",
            text="parcelle à Saaba de 300 m2",
            property_type="parcelle",
            neighborhood="Saaba",
            area_m2=300,
            age_days=2,
        ),
    ]
    results = rank_candidates(criteria, candidates)
    assert [result.candidate.identifier for result in results] == ["best", "far"]
    assert results[0].score > results[1].score
    assert "Même quartier ou zone" in results[0].explanations


def test_limit_is_respected() -> None:
    criteria = SearchCriteria(description="terrain")
    candidates = [
        SearchCandidate(identifier=str(index), text="terrain")
        for index in range(5)
    ]
    assert len(rank_candidates(criteria, candidates, limit=2)) == 2


def test_old_ad_is_kept_when_no_date_limit_is_requested() -> None:
    criteria = SearchCriteria(description="terrain")
    old = SearchCandidate(
        identifier="old-but-relevant",
        text="terrain",
        age_days=365,
    )
    assert score_candidate(criteria, old) is not None


def test_budget_without_currency_is_a_maximum() -> None:
    criteria = parse_search_description(
        "Avec un budget de 10 000 000 donne moi les annonces de bon deal"
    )

    assert criteria.price_fcfa == 10_000_000
    assert criteria.price_is_maximum is True


def test_budget_without_currency_excludes_more_expensive_candidate() -> None:
    criteria = parse_search_description("Budget de 10 000 000 pour un bon deal")
    candidate = SearchCandidate(
        identifier="trop-cher",
        text="Parcelle à vendre",
        price_fcfa=380_000_000,
    )

    assert score_candidate(criteria, candidate) is None


def test_good_deal_prioritizes_large_area_within_budget() -> None:
    criteria = parse_search_description(
        "Avec un budget de 10 000 000 donne moi les annonces de bon deal"
    )
    results = rank_candidates(
        criteria,
        [
            SearchCandidate(
                identifier="small",
                text="Terrain à vendre",
                price_fcfa=9_800_000,
                area_m2=300,
            ),
            SearchCandidate(
                identifier="large",
                text="Terrain à vendre",
                price_fcfa=9_000_000,
                area_m2=700,
            ),
            SearchCandidate(
                identifier="over-budget",
                text="Terrain à vendre",
                price_fcfa=11_000_000,
                area_m2=1_000,
            ),
        ],
        limit=10,
    )

    assert [result.candidate.identifier for result in results] == ["large", "small"]
    assert "grande superficie" in results[0].explanations[-1]
