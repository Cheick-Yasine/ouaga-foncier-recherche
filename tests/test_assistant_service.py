"""Tests du cerveau conversationnel et de son appel MCP."""

import json
from types import SimpleNamespace

import pytest

from app.assistant_service import (
    AssistantNotConfiguredError,
    ChatMessage,
    run_assistant,
)
from app.config import Settings


class FakeResponses:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self._responses)


class FakeClient:
    def __init__(self, responses):
        self.responses = FakeResponses(responses)


def text_response(text):
    return SimpleNamespace(output=[], output_text=text)


def tool_response(arguments):
    return SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                name="rechercher_annonces",
                arguments=json.dumps(arguments),
                call_id="call-1",
            )
        ],
        output_text="",
    )


@pytest.mark.anyio
@pytest.mark.parametrize("model", ["gpt-4o-mini", "gpt-5.6-luna"])
async def test_assistant_can_greet_without_calling_mcp(model) -> None:
    client = FakeClient([text_response("Bonjour ! Comment puis-je vous aider ?")])
    called = False

    async def execute(_name, _arguments):
        nonlocal called
        called = True
        return {}

    outcome = await run_assistant(
        "Bonjour",
        [],
        max_age_days=30,
        settings=Settings(openai_api_key="test", assistant_model=model),
        client=client,
        tool_executor=execute,
    )

    assert outcome.answer == "Bonjour ! Comment puis-je vous aider ?"
    assert outcome.mcp_used is False
    assert outcome.results == []
    assert called is False
    assert client.responses.calls[0]["tool_choice"] == "auto"


@pytest.mark.anyio
@pytest.mark.parametrize("model", ["gpt-4o-mini", "gpt-5.6-luna"])
async def test_assistant_executes_search_through_mcp_and_returns_results(model) -> None:
    client = FakeClient(
        [
            tool_response(
                {
                    "description": "Parcelle à Saaba, budget maximum 6 millions",
                    "criteres_obligatoires": ["quartier", "prix"],
                }
            ),
            text_response("J’ai trouvé une parcelle adaptée à Saaba."),
        ]
    )
    received = {}
    result = {
        "id": "annonce-publique",
        "title": "Parcelle à Saaba",
        "prix_fcfa": 5_500_000,
        "score": 91,
        "url": "https://example.test/annonce",
        "contact": "70 12 34 56",
    }

    async def execute(name, arguments):
        received["name"] = name
        received["arguments"] = arguments
        return {"results": [result]}

    outcome = await run_assistant(
        "Je cherche à Saaba",
        [ChatMessage("user", "Mon budget maximum est de 6 millions")],
        max_age_days=7,
        settings=Settings(openai_api_key="test", assistant_model=model),
        client=client,
        tool_executor=execute,
    )

    for request in client.responses.calls:
        assert request["model"] == model
        assert request.get("reasoning") == ({"effort": "none"} if model == "gpt-5.6-luna" else None)
    assert outcome.mcp_used is True
    assert outcome.answer == "J’ai trouvé une parcelle adaptée à Saaba."
    assert outcome.results == [result]
    assert received["name"] == "rechercher_annonces"
    assert received["arguments"]["anciennete_jours"] == 7
    assert received["arguments"]["utiliser_filtre_llm"] is False
    assert received["arguments"]["limit"] == 10
    assert client.responses.calls[0]["tool_choice"] == "required"
    assert client.responses.calls[1]["tool_choice"] == "none"
    second_input = client.responses.calls[1]["input"]
    outputs = [item for item in second_input if isinstance(item, dict)]
    assert any(item.get("type") == "function_call_output" for item in outputs)
    serialized_output = next(
        item["output"]
        for item in outputs
        if item.get("type") == "function_call_output"
    )
    assert "example.test" not in serialized_output
    assert "70 12 34 56" not in serialized_output


@pytest.mark.anyio
async def test_assistant_requires_key_without_injected_client() -> None:
    with pytest.raises(AssistantNotConfiguredError):
        await run_assistant(
            "Je cherche un terrain",
            [],
            max_age_days=30,
            settings=Settings(openai_api_key=None),
        )


@pytest.mark.anyio
async def test_conversation_sent_to_llm_is_anonymized() -> None:
    client = FakeClient([text_response("Quel quartier préférez-vous ?")])

    async def execute(_name, _arguments):
        return {}

    await run_assistant(
        "Appelez-moi au 70 12 34 56",
        [ChatMessage("user", "Mon e-mail est test@example.com")],
        max_age_days=30,
        settings=Settings(openai_api_key="test"),
        client=client,
        tool_executor=execute,
    )

    rendered = json.dumps(client.responses.calls[0]["input"])
    assert "70 12 34 56" not in rendered
    assert "test@example.com" not in rendered
    assert "[contact retire]" in rendered
    assert "[email retire]" in rendered


@pytest.mark.anyio
async def test_multiple_calls_in_one_response_execute_only_one_search():
    first=tool_response({'description':'Bonne affaire parcelle à Saaba','criteres_obligatoires':[]})
    second=tool_response({'description':'Autre recherche','criteres_obligatoires':[]})
    second.output[0].call_id='call-2'
    first.output.extend(second.output)
    client=FakeClient([first,text_response('Voici les offres retenues.')])
    calls=[]
    async def execute(name,arguments):
        calls.append((name,arguments))
        return {'criteres':{'quartier':'Saaba'},'results':[]}
    outcome=await run_assistant('Une bonne affaire à Saaba',[],max_age_days=30,client=client,tool_executor=execute,settings=Settings(openai_api_key='test'))
    assert len(calls)==1
    assert outcome.criteria['quartier']=='Saaba'
    assert client.responses.calls[1]['tool_choice']=='none'


@pytest.mark.anyio
async def test_copied_offer_uses_evaluation_and_returns_analysis():
    response=tool_response({'publication':'Parcelle à Saaba 300 m² pour 8 millions','description':'Budget maximum 6 millions','criteres_obligatoires':[]})
    response.output[0].name='evaluer_annonce'
    client=FakeClient([response,text_response('Le prix est élevé par rapport aux annonces comparables.')])
    calls=[]
    async def execute(name,arguments):
        calls.append((name,arguments))
        return {'criteres':{'quartier':'Saaba','prix_fcfa':6_000_000},'analyse':{'verdict':'Prix élevé'},'results':[{'id':'public-1'}]}
    outcome=await run_assistant('Est-ce une bonne affaire ? Parcelle à Saaba 300 m² pour 8 millions',[],max_age_days=7,client=client,tool_executor=execute,settings=Settings(openai_api_key='test'))
    assert calls[0][0]=='evaluer_annonce'
    assert calls[0][1]['anciennete_jours']==7
    assert outcome.analysis['verdict']=='Prix élevé'
    assert outcome.criteria['prix_fcfa']==6_000_000
    assert outcome.results[0]['id']=='public-1'


@pytest.mark.anyio
async def test_mcp_error_is_not_returned_as_successful_empty_search():
    from app.assistant_service import MCPAssistantError
    client=FakeClient([tool_response({'description':'Parcelle à Saaba','criteres_obligatoires':[]})])
    async def execute(name,arguments):
        return {'erreur':'Base temporairement indisponible'}
    with pytest.raises(MCPAssistantError,match='Base temporairement indisponible'):
        await run_assistant('Parcelle à Saaba',[],max_age_days=30,client=client,tool_executor=execute,settings=Settings(openai_api_key='test'))


@pytest.mark.anyio
async def test_evaluation_uses_original_amount_instead_of_llm_rewritten_price():
    response=tool_response({'publication':'Parcelle à Roumtenga 300 m² prix 3 500 FCFA','description':'Budget maximum 6 millions','criteres_obligatoires':[]})
    response.output[0].name='evaluer_annonce'
    client=FakeClient([response,text_response('Analyse de votre annonce.')])
    received={}
    async def execute(name,arguments):
        received.update(arguments)
        return {'analyse':{},'results':[]}
    original='Parcelle à ROUMTENGA (Songdin), 300 m², prix 3 500 000 FCFA. Contact 70 12 34 56'
    await run_assistant('Mon budget est de 6 millions. Voici l’annonce : '+original,[],max_age_days=30,client=client,tool_executor=execute,settings=Settings(openai_api_key='test'))
    assert '3 500 000 FCFA' in received['publication']
    assert '6 millions' not in received['publication']
    assert '70 12 34 56' not in received['publication']


def test_comparison_suggestion_chooses_same_neighborhood_ranks():
    from app.assistant_service import _suggestions
    results=[{'id':'a','quartier':'Saaba','type_bien':'parcelle'}, {'id':'b','quartier':'Karpala','type_bien':'parcelle'}, {'id':'c','quartier':'Saaba','type_bien':'parcelle'}]
    suggestions=_suggestions(results,{})
    comparison=next(s for s in suggestions if s['label'].startswith('Comparer'))
    assert 'rang 1 et 3' in comparison['message']


@pytest.mark.anyio
async def test_search_budget_is_kept_before_mcp_and_before_the_advisory_reply():
    from app.search_engine import parse_search_description
    client=FakeClient([
        tool_response({'description':'Une bonne affaire avec un budget de 20 millions','criteres_obligatoires':[]}),
        text_response('Je privilégierais les documents disponibles et un accès à l’eau. Cette offre respecte votre budget et mérite une visite.'),
    ])
    received={}
    async def execute(name,arguments):
        received.update(arguments)
        return {'criteres':{'prix_fcfa':20_000_000},'results':[{'id':'too-expensive','prix_fcfa':20_000_000},{'id':'within-budget','prix_fcfa':9_000_000}]}
    outcome=await run_assistant('Je cherche une parcelle, budget maximum 10 millions FCFA',[],max_age_days=30,client=client,tool_executor=execute,settings=Settings(openai_api_key='test'))
    assert parse_search_description(received['description']).price_fcfa==10_000_000
    assert outcome.criteria['prix_fcfa']==10_000_000
    assert [r['id'] for r in outcome.results]==['within-budget']
    assert outcome.answer.startswith('Je privilégierais')
    tool_output=next(item['output'] for item in client.responses.calls[1]['input'] if isinstance(item,dict) and item.get('type')=='function_call_output')
    assert [r['id'] for r in json.loads(tool_output)['results']]==['within-budget']



@pytest.mark.anyio
async def test_guided_deal_form_keeps_ranges_and_multiple_zones():
    message = (
        "Trouve-moi une bonne affaire : parcelle en vente. "
        "Zones souhaitées : Saaba, Karpala. Uniquement dans ces zones. "
        "Prix entre 5000000 et 25000000 FCFA. "
        "Superficie entre 300 et 600 m². "
        "Document souhaité : PUH."
    )
    client = FakeClient([
        tool_response({
            "description": "Parcelle à Ouagadougou avec PUH",
            "criteres_obligatoires": [],
        }),
        text_response("Voici les offres."),
    ])
    received = {}

    async def execute(name, arguments):
        received["name"] = name
        received["arguments"] = arguments
        return {"criteres": {}, "results": []}

    await run_assistant(
        message,
        [],
        max_age_days=30,
        client=client,
        tool_executor=execute,
        settings=Settings(openai_api_key="test"),
    )

    from app.search_engine import parse_search_description

    parsed = parse_search_description(received["arguments"]["description"])
    assert parsed.neighborhoods == ("Saaba", "Karpala")
    assert parsed.neighborhoods_strict is True
    assert parsed.price_min_fcfa == 5_000_000
    assert parsed.price_max_fcfa == 25_000_000
    assert parsed.area_min_m2 == 300
    assert parsed.area_max_m2 == 600
    assert parsed.document_status == "puh"

@pytest.mark.anyio
async def test_target_price_reply_uses_real_result_price_instead_of_hallucinating():
    client = FakeClient([
        tool_response({
            "description": "Parcelle à Balkuy à 2 millions FCFA",
            "criteres_obligatoires": ["quartier", "prix"],
        }),
        text_response(
            "Parcelle à Balkuy : Prix 2 millions FCFA, superficie 250 m²."
        ),
    ])

    async def execute(name, arguments):
        return {
            "criteres": {"quartier": "Balkuy", "prix_fcfa": 2_000_000},
            "results": [{
                "id": "balkuy-8m",
                "quartier": "Balkuy",
                "type_bien": "parcelle",
                "prix_fcfa": 8_000_000,
                "superficie_m2": 250,
            }],
        }

    outcome = await run_assistant(
        "Donne-moi le lien de la parcelle à Balkuy qui coûte 2 millions",
        [],
        max_age_days=90,
        client=client,
        tool_executor=execute,
        settings=Settings(openai_api_key="test"),
    )

    assert "exactement à 2 000 000 FCFA" in outcome.answer
    assert "8 000 000 FCFA" in outcome.answer
    assert "bouton « Voir »" in outcome.answer
    assert outcome.results[0]["prix_fcfa"] == 8_000_000


@pytest.mark.anyio
async def test_natural_price_range_never_returns_offer_outside_range():
    client = FakeClient([
        tool_response({
            "description": "Parcelle à Balkuy",
            "criteres_obligatoires": ["quartier", "prix"],
        }),
        text_response(
            "Il y a quelques parcelles entre 1 et 2 millions."
        ),
    ])
    received = {}

    async def execute(name, arguments):
        received.update(arguments)
        return {
            "criteres": {"quartier": "Balkuy"},
            "results": [{
                "id": "balkuy-8m",
                "quartier": "Balkuy",
                "type_bien": "parcelle",
                "prix_fcfa": 8_000_000,
                "superficie_m2": 250,
            }],
        }

    outcome = await run_assistant(
        "Mais y'en a-t-il qui sont entre 1 et 2millions ?",
        [ChatMessage("user", "Je cherche une parcelle à Balkuy")],
        max_age_days=90,
        client=client,
        tool_executor=execute,
        settings=Settings(openai_api_key="test"),
    )

    from app.search_engine import parse_search_description

    parsed = parse_search_description(received["description"])
    assert parsed.price_min_fcfa == 1_000_000
    assert parsed.price_max_fcfa == 2_000_000
    assert outcome.results == []
    assert "aucune annonce entre 1 000 000 FCFA et 2 000 000 FCFA" in outcome.answer




@pytest.mark.anyio
async def test_price_range_keeps_conversational_advice_when_results_are_valid():
    client = FakeClient([
        tool_response({
            "description": "Parcelle à Boassa et Tengandogo entre 4 et 20 millions",
            "criteres_obligatoires": ["prix"],
        }),
        text_response(
            "Je regarderais d'abord l'offre la mieux documentée, même si elle n'est "
            "pas la moins chère. Dans cette sélection, le vrai point faible est "
            "l'absence de document précisé sur plusieurs annonces. Je vérifierais "
            "donc le document avant de comparer seulement les prix."
        ),
    ])

    async def execute(name, arguments):
        return {
            "criteres": {
                "quartiers": ["Boassa", "Tengandogo"],
                "prix_min_fcfa": 4_000_000,
                "prix_max_fcfa": 20_000_000,
            },
            "results": [
                {
                    "id": "boassa-1",
                    "quartier": "Boassa",
                    "type_bien": "parcelle",
                    "prix_fcfa": 12_000_000,
                    "superficie_m2": 300,
                    "document": "non_precise",
                },
                {
                    "id": "tengandogo-1",
                    "quartier": "Tengandogo",
                    "type_bien": "parcelle",
                    "prix_fcfa": 10_000_000,
                    "superficie_m2": 300,
                    "document": "puh",
                },
            ],
        }

    outcome = await run_assistant(
        "Trouve-moi une bonne affaire : parcelle en vente. "
        "Zones souhaitées : Boassa, Tengandogo. "
        "Prix entre 4000000 et 20000000 FCFA.",
        [],
        max_age_days=30,
        client=client,
        tool_executor=execute,
        settings=Settings(openai_api_key="test"),
    )

    assert "Je regarderais d'abord" in outcome.answer
    assert "le vrai point faible" in outcome.answer
    assert "J’ai trouvé 2 offres dans cette fourchette" not in outcome.answer
    assert [row["quartier"] for row in outcome.results] == [
        "Boassa",
        "Tengandogo",
    ]



@pytest.mark.anyio
async def test_new_self_contained_question_is_marked_as_independent_context():
    client = FakeClient([
        tool_response({
            "description": "Maison à Karpala",
            "criteres_obligatoires": ["quartier", "type_bien"],
        }),
        text_response("Je regarderais les offres disponibles à Karpala."),
    ])
    received = {}

    async def execute(name, arguments):
        received.update(arguments)
        return {"criteres": {"quartier": "Karpala"}, "results": []}

    await run_assistant(
        "Je cherche une maison à Karpala",
        [
            ChatMessage(
                "user",
                "Je cherche une parcelle à Saaba avec un budget maximum de 6 millions.",
            )
        ],
        max_age_days=30,
        client=client,
        tool_executor=execute,
        settings=Settings(openai_api_key="test"),
    )

    assert "nouvelle demande autonome" in client.responses.calls[0]["instructions"]
    assert "6 millions" not in received["description"]
    assert "Saaba" not in received["description"]


@pytest.mark.anyio
async def test_short_followup_is_marked_as_continuation_context():
    client = FakeClient([
        tool_response({
            "description": "Parcelle à Saaba avec PUH",
            "criteres_obligatoires": ["quartier", "prix", "statut_document"],
        }),
        text_response("Je privilégierais les offres avec PUH."),
    ])

    async def execute(name, arguments):
        return {"criteres": {}, "results": []}

    await run_assistant(
        "Et avec un PUH ?",
        [
            ChatMessage(
                "user",
                "Je cherche une parcelle à Saaba avec un budget maximum de 6 millions.",
            )
        ],
        max_age_days=30,
        client=client,
        tool_executor=execute,
        settings=Settings(openai_api_key="test"),
    )

    assert "il s'agit d'une continuation" in client.responses.calls[0]["instructions"]


@pytest.mark.anyio
async def test_new_neighborhood_question_does_not_reinject_previous_budget_or_area():
    client = FakeClient([
        tool_response({
            "description": "Parcelle à Gounghin",
            "criteres_obligatoires": ["quartier", "type_bien"],
        }),
        text_response("Je vais vérifier les parcelles disponibles à Gounghin."),
    ])
    received = {}

    async def execute(name, arguments):
        received.update(arguments)
        return {
            "criteres": {"quartier": "Gounghin"},
            "results": [],
        }

    await run_assistant(
        "Et une parcelle à Gounghin est-elle disponible ?",
        [
            ChatMessage(
                "user",
                "Trouve-moi une bonne affaire : parcelle en vente. "
                "Zones souhaitées : Boassa, Dassasgho, Ouaga 2000. "
                "Prix entre 5000000 et 20000000 FCFA. "
                "Superficie entre 1 et 528 m².",
            )
        ],
        max_age_days=30,
        client=client,
        tool_executor=execute,
        settings=Settings(openai_api_key="test"),
    )

    assert "nouvelle demande autonome" in client.responses.calls[0]["instructions"]
    assert "Boassa" not in received["description"]
    assert "Dassasgho" not in received["description"]
    assert "Ouaga 2000" not in received["description"]
    assert "5000000" not in received["description"]
    assert "528" not in received["description"]
    assert "Gounghin" in received["description"]


@pytest.mark.anyio
async def test_same_neighborhood_modifier_still_inherits_previous_budget():
    client = FakeClient([
        tool_response({
            "description": "Parcelle à Saaba avec école",
            "criteres_obligatoires": ["quartier", "proximite"],
        }),
        text_response("Je vérifierais les annonces avec une école à Saaba."),
    ])

    received = {}

    async def execute(name, arguments):
        received.update(arguments)
        return {"criteres": {}, "results": []}

    await run_assistant(
        "Et avec une école à Saaba ?",
        [
            ChatMessage(
                "user",
                "Je cherche une parcelle à Saaba, budget maximum 6 millions.",
            )
        ],
        max_age_days=30,
        client=client,
        tool_executor=execute,
        settings=Settings(openai_api_key="test"),
    )

    assert "il s'agit d'une continuation" in client.responses.calls[0]["instructions"]
    from app.search_engine import parse_search_description
    assert parse_search_description(received["description"]).price_fcfa == 6_000_000
