"""Tests du moteur de recherche hybride."""

from app.search_engine import (
    SearchCandidate,
    SearchCriteria,
    cosine_similarity,
    numeric_similarity,
    parse_search_description,
    price_per_square_metre,
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


def test_price_per_square_metre_uses_total_price_and_area() -> None:
    candidate = SearchCandidate(
        identifier="unit-price",
        text="Parcelle de 500 m2 à 8 millions",
        price_fcfa=8_000_000,
        area_m2=500,
    )

    assert price_per_square_metre(candidate) == 16_000


def test_price_per_square_metre_requires_price_and_area() -> None:
    candidate = SearchCandidate(
        identifier="missing-area",
        text="Parcelle à vendre",
        price_fcfa=8_000_000,
        area_m2=None,
    )

    assert price_per_square_metre(candidate) is None


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
    assert "Informations limitées" in results[0].explanations[-1]


def test_near_identical_republication_is_listed_once() -> None:
    criteria = SearchCriteria(description="terrain à Saaba")
    results = rank_candidates(
        criteria,
        [
            SearchCandidate(
                identifier="repost-1",
                text="Belle parcelle à Saaba 300 m2 avec PUH proche de la route contact",
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=5_000_000,
                area_m2=300,
            ),
            SearchCandidate(
                identifier="repost-2",
                text="Belle parcelle à Saaba 300 m2 avec PUH proche de la route contact direct",
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=5_000_000,
                area_m2=300,
            ),
        ],
    )

    assert len(results) == 1


def test_same_characteristics_with_different_text_remain_distinct() -> None:
    criteria = SearchCriteria(description="parcelle")
    results = rank_candidates(
        criteria,
        [
            SearchCandidate(
                identifier="property-1",
                text="Parcelle résidentielle près du marché et de la mairie",
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=5_000_000,
                area_m2=300,
            ),
            SearchCandidate(
                identifier="property-2",
                text="Terrain calme derrière le lycée avec accès à l eau",
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=5_000_000,
                area_m2=300,
            ),
        ],
    )

    assert len(results) == 2


def test_republication_without_neighborhood_is_listed_once() -> None:
    criteria = SearchCriteria(description="bon deal avec un budget de 10 millions")
    results = rank_candidates(
        criteria,
        [
            SearchCandidate(
                identifier="publication-1",
                text=(
                    "Terrain agricole de 100 hectares à 2 250 000 FCFA "
                    "par hectare avec accès à l eau"
                ),
                property_type="terrain",
                neighborhood=None,
                price_fcfa=2_250_000,
                area_m2=10_000,
            ),
            SearchCandidate(
                identifier="publication-2",
                text=(
                    "Terrain agricole de 100 hectares à 2 250 000 FCFA "
                    "par hectare avec accès à l eau disponible"
                ),
                property_type="terrain",
                neighborhood=None,
                price_fcfa=2_250_000,
                area_m2=10_000,
            ),
        ],
    )

    assert len(results) == 1


def test_good_deal_for_requested_area_prefers_lower_price() -> None:
    criteria = parse_search_description(
        "Je veux un bon deal pour une parcelle de 300 m2"
    )
    results = rank_candidates(
        criteria,
        [
            SearchCandidate(
                identifier="cheap-exact",
                text="Parcelle de 300 m2",
                price_fcfa=4_000_000,
                area_m2=300,
            ),
            SearchCandidate(
                identifier="expensive-exact",
                text="Parcelle de 300 m2",
                price_fcfa=8_000_000,
                area_m2=300,
            ),
            SearchCandidate(
                identifier="cheap-far",
                text="Parcelle de 900 m2",
                price_fcfa=3_000_000,
                area_m2=900,
            ),
        ],
    )

    assert results[0].candidate.identifier == "cheap-exact"
    assert "Informations limitées" in results[0].explanations[-1]


def test_requested_neighborhood_precedes_a_better_price() -> None:
    criteria = parse_search_description(
        "Je cherche une parcelle à Saaba de 300 m2 avec un budget de 10 millions"
    )
    results = rank_candidates(
        criteria,
        [
            SearchCandidate(
                identifier="saaba",
                text="Parcelle à Saaba de 300 m2",
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=9_500_000,
                area_m2=300,
            ),
            SearchCandidate(
                identifier="cheaper-elsewhere",
                text="Parcelle de 300 m2 à prix exceptionnel",
                property_type="parcelle",
                neighborhood="Karpala",
                price_fcfa=4_000_000,
                area_m2=300,
            ),
        ],
    )

    assert results[0].candidate.identifier == "saaba"


def test_good_price_prefers_lowest_unit_price_in_requested_neighborhood() -> None:
    criteria = parse_search_description(
        "Je cherche une parcelle à Saaba à bon prix"
    )
    results = rank_candidates(
        criteria,
        [
            SearchCandidate(
                identifier="saaba-low-unit-price",
                text="Parcelle de 600 m2 à Saaba",
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=9_000_000,
                area_m2=600,
            ),
            SearchCandidate(
                identifier="saaba-high-unit-price",
                text="Parcelle de 300 m2 à Saaba",
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=6_000_000,
                area_m2=300,
            ),
            SearchCandidate(
                identifier="outside-cheapest",
                text="Parcelle de 800 m2 à Karpala",
                property_type="parcelle",
                neighborhood="Karpala",
                price_fcfa=4_000_000,
                area_m2=800,
            ),
        ],
    )

    assert results[0].candidate.identifier == "saaba-low-unit-price"
    assert results[1].candidate.identifier == "saaba-high-unit-price"
    assert results[2].candidate.identifier == "outside-cheapest"
    assert all(
        "prix au m² le plus avantageux" not in explanation
        for explanation in results[0].explanations
    )


def test_missing_price_is_excluded_when_budget_is_requested() -> None:
    criteria = parse_search_description(
        "Avec un budget de 10 000 000 donne-moi les annonces de bon deal"
    )
    candidate = SearchCandidate(
        identifier="unknown-price",
        text="Grande parcelle disponible",
        price_fcfa=None,
        area_m2=320_000,
    )

    assert score_candidate(criteria, candidate) is None


def test_good_deal_prefers_prices_near_requested_budget() -> None:
    criteria = parse_search_description(
        "Avec un budget de 10 000 000 donne-moi les annonces de bon deal"
    )
    results = rank_candidates(
        criteria,
        [
            SearchCandidate(
                identifier="cheap",
                text="Terrain de 500 m2",
                price_fcfa=4_000_000,
                area_m2=500,
            ),
            SearchCandidate(
                identifier="expensive",
                text="Terrain de 500 m2",
                price_fcfa=9_500_000,
                area_m2=500,
            ),
        ],
    )

    assert results[0].candidate.identifier == "expensive"
    assert "Informations limitées" in results[0].explanations[-1]


def test_same_dakoure_property_from_different_groups_is_listed_once() -> None:
    criteria = SearchCriteria(description="parcelle à Saaba")
    results = rank_candidates(
        criteria,
        [
            SearchCandidate(
                identifier="dakoure-group-a",
                text=(
                    "Belle opportunité sur le site Dakouré à Saaba. Parcelle "
                    "à proximité de la grande voie rouge, non loin du lycée CGE. "
                    "Prix 11 000 000 FCFA, superficie 300 m2, attestation."
                ),
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=11_000_000,
                area_m2=300,
                contact="72 62 59 31",
            ),
            SearchCandidate(
                identifier="dakoure-group-b",
                text=(
                    "Une parcelle est mise en vente à Saaba sur le site de "
                    "Dakoure, grande voie rouge non loin du lycée CGE de Saaba. "
                    "Superficie 300m2 document attestation prix 11 millions."
                ),
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=11_000_000,
                area_m2=300,
                contact="67 47 48 62; 65 46 61 14",
            ),
        ],
    )

    assert len(results) == 1


def test_same_phone_identifies_shortened_cross_group_repost() -> None:
    criteria = SearchCriteria(description="parcelle à Saaba")
    results = rank_candidates(
        criteria,
        [
            SearchCandidate(
                identifier="mairie-a",
                text=(
                    "Saaba 300 m2 après la nouvelle mairie avec attestation "
                    "guichet unique à 10 millions fixe"
                ),
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=10_000_000,
                area_m2=300,
                contact="+226 56 53 34 15",
            ),
            SearchCandidate(
                identifier="mairie-b",
                text=(
                    "Saaba 300 m2 en vente à 10 millions attestation guichet unique"
                ),
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=10_000_000,
                area_m2=300,
                contact="56 53 34 15",
            ),
        ],
    )

    assert len(results) == 1


def test_exact_requested_area_is_ordered_by_lowest_price() -> None:
    criteria = parse_search_description(
        "Donne-moi les bons deals pour une parcelle de 300 m2"
    )
    results = rank_candidates(
        criteria,
        [
            SearchCandidate(
                identifier="eleven-million",
                text="Parcelle exceptionnelle de 300 m2 à Saaba",
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=11_000_000,
                area_m2=300,
            ),
            SearchCandidate(
                identifier="ten-million",
                text="Parcelle de 300 m2",
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=10_000_000,
                area_m2=300,
            ),
        ],
    )

    assert results[0].candidate.identifier == "ten-million"


def test_plain_amount_after_property_is_interpreted_as_target_price() -> None:
    criteria = parse_search_description(
        "Je cherche un terrain à 1000000"
    )

    assert criteria.price_fcfa == 1_000_000
    assert criteria.price_is_maximum is False


def test_two_hectares_are_converted_to_square_metres() -> None:
    criteria = parse_search_description(
        "Je cherche un terrain de 2 ha"
    )

    assert criteria.area_m2 == 20_000
    assert criteria.price_fcfa is None


def test_good_deal_at_target_price_prefers_largest_area() -> None:
    criteria = parse_search_description(
        "Je cherche un bon deal pour un terrain à 1 000 000"
    )
    results = rank_candidates(
        criteria,
        [
            SearchCandidate(
                identifier="small",
                text="Terrain à 1 000 000",
                property_type="terrain",
                price_fcfa=1_000_000,
                area_m2=300,
            ),
            SearchCandidate(
                identifier="large",
                text="Terrain à 1 000 000",
                property_type="terrain",
                price_fcfa=1_000_000,
                area_m2=800,
            ),
            SearchCandidate(
                identifier="different-price",
                text="Terrain à 900 000",
                property_type="terrain",
                price_fcfa=900_000,
                area_m2=1_000,
            ),
        ],
    )

    assert results[0].candidate.identifier == "large"


def test_requested_area_prefers_low_price_at_same_area() -> None:
    criteria = parse_search_description(
        "Je cherche une parcelle de 800 m2"
    )
    results = rank_candidates(
        criteria,
        [
            SearchCandidate(
                identifier="expensive",
                text="Parcelle de 800 m2",
                property_type="parcelle",
                price_fcfa=12_000_000,
                area_m2=800,
            ),
            SearchCandidate(
                identifier="cheap",
                text="Parcelle de 800 m2",
                property_type="parcelle",
                price_fcfa=5_000_000,
                area_m2=800,
            ),
        ],
    )

    assert results[0].candidate.identifier == "cheap"


def test_school_destination_does_not_satisfy_school_proximity() -> None:
    criteria = parse_search_description(
        "Parcelle avec attestation proche d'une voie bitumée et d'une école"
    )
    candidate = SearchCandidate(
        identifier="school-destination",
        text=(
            "Terrain d'un hectare et quart. Document attestation. "
            "Destination école."
        ),
        property_type="parcelle",
        proximity=None,
        document_status="attestation_non_precisee",
        price_fcfa=100_000_000,
        area_m2=12_500,
    )

    assert score_candidate(criteria, candidate) is None


def test_candidate_must_have_every_requested_proximity() -> None:
    criteria = parse_search_description(
        "Parcelle proche d'une voie bitumée et d'une école"
    )
    road_only = SearchCandidate(
        identifier="road-only",
        text="Parcelle proche d'une voie bitumée",
        property_type="parcelle",
        proximity="voie_bitumee",
    )
    both = SearchCandidate(
        identifier="both",
        text="Parcelle proche d'une voie bitumée et d'une école",
        property_type="parcelle",
        proximity="ecole+voie_bitumee",
    )

    assert score_candidate(criteria, road_only) is None
    assert score_candidate(criteria, both) is not None
