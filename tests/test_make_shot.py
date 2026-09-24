from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Game


client = TestClient(app)

@pytest.fixture
def create_game():
    session_ids = []

    def _create_game():
        response = client.post('/game')

        assert response.status_code == 201

        session_id = UUID(response.json()['session_id'])
        session_ids.append(session_id)

        return session_id

    yield _create_game

    with SessionLocal() as db:
        for session_id in session_ids:
            game = db.get(Game, session_id)

            if game is not None:
                db.delete(game)

        db.commit()

def test_make_shot_returns_coordinate(create_game):
    session_id = create_game()

    response = client.post(f'/game/{session_id}/shot')

    assert response.status_code == 200

    body = response.json()

    assert 'coordinate' in body
    assert body['coordinate'] == 'A1'

def test_make_shot_saves_pending_shot(create_game):
    session_id = create_game()

    response = client.post(f'/game/{session_id}/shot')

    coordinate = response.json()['coordinate']

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.pending_shot == coordinate
        assert game.own_shots == {}
        assert game.turn == 'ours'

def test_make_shot_is_allowed_when_turn_unknown(create_game):
    session_id = create_game()

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.turn == 'unknown'

    response = client.post(f'/game/{session_id}/shot')

    assert response.status_code == 200

def test_make_shot_rejected_on_opponent_turn(create_game):
    session_id = create_game()

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None

        game.turn = 'opponent'
        db.commit()

    response = client.post(f'/game/{session_id}/shot')

    assert response.status_code == 409
    assert 'detail' in response.json()

def test_second_shot_rejected_while_result_pending(create_game):
    session_id = create_game()

    first_response = client.post(f'/game/{session_id}/shot')

    assert first_response.status_code == 200

    second_response = client.post(f'/game/{session_id}/shot')

    assert second_response.status_code == 409
    assert 'detail' in second_response.json()

def test_make_shot_skips_previous_shots(create_game):
    session_id = create_game()

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None

        game.own_shots = {'A1': 'miss'}
        game.turn = 'ours'
        db.commit()

    response = client.post(f'/game/{session_id}/shot')

    assert response.status_code == 200

    coordinate = response.json()['coordinate']

    assert coordinate != 'A1'

def test_make_shot_unknown_session_returns_404():
    session_id = uuid4()

    response = client.post(f'/game/{session_id}/shot')

    assert response.status_code == 404
    assert 'detail' in response.json()

def test_make_shot_closed_session_returns_410(create_game):
    session_id = create_game()

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None

        game.status = 'closed'
        db.commit()

    response = client.post(f'/game/{session_id}/shot')

    assert response.status_code == 410
    assert 'detail' in response.json()