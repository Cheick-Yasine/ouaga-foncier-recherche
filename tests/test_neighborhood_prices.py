from app.neighborhood_prices import (
    calculate_neighborhood_medians,
    load_neighborhood_catalog,
)


def test_all_property_types_share_one_neighborhood_median_and_aliases_merge():
    catalog = [
        {"name": "Saaba", "key": "saaba"},
        {"name": "Boassa", "key": "boassa"},
    ]
    rows = [
        {"id": "1", "url": "u1", "type_bien_normalise": "terrain", "quartier_zone": "Saaba", "prix_fcfa": 1_000_000, "superficie_m2": 100, "texte_nettoye": "Terrain en vente à Saaba"},
        {"id": "2", "url": "u2", "type_bien_normalise": "maison", "quartier_zone": "SAABA", "prix_fcfa": 4_000_000, "superficie_m2": 200, "texte_nettoye": "Maison en vente à Saaba"},
        {"id": "3", "url": "u3", "type_bien_normalise": "parcelle", "quartier_zone": "Saaba", "prix_fcfa": 9_000_000, "superficie_m2": 100, "texte_nettoye": "Parcelle en vente à Saaba"},
        {"id": "4", "url": "u3", "type_bien_normalise": "parcelle", "quartier_zone": "Saaba", "prix_fcfa": 99_000_000, "superficie_m2": 100, "texte_nettoye": "Parcelle en vente à Saaba"},
        {"id": "5", "url": "u5", "type_bien_normalise": "terrain", "quartier_zone": "boassa", "prix_fcfa": 2_000_000, "superficie_m2": 100, "texte_nettoye": "Terrain en vente à Boassa"},
    ]

    result = calculate_neighborhood_medians(rows, catalog)

    assert result[0]["median_price_m2"] == 20_000
    assert result[0]["listing_count"] == 3
    assert result[1]["median_price_m2"] == 20_000
    assert result[1]["listing_count"] == 1


def test_invalid_or_excluded_announcements_do_not_affect_the_median():
    catalog = [{"name": "Saaba", "key": "saaba"}]
    rows = [
        {"id": "valid", "url": "valid", "type_bien": "parcelle", "quartier_zone": "Saaba", "prix_fcfa": 3_000_000, "superficie_m2": 150, "texte_nettoye": "Parcelle en vente à Saaba"},
        {"id": "rent", "url": "rent", "type_bien": "parcelle", "quartier_zone": "Saaba", "prix_fcfa": 1_000_000, "superficie_m2": 100, "texte_nettoye": "Parcelle en location à Saaba"},
        {"id": "unserviced", "url": "unserviced", "type_bien": "terrain", "quartier_zone": "Saaba", "prix_fcfa": 1_000_000, "superficie_m2": 100, "texte_nettoye": "Terrain non loti en vente à Saaba"},
        {"id": "villa", "url": "villa", "type_bien_normalise": "villa", "quartier_zone": "Saaba", "prix_fcfa": 1_000_000, "superficie_m2": 100, "texte_nettoye": "Villa en vente à Saaba"},
        {"id": "trash", "url": "trash", "type_bien": "maison", "quartier_zone": "Saaba", "prix_fcfa": 1_000_000, "superficie_m2": 100, "texte_nettoye": "Maison en vente à Saaba", "is_trashed": True},
        {"id": "outside", "url": "outside", "type_bien": "terrain", "quartier_zone": "Bobo-Dioulasso", "prix_fcfa": 1_000_000, "superficie_m2": 100, "texte_nettoye": "Terrain en vente à Bobo-Dioulasso"},
        {"id": "no-area", "url": "no-area", "type_bien": "terrain", "quartier_zone": "Saaba", "prix_fcfa": 1_000_000, "superficie_m2": 0, "texte_nettoye": "Terrain en vente à Saaba"},
        {"id": "no-price", "url": "no-price", "type_bien": "terrain", "quartier_zone": "Saaba", "prix_fcfa": None, "superficie_m2": 100, "texte_nettoye": "Terrain en vente à Saaba"},
    ]

    result = calculate_neighborhood_medians(rows, catalog)

    assert result == [
        {
            "neighborhood_key": "saaba",
            "neighborhood_name": "Saaba",
            "median_price_m2": 20_000,
            "listing_count": 1,
        }
    ]


def test_catalog_contains_all_201_neighborhoods_including_unlocated_ones():
    catalog = load_neighborhood_catalog()

    assert len(catalog) == 201
    assert all("name" in item and "key" in item for item in catalog)
