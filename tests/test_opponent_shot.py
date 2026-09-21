from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Game

client = TestClient(app)

TEST_FLEET = [
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

@pytest.fixture
def create_game():
    session_ids = []

    def _create_game():
        response = client.post('/game')

        assert response.status_code == 201

        session_id = UUID(response.json()['session_id'])

        with SessionLocal() as db:
            game = db.get(Game, session_id)

            assert game is not None

            game.ships = deepcopy(TEST_FLEET)
            game.opponent_shots = {}
            game.turn = 'unknown'

            db.commit()

        session_ids.append(session_id)

        return session_id

    yield _create_game

    with SessionLocal() as db:
        for session_id in session_ids:
            game = db.get(Game, session_id)

            if game is not None:
                db.delete(game)

        db.commit()

def test_opponent_shot_miss(create_game):
    session_id = create_game()

    response = client.post(f'/game/{session_id}/opponent-shot', json={'coordinate': 'C10'})

    assert response.status_code == 200
    assert response.json() == {'result': 'miss'}

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.opponent_shots == {'C10': 'miss'}
        assert game.turn == 'ours'

def test_opponent_shot_hit(create_game):
    session_id = create_game()

    response = client.post(f'/game/{session_id}/opponent-shot', json={'coordinate': 'A1'})

    assert response.status_code == 200
    assert response.json() == {'result': 'hit'}

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.opponent_shots == {'A1': 'hit'}
        assert game.turn == 'opponent'

def test_opponent_shot_killed_on_last_deck(create_game):
    session_id = create_game()

    coordinates = ['A1', 'B1', 'C1', 'D1']
    results = []

    for coordinate in coordinates:
        response = client.post(f'/game/{session_id}/opponent-shot', json={'coordinate': coordinate})

        assert response.status_code == 200

        results.append(response.json()['result'])

    assert results == ['hit', 'hit', 'hit', 'killed']

def test_single_deck_ship_is_killed(create_game):
    session_id = create_game()

    response = client.post(f'/game/{session_id}/opponent-shot', json={'coordinate': 'B8'})

    assert response.status_code == 200
    assert response.json() == {'result': 'killed'}

def test_repeated_opponent_shot_returns_same_result(create_game):
    session_id = create_game()

    first_response = client.post(f'/game/{session_id}/opponent-shot', json={'coordinate': 'A1'})

    second_response = client.post(f'/game/{session_id}/opponent-shot', json={'coordinate': 'A1'})

    assert first_response.json() == {'result': 'hit'}
    assert second_response.json() == {'result': 'hit'}

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.opponent_shots == {'A1': 'hit'}

def test_invalid_opponent_coordinate_returns_400(create_game):
    session_id = create_game()

    response = client.post(f'/game/{session_id}/opponent-shot', json={'coordinate': 'K1'})

    assert response.status_code == 400
    assert 'detail' in response.json()

def test_missing_coordinate_returns_400(create_game):
    session_id = create_game()

    response = client.post(f'/game/{session_id}/opponent-shot', json = {})

    assert response.status_code == 400
    assert 'detail' in response.json()

def test_unknow_session_returns_404():
    session_id = uuid4()

    response = client.post(f'/game/{session_id}/opponent-shot', json={'coordinate': 'A1'})

    assert response.status_code == 404
    assert 'detail' in response.json()

def test_closed_session_returns_410(create_game):
    session_id = create_game()

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None

        game.status = 'closed'
        db.commit()

    response = client.post(f'/game/{session_id}/opponent-shot', json={'coordinate': 'A1'})

    assert response.status_code == 410
    assert 'detail' in response.json()

def test_opponent_shots_are_isolated_between_sessions(create_game):
    first_session_id = create_game()
    second_session_id = create_game()

    response = client.post(f'/game/{first_session_id}/opponent-shot', json={'coordinate': 'A1'})

    assert response.status_code == 200

    with SessionLocal() as db:
        first_game = db.get(Game, first_session_id)
        second_game = db.get(Game, second_session_id)

        assert first_game is not None
        assert second_game is not None

        assert first_game.opponent_shots == {'A1': "hit"}

        assert second_game.opponent_shots == {}