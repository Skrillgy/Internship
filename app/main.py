from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.fleet import generate_fleet
from app.models import Game
from app.schemas import StartGameResponse

app = FastAPI(title='NavalBattle Service')

@app.exception_handler(Exception)
async def internal_server_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={'detail': 'Internal Server Error'}
    )

@app.post('/game', response_model=StartGameResponse, status_code=status.HTTP_201_CREATED)
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