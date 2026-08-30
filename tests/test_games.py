from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db import SessionLocal, engine
from app.main import app
from app.models import Game

client = TestClient(app)

def test_games_table_exists():
    inspector = inspect(engine)

    assert inspector.has_table('games')

def test_start_game():
    response = client.post('/games')

    assert response.status_code == 200

    body = response.json()

    assert "session_id" in body

    session_id = UUID(body['session_id'])

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.status == 'active'

        db.delete(game)
        db.commit()