import httpx
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from threading import Barrier, Event
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Game

client = TestClient(app)

PARALLEL_GAMES = 8
MAX_RESPONSE_TIME = 1.0
API_URL = 'http://127.0.0.1:8000'

@pytest.fixture
def create_game():
    session_ids= []

    def _create_game():
        response = client.post('/game')

        assert response.status_code == 201

        body = response.json()
        session_id = UUID(body['session_id'])

        session_ids.append(session_id)

        return session_id, body['ships']

    yield _create_game

    with SessionLocal() as db:
        for session_id in session_ids:
            game = db.get(Game, session_id)

            if game is not None:
                db.delete(game)

        db.commit()

def test_parallel_games_keep_own_shots_isolated(create_game):
    games = [create_game() for _ in range(PARALLEL_GAMES)]
    session_ids = [session_id for session_id, _ in games]
    barrier = Barrier(PARALLEL_GAMES)

    def make_shot(session_id):
        barrier.wait(timeout=10)

        started_at = perf_counter()
        response = httpx.post(f'{API_URL}/game/{session_id}/shot')
        elapsed = perf_counter() - started_at

        return session_id, response, elapsed

    with ThreadPoolExecutor(max_workers=PARALLEL_GAMES) as executor:
        futures = [executor.submit(make_shot, session_id) for session_id in session_ids]
        shot_results = [future.result() for future in futures]

    coordinates = {}

    for session_id, response, elapsed in shot_results:
        assert response.status_code == 200

        assert elapsed < MAX_RESPONSE_TIME, (
            f'/shot for session {session_id} '
            f'took {elapsed:.3f} seconds'
        )

        coordinates[session_id] = (response.json()['coordinate'])

    expected_results = {}

    for index, session_id in enumerate(session_ids):
        if index % 2 == 0:
            expected_results[session_id] = 'hit'
        else:
            expected_results[session_id] = 'miss'

    result_barrier = Barrier(PARALLEL_GAMES)

    def accept_result(session_id):
        result_barrier.wait(timeout=10)

        started_at = perf_counter()
        response = httpx.post(f'{API_URL}/game/{session_id}/shot/result', json={'result': expected_results[session_id]})
        elapsed = perf_counter() - started_at

        return session_id, response, elapsed

    with ThreadPoolExecutor(max_workers=PARALLEL_GAMES) as executor:
        futures = [executor.submit(accept_result, session_id) for session_id in session_ids]
        result_responses = [future.result() for future in futures]

    for session_id, response, elapsed in result_responses:
        assert response.status_code == 200
        assert response.json() == {'status': 'accepted'}
        assert elapsed < MAX_RESPONSE_TIME, (
            f'/shot/result for session {session_id} '
            f'took {elapsed:.3f} seconds'
        )

    with SessionLocal() as db:
        for session_id in session_ids:
            game = db.get(Game, session_id)

            assert game is not None

            coordinate = coordinates[session_id]
            expected_result = expected_results[session_id]

            assert game.own_shots == {coordinate: expected_result}
            assert game.pending_shot is None

            if expected_result == 'hit':
                assert game.target_hits == [coordinate]
                assert game.turn == 'ours'
            else:
                assert game.target_hits == []
                assert game.turn == 'opponent'

def test_parallel_opponent_shots_are_isolated(create_game):
    games = [create_game() for _ in range(PARALLEL_GAMES)]

    requests = []

    for session_id, ships in games:
        single_deck_coordinate = next(ship['coordinates'][0] for ship in ships if len(ship['coordinates']) == 1)

        requests.append ((session_id, single_deck_coordinate))
        start_event = Event()

        def opponent_shot(session_id, coordinate):
            start_event.wait()

            started_at = perf_counter()
            response = httpx.post(f'{API_URL}/game/{session_id}/opponent-shot', json={'coordinate': coordinate})
            elapsed = perf_counter() - started_at

            return session_id, coordinate, response, elapsed

        with ThreadPoolExecutor(max_workers=PARALLEL_GAMES) as executor:
            futures = [executor.submit(opponent_shot, session_id, coordinate) for session_id, coordinate in requests]
            start_event.set()
            responses = [future.result() for future in futures]

        with SessionLocal() as db:
            for (session_id, coordinate, response, elapsed) in responses:
                assert response.status_code == 200
                assert response.json() == {'result': 'killed'}
                assert elapsed < MAX_RESPONSE_TIME, (
                    f'/opponent-shot for session '
                    f'{session_id} took'
                    f'{elapsed:.3f} seconds'
                )

                game = db.get(Game, session_id)

                assert game is not None
                assert game.opponent_shots == {coordinate: 'killed'}
                assert game.own_shots == {}
                assert game.pending_shot is None
                assert game.target_hits == []
                assert game.turn == 'opponent'

def test_parallel_game_creation():
    start_event = Event()

    def create_game():
        start_event.wait()

        started_at = perf_counter()
        response = httpx.post(f'{API_URL}/game')
        elapsed = perf_counter() - started_at

        return response, elapsed

    with ThreadPoolExecutor(max_workers=PARALLEL_GAMES) as executor:
        futures = [executor.submit(create_game) for _ in range(PARALLEL_GAMES)]
        start_event.set()
        results = [future.result(timeout=10) for future in futures]

    session_ids = []

    try:
        for response, elapsed in results:
            assert response.status_code == 201
            assert elapsed < MAX_RESPONSE_TIME, (
                f'/game took {elapsed:.3f} seconds'
            )

            body = response.json()

            session_id = UUID(body['session_id'])
            session_ids.append(session_id)

            assert 'ships' in body

        assert len(session_ids) == PARALLEL_GAMES
        assert len(set(session_ids)) == PARALLEL_GAMES

        with SessionLocal() as db:
            for session_id in session_ids:
                game = db.get(Game, session_id)

                assert game is not None
                assert game.status == 'active'
                assert game.own_shots == {}
                assert game.opponent_shots == {}
                assert game.target_hits == []
                assert game.pending_shot is None
                assert game.turn == 'unknown'

    finally:
        with SessionLocal() as db:
            for session_id in session_ids:
                game = db.get(Game, session_id)

                if game is not None:
                    db.delete(game)

            db.commit()