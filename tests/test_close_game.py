from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from threading import Event
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Game

client = TestClient(app)
APP_URL = 'http://127.0.0.1:8000'
MAX_RESPONSE_TIME = 1.0

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

def test_close_game(create_game):
    session_id = create_game()

    response = client.post(f'/game/{session_id}/close')

    assert response.status_code == 200
    assert response.json() == {'status': 'closed'}

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.status == 'closed'

def test_close_game_twice_returns_400(create_game):
    session_id = create_game()

    first_response = client.post(f'/game/{session_id}/close')

    assert first_response.status_code == 200

    second_response = client.post(f'/game/{session_id}/close')

    assert second_response.status_code == 400
    assert 'detail' in second_response.json()

def test_close_unknown_session_returns_404():
    session_id = uuid4()

    responce = client.post(f'/game/{session_id}/close')

    assert responce.status_code == 404
    assert 'detail' in responce.json()

@pytest.mark.parametrize(
    ('path', 'body'), [
        ('shot', None),
        ('shot/result', {'result': 'miss'}),
        ('opponent-shot', {'coordinate': 'A1'})
    ]
)
def test_closed_game_rejects_game_actions(create_game, path, body):
    session_id = create_game()

    close_response = client.post(f'/game/{session_id}/close')

    assert close_response.status_code == 200

    if body is None:
        response = client.post(f'/game/{session_id}/{path}')
    else:
        response = client.post(f'/game/{session_id}/{path}', json=body)

    assert response.status_code == 410
    assert 'detail' in response.json()

def test_closing_one_game_does_not_close_another(create_game):
    first_session_id = create_game()
    second_session_id = create_game()

    response = client.post(f'/game/{first_session_id}/close')

    assert response.status_code == 200

    with SessionLocal() as db:
        first_game = db.get(Game, first_session_id)
        second_game = db.get(Game, second_session_id)

        assert first_game is not None
        assert second_game is not None

        assert first_game.status == 'closed'
        assert second_game.status == 'active'

def test_parallel_close_only_one_request_succeeds(create_game):
    session_id = create_game()
    start_event = Event()

    def close_game():
        start_event.wait()

        started_at = perf_counter()
        response = httpx.post(f'{APP_URL}/game/{session_id}/close')
        elapsed = perf_counter() - started_at

        return response.status_code, elapsed

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(close_game),
            executor.submit(close_game)
        ]

        start_event.set()
        results = [future.result(timeout=10) for future in futures]
        status_codes = [status_code for status_code, _ in results]

        assert sorted(status_codes) == [200, 400]

        for status_code, elapsed in results:
            assert elapsed < MAX_RESPONSE_TIME, (
                f'/close returned {status_code} '
                f'in {elapsed:.3f} seconds'
            )

        with SessionLocal() as db:
            game = db.get(Game, session_id)

            assert game is not None
            assert game.status == 'closed'