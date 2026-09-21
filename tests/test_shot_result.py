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

        session_id = UUID(
            response.json()['session_id']
        )

        session_ids.append(session_id)

        return session_id

    yield _create_game

    with SessionLocal() as db:
        for session_id in session_ids:
            game = db.get(Game, session_id)

            if game is not None:
                db.delete(game)

        db.commit()

def test_shot_result_miss_is_saved(create_game):
    session_id = create_game()

    shot_response = client.post(f'/game/{session_id}/shot')
    coordinate = shot_response.json()['coordinate']
    response = client.post(f'/game/{session_id}/shot/result', json={'result': 'miss'})

    assert response.status_code == 200
    assert response.json() == {'status': 'accepted'}

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.own_shots == {coordinate: 'miss'}
        assert game.pending_shot is None
        assert game.turn == 'opponent'

def test_shot_result_hit_is_saved_and_targeted(create_game):
    session_id = create_game()

    shot_response = client.post(f'/game/{session_id}/shot')
    coordinate = shot_response.json()['coordinate']
    response = client.post(f'/game/{session_id}/shot/result', json={'result': 'hit'})

    assert response.status_code == 200

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.own_shots == {coordinate: 'hit'}
        assert game.target_hits == [coordinate]
        assert game.pending_shot is None
        assert game.turn == 'ours'

def test_killed_clears_target_hits(create_game):
    session_id = create_game()

    first_shot = client.post(f'/game/{session_id}/shot')
    first_coordinate = (first_shot.json()['coordinate'])
    first_result = client.post(f'/game/{session_id}/shot/result', json={'result': 'hit'})

    assert first_result.status_code == 200

    second_shot = client.post(f'/game/{session_id}/shot')
    second_coordinate = (second_shot.json()['coordinate'])
    second_result = client.post(f'/game/{session_id}/shot/result', json={'result': 'killed'})

    assert second_result.status_code == 200

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.own_shots == {first_coordinate: 'hit', second_coordinate: 'killed'}
        assert game.target_hits == []
        assert game.pending_shot is None
        assert game.turn == 'ours'

def test_miss_preserves_target_hits(create_game):
    session_id = create_game()

    first_shot = client.post(f'/game/{session_id}/shot')
    first_coordinate = (first_shot.json()['coordinate'])
    client.post(f'/game/{session_id}/shot/result', json={'result': 'hit'})

    second_shot = client.post(f'/game/{session_id}/shot')
    client.post(f'/game/{session_id}/shot/result', json={'result': 'miss'})

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.target_hits == [first_coordinate]
        assert game.turn == 'opponent'

def test_hit_allows_immediate_next_shot(create_game):
    session_id = create_game()

    first_shot = client.post(f'/game/{session_id}/shot')
    first_coordinate = (first_shot.json()['coordinate'])
    result_response = client.post(f'/game/{session_id}/shot/result', json={'result': 'hit'})

    assert result_response.status_code == 200

    second_shot = client.post(f'/game/{session_id}/shot')

    assert second_shot.status_code == 200

    second_coordinate = (second_shot.json()['coordinate'])

    assert second_coordinate != first_coordinate

def test_result_withour_pending_shot_returns_400(create_game):
    session_id = create_game()

    response = client.post(f'/game/{session_id}/shot/result', json={'result': 'miss'})

    assert response.status_code == 409
    assert 'detail' in response.json()

def test_second_result_returns_409(create_game):
    session_id = create_game()

    client.post(f'/game/{session_id}/shot')
    first_result = client.post(f'/game/{session_id}/shot/result', json={'result': 'miss'})

    assert first_result.status_code == 200

    second_result = client.post(f'/game/{session_id}/shot/result', json={'result': 'miss'})

    assert second_result.status_code == 409
    assert 'detail' in second_result.json()

def test_invalid_result_returns_400(create_game):
    session_id = create_game()

    client.post(f'/game/{session_id}/shot')
    response = client.post(f'/game/{session_id}/shot/result', json={'result': 'boom'})

    assert response.status_code == 400
    assert 'detail' in response.json()

def test_result_unknown_session_returns_400():
    session_id = uuid4()

    response = client.post(f'/game/{session_id}/shot/result', json={'result': 'miss'})

    assert response.status_code == 404
    assert 'detail' in response.json()

def test_result_closed_session_returns_410(create_game):
    session_id = create_game()

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None

        game.status = 'closed'
        db.commit()

    response = client.post(f'/game/{session_id}/shot/result', json={'result': 'miss'})

    assert response.status_code == 410
    assert 'detail' in response.json()

def test_invalid_result_keeps_pending_shot(create_game):
    session_id = create_game()

    shot_response = client.post(f'/game/{session_id}/shot')
    coordinate = (shot_response.json()['coordinate'])
    response = client.post(f'/game/{session_id}/shot/result', json={'result': 'invalid'})

    assert response.status_code == 400

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.pending_shot == coordinate
        assert game.own_shots == {}