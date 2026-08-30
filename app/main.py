from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Game
from app.schemas import StartGameResponse

app = FastAPI(title='NavalBattle Service')

@app.post('/games', response_model=StartGameResponse)
def start_game(
    db: Session = Depends(get_db)
) -> StartGameResponse:
    game = Game()

    db.add(game)
    db.commit()
    db.refresh(game)

    return StartGameResponse(
        session_id=game.session_id
    )