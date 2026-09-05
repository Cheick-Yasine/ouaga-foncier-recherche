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
async def test_assistant_can_greet_without_calling_mcp() -> None:
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
        settings=Settings(openai_api_key="test", assistant_model="gpt-4o-mini"),
        client=client,
        tool_executor=execute,
    )

    assert outcome.answer == "Bonjour ! Comment puis-je vous aider ?"
    assert outcome.mcp_used is False
    assert outcome.results == []
    assert called is False
    assert client.responses.calls[0]["tool_choice"] == "auto"


@pytest.mark.anyio
async def test_assistant_executes_search_through_mcp_and_returns_results() -> None:
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
        settings=Settings(openai_api_key="test", assistant_model="gpt-4o-mini"),
        client=client,
        tool_executor=execute,
    )

    assert outcome.mcp_used is True
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
