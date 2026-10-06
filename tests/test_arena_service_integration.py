import asyncio
import json
from copy import deepcopy
from uuid import UUID

import httpx
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Game
from app.shots import choose_shot as original_choose_shot
from arena.client import ServiceClient
from arena.match import run_match

VALID_FLEET = [
    {'coordinates': ['A1', 'B1', 'C1', 'D1']},
    {'coordinates': ['F1', 'G1', 'H1']},
    {'coordinates': ['J1', 'J2', 'J3']},
    {'coordinates': ['A4', 'A5']},
    {'coordinates': ['D4', 'E4']},
    {'coordinates': ['H5', 'I5']},
    {'coordinates': ['B8']},
    {'coordinates': ['E8']},
    {'coordinates': ['H8']},
    {'coordinates': ['J10']}
]

def test_arena_and_real_service_continue_after_repeats(monkeypatch):
    session_ids = []
    shot_counts = {}
    current_shot_number = 0

    def choose_shot_with_repeat(own_shots, target_hits):
        if current_shot_number == 2:
            return 'A1'

        return original_choose_shot(own_shots, target_hits)

    monkeypatch.setattr('app.main.generate_fleet', lambda: deepcopy(VALID_FLEET))
    monkeypatch.setattr('app.main.choose_shot', choose_shot_with_repeat)

    async def play(api):
        async def handler(request):
            nonlocal current_shot_number

            path = request.url.path

            if path.endswith('/shot'):
                session_id = path.split('/')[2]

                shot_counts[session_id] = (shot_counts.get(session_id, 0) + 1)
                current_shot_number = shot_counts[session_id]

            options = {}

            if request.content:
                options['json'] = json.loads(request.content)

            response = api.post(path, **options)

            if path == '/game' and response.status_code == 201:
                session_ids.append(UUID(response.json()['session_id']))

            return httpx.Response(
                response.status_code,
                content=response.content,
                headers={
                    'content-type': response.headers.get('content-type', 'application/json')
                }
            )

        async with (
            ServiceClient(
                'http://localhost:8000',
                transport=httpx.MockTransport(handler)
            ) as first,
            ServiceClient(
                'http://localhost:8000',
                transport=httpx.MockTransport(handler)
            ) as second
        ):
            return await run_match(first, second, starting_player=0)

    try:
        with TestClient(app) as api:
            result = asyncio.run(play(api))

        assert len(session_ids) == 2
        assert session_ids[0] != session_ids[1]

        assert result.outcome == 'victory', (result.reason, result.violations)
        assert result.winner in (0, 1)
        assert result.violations == {}
        assert result.close_errors == {}

        repeated_shots = [shot for shot in result.shots if shot['repeated']]

        assert len(repeated_shots) == 2
        assert {shot['player'] for shot in repeated_shots} == {0, 1}

        for shot in repeated_shots:
            assert shot['coordinate'] == 'A1'
            assert shot['expected'] == 'hit'
            assert shot['reported'] == 'hit'

        assert [shot['player'] for shot in result.shots[:4]] == [0, 0, 1, 1]

        with SessionLocal() as db:
            for player, session_id in enumerate(session_ids):
                game = db.get(Game, session_id)

                assert game is not None
                assert game.status == 'closed'
                assert game.pending_shot is None

                own_coordinates = {shot['coordinate'] for shot in result.shots if shot['player'] == player}
                opponent_coordinates = {shot['coordinate'] for shot in result.shots if shot['player'] == 1 - player}

                assert set(game.own_shots) == own_coordinates
                assert set(game.opponent_shots) == opponent_coordinates

    finally:
        with SessionLocal() as db:
            for session_id in session_ids:
                game = db.get(Game, session_id)

                if game is not None:
                    db.delete(game)

            db.commit()