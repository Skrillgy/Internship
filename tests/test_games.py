from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db import SessionLocal, engine
from app.fleet import validate_fleet
from app.main import app
from app.models import Game

client = TestClient(app)

def test_games_table_exists():
    inspector = inspect(engine)

    assert inspector.has_table('games')

def test_start_game():
    response = client.post('/game')

    assert response.status_code == 201

    body = response.json()

    assert 'session_id' in body
    assert 'ships' in body

    session_id = UUID(body['session_id'])
    ships = body['ships']

    assert validate_fleet(ships)

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.status == 'active'
        assert game.ships == ships

        db.delete(game)
        db.commit()

def test_start_multiple_games():
    first_response = client.post('/game')
    second_response = client.post('/game')

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_body = first_response.json()
    second_body = second_response.json()

    first_session_id = UUID(first_body['session_id'])
    second_session_id = UUID(second_body['session_id'])

    assert first_session_id != second_session_id

    assert validate_fleet(first_body['ships'])
    assert validate_fleet(second_body['ships'])

    with SessionLocal() as db:
        first_game = db.get(Game, first_session_id)
        second_game = db.get(Game, second_session_id)

        assert first_game is not None
        assert second_game is not None

        assert first_game.status == 'active'
        assert second_game.status == 'active'

        assert first_game.ships == first_body['ships']
        assert second_game.ships == second_body['ships']

        db.delete(first_game)
        db.delete(second_game)
        db.commit()

def test_start_game_internal_server_error(monkeypatch):
    def broken_generate_fleet():
        raise RuntimeError('Test error')

    monkeypatch.setattr('app.main.generate_fleet', broken_generate_fleet)
    error_client = TestClient(app, raise_server_exceptions=False)

    response = error_client.post('/game')
    assert response.status_code == 500
    assert response.json() == {'detail': 'Internal Server Error'}