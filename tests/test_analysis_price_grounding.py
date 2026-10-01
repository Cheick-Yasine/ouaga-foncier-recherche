from app.assistant_service import _ground_analysis_answer


def test_analysis_summary_uses_server_calculated_values():
    answer = (
        "**En résumé**, cette offre de parcelle de 550 m² à Pissy pour 75 millions FCFA "
        "présente un prix de 136 FCFA/m², ce qui est 99.9 % inférieur au prix de repère "
        "de 126 515 FCFA/m² dans le quartier.\n\n"
        "**À comparer dans la liste :**\n\nAnnonce comparable."
    )
    analysis = {
        "resume": (
            "Cette offre est annoncée à 75 000 000 FCFA pour 550 m², soit "
            "136 364 FCFA/m². Son prix au m² est 7.8 % plus élevé que le prix de repère "
            "des offres similaires du quartier. Ce repère est d’environ 126 515 FCFA/m²."
        )
    }

    grounded = _ground_analysis_answer(answer, analysis)

    assert "136 364 FCFA/m²" in grounded
    assert "7.8 % plus élevé" in grounded
    assert "136 FCFA/m²" not in grounded
    assert "99.9 %" not in grounded
    assert "126 515 FCFA/m²" in grounded
    assert "**À comparer dans la liste:**" not in grounded
    assert "Annonce comparable." in grounded
