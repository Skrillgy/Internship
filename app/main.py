from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.db import get_db
from app.fleet import generate_fleet
from app.models import Game
from app.schemas import StartGameResponse

app = FastAPI(title='NavalBattle Service')

@app.post('/games', response_model=StartGameResponse)
def start_game(
    db: Session = Depends(get_db)
) -> StartGameResponse:
    fleet = generate_fleet()

    game = Game(
        ships=fleet
    )

    db.add(game)
    db.commit()
    db.refresh(game)

    return StartGameResponse(
        session_id=game.session_id,
        ships=game.ships
    )