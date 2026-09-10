import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.public_references import public_announcement_id
from app.sql_assistant import run_sql_assistant
from app.sql_reader import SQLReadError


class Responses:
    def __init__(self, output):
        self.output = iter(output)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self.output)


def tool(name, args, call_id='call1'):
    return SimpleNamespace(output=[SimpleNamespace(type='function_call', name=name,
                           arguments=json.dumps(args), call_id=call_id)], output_text='')


def final(refs, recommendation=None):
    return tool('presenter_selection', {'answer': 'Voici mon conseil.', 'references': refs,
                'recommandee': recommendation, 'description_recherche': 'Parcelle à Saaba', 'mode': 'recherche'})


def row(identifier, price=5000000):
    return {'id': identifier, 'texte_nettoye': 'Parcelle à Saaba, 300 m2, attestation disponible.',
            'quartier_zone': 'Saaba', 'prix_fcfa': price, 'superficie_m2': 300,
            'type_bien_normalise': 'parcelle', 'premiere_collecte': datetime.now(timezone.utc)}


@pytest.mark.anyio
async def test_gpt_writes_sql_and_decides_final_order():
    a, b = public_announcement_id('a'), public_announcement_id('b')
    sql = 'SELECT id FROM annonces ORDER BY prix_fcfa LIMIT 10'
    responses = Responses([tool('consulter_annonces_sql', {'sql': sql}), final([b, a], b)])
    seen = []
    async def execute(statement):
        seen.append(statement)
        return [row('a'), row('b', 8000000)]
    result = await run_sql_assistant('Cherche une parcelle', [], max_age_days=30,
        settings=Settings(assistant_model='gpt-5.6-luna'),
        client=SimpleNamespace(responses=responses), query_executor=execute)
    assert seen == [sql]
    assert [r['id'] for r in result.results] == [b, a]
    assert result.results[0]['recommande_par_gpt'] is True
    assert result.data_used and not result.mcp_used
    assert result.results[0]['prix_fcfa'] == 8000000
    assert all('contact' not in r for r in result.results)
    assert any(isinstance(x, dict) and x.get('type') == 'function_call_output' for x in responses.calls[-1]['input'])


@pytest.mark.anyio
async def test_bad_sql_can_be_corrected_and_unknown_selection_is_rejected():
    ref = public_announcement_id('a')
    responses = Responses([tool('consulter_annonces_sql', {'sql': 'DELETE FROM annonces'}),
        tool('consulter_annonces_sql', {'sql': 'SELECT id FROM annonces'}),
        final(['invente']), final([ref], ref)])
    async def execute(statement):
        if statement.startswith('DELETE'):
            raise SQLReadError('SELECT uniquement')
        return [row('a')]
    result = await run_sql_assistant('Parcelle', [], max_age_days=30,
        settings=Settings(), client=SimpleNamespace(responses=responses), query_executor=execute)
    assert [r['id'] for r in result.results] == [ref]


@pytest.mark.anyio
async def test_greeting_needs_no_database_or_mcp():
    responses = Responses([SimpleNamespace(output=[], output_text='Bonjour !')])
    result = await run_sql_assistant('Bonjour', [], max_age_days=30,
        settings=Settings(), client=SimpleNamespace(responses=responses))
    assert result.answer == 'Bonjour !'
    assert not result.data_used


@pytest.mark.anyio
async def test_database_failure_is_not_reported_as_no_matches():
    responses = Responses([tool('consulter_annonces_sql', {'sql': 'SELECT id FROM annonces'})] + [final([])] * 6)
    async def execute(_):
        raise SQLReadError('Indisponible')
    with pytest.raises(SQLReadError):
        await run_sql_assistant('Parcelle', [], max_age_days=30, settings=Settings(),
            client=SimpleNamespace(responses=responses), query_executor=execute)
