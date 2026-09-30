        comparison_text = "Il n’y a pas assez d’annonces similaires dans ce quartier pour dire si ce prix est bas ou élevé."
    if sufficient and benchmark:
        comparison_text += f" Ce repère est d’environ {benchmark:,.0f} FCFA/m² ; il repose sur les prix demandés par les vendeurs.".replace(',', ' ')
    reasons.extend(quality['atouts'])
    analysis = {
        'verdict':verdict,'comparaison':comparison_text,'raisons':reasons,
        'bien':{'type_bien':subject.property_type,'quartier':subject.neighborhood,'prix_fcfa':subject.price_fcfa,'superficie_m2':subject.area_m2,'prix_m2_fcfa':unit_price,'document':quality['document']},
        'qualite':quality,'nombre_comparables':len(comparables),'mediane_prix_m2':benchmark,
        'ecart_mediane_pct':delta if sufficient else None,
        'portee':'Prix demandés dans les annonces, documents et équipements non vérifiés.',
    }
    strict_zone = 'quartier' in criteria.required_fields or bool(re.search(r'\b(?:(?:uniquement|seulement|exclusivement)\s+(?:a|au|dans)|meme quartier|pas d.autres? quartiers?)\b', normalize_text(preferences)))
    origin = criteria.neighborhood