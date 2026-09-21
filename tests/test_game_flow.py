from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.fleet import parse_coordinate, to_coordinate
from app.main import app
from app.models import Game


client = TestClient(app)


@pytest.fixture
def create_game():
    session_ids = []

    def _create_game():
        response = client.post('/game')

        assert response.status_code == 201

        body = response.json()

        session_id = UUID(body['session_id'])
        ships = body['ships']

        session_ids.append(session_id)

        return session_id, ships

    yield _create_game

    with SessionLocal() as db:
        for session_id in session_ids:
            game = db.get(Game, session_id)

            if game is not None:
                db.delete(game)

        db.commit()

def test_complete_shooting_flow(create_game):
    session_id, ships = create_game()

    first_shot = client.post(f'/game/{session_id}/shot')
    assert first_shot.status_code == 200

    first_coordinate = (first_shot.json()['coordinate'])
    first_result = client.post(f'/game/{session_id}/shot/result', json={'result': 'hit'})

    assert first_result.status_code == 200

    second_shot = client.post(f'/game/{session_id}/shot')
    assert second_shot.status_code == 200

    second_coordinate = (second_shot.json()['coordinate'])
    assert second_coordinate != first_coordinate

    first_row, first_column = parse_coordinate(first_coordinate)
    second_row, second_column = parse_coordinate(second_coordinate)

    assert (abs(first_row - second_row) + abs(first_column - second_column) == 1)

    second_result = client.post(f'/game/{session_id}/shot/result', json={'result': 'hit'})
    assert second_result.status_code == 200

    third_shot = client.post(f'/game/{session_id}/shot')
    assert third_shot.status_code == 200

    third_coordinate = (third_shot.json()['coordinate'])
    assert third_coordinate not in {first_coordinate, second_coordinate}

    third_row, third_column = parse_coordinate(third_coordinate)

    if first_row == second_row:
        assert third_row == first_row
    else:
        assert third_column == first_column

    third_result = client.post(f'/game/{session_id}/shot/result', json={'result': 'killed'})
    assert third_result.status_code == 200

    fourth_shot = client.post(f'/game/{session_id}/shot')
    assert fourth_shot.status_code == 200

    fourth_coordinate = (fourth_shot.json()['coordinate'])
    assert fourth_coordinate not in (first_coordinate, second_coordinate, third_coordinate)

    fourth_result = client.post(f'/game/{session_id}/shot/result', json={'result': 'miss'})
    assert fourth_result.status_code == 200

    blocked_shot = client.post(f'/game/{session_id}/shot')
    assert blocked_shot.status_code == 409

    single_deck_coordinate = next(
        ship['coordinates'][0]
        for ship in ships
        if len(ship['coordinates']) == 1
    )

    opponent_kill = client.post(f'/game/{session_id}/opponent-shot', json={'coordinate': single_deck_coordinate})

    assert opponent_kill.status_code == 200
    assert opponent_kill.json() == {'result': 'killed'}

    still_blocked = client.post(f'/game/{session_id}/shot')
    assert still_blocked.status_code == 409

    occupied = {coordinate for ship in ships for coordinate in ship['coordinates']}

    water_coordinate = next(
        to_coordinate(row,column) for row in range(10)
        for column in range(10) if to_coordinate(row, column)
        not in occupied
    )

    opponent_miss = client.post(f'/game/{session_id}/opponent-shot', json={'coordinate': water_coordinate})

    assert opponent_miss.status_code == 200
    assert opponent_miss.json() == {'result': 'miss'}

    resumed_shot = client.post(f'/game/{session_id}/shot')
    assert resumed_shot.status_code == 200

    resumed_coordinate = (resumed_shot.json()['coordinate'])
    assert resumed_coordinate not in (first_coordinate, second_coordinate, third_coordinate, fourth_coordinate)

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None

        assert game.own_shots == {
            first_coordinate: 'hit',
            second_coordinate: 'hit',
            third_coordinate: 'killed',
            fourth_coordinate: 'miss'
        }

        assert game.target_hits == []
        assert game.pending_shot == resumed_coordinate
        assert game.turn == 'ours'

        assert game.opponent_shots == {
            single_deck_coordinate: 'killed',
            water_coordinate: 'miss'
        }

def test_parallel_games_keep_independent_state(create_game):
    first_session_id, _ = create_game()
    second_session_id, _ = create_game()

    first_shot = client.post(f'/game/{first_session_id}/shot')
    second_shot = client.post(f'/game/{second_session_id}/shot')

    assert first_shot.status_code == 200
    assert second_shot.status_code == 200

    first_coordinate = (first_shot.json()['coordinate'])
    second_coordinate = (second_shot.json()['coordinate'])

    result = client.post(f'/game/{first_session_id}/shot/result', json={'result': 'hit'})
    assert result.status_code == 200

    with SessionLocal() as db:
        first_game = db.get(Game, first_session_id)
        second_game = db.get(Game, second_session_id)

        assert first_game is not None
        assert second_game is not None

        assert first_game.own_shots == {first_coordinate: 'hit'}
        assert first_game.target_hits == [first_coordinate]
        assert first_game.pending_shot is None

        assert second_game.own_shots == {}
        assert second_game.target_hits == []
        assert (second_game.pending_shot == second_coordinate)