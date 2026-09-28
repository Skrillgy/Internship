from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db import get_db
from app.fleet import generate_fleet
from app.models import Game
from app.schemas import (
    CloseGameResponse,
    OpponentShotRequest,
    OpponentShotResponse,
    ShotResponse,
    ShotResultRequest,
    ShotResultResponse,
    StartGameResponse
)
from app.shots import (choose_shot, resolve_opponent_shot)

app = FastAPI(title='NavalBattle Service')

@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={'detail': 'Bad Request'}
    )

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

@app.post('/game/{session_id}/shot', response_model=ShotResponse, status_code=status.HTTP_200_OK)
def make_shot(
    session_id: UUID,
    db: Session = Depends(get_db)
) -> ShotResponse:
    game = db.get(Game, session_id)

    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Session not found'
        )

    if game.status != 'active':
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail='Session is not active'
        )

    if game.turn == 'opponent':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Not our turn'
        )

    if game.pending_shot is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Previous shot result is pending'
        )

    coordinate = choose_shot(
        game.own_shots,
        game.target_hits
    )

    game.pending_shot = coordinate
    game.turn = 'ours'

    db.commit()

    return ShotResponse(coordinate=coordinate)

@app.post('/game/{session_id}/shot/result', response_model=ShotResultResponse, status_code=status.HTTP_200_OK)
def accept_shot_result(
    session_id: UUID,
    shot_result: ShotResultRequest,
    db: Session = Depends(get_db)
) -> ShotResultResponse:
    game = db.get(Game, session_id)

    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Session not found'
        )

    if game.status != 'active':
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail='Session is not active'
        )

    if game.pending_shot is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='No shot result is expected'
        )

    if game.turn != 'ours':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Invalid game sequence'
        )

    coordinate = game.pending_shot
    result = shot_result.result

    updated_shots = dict(game.own_shots)
    updated_shots[coordinate] = result
    game.own_shots = updated_shots

    if result == 'hit':
        updated_target_hits = list(game.target_hits)

        if coordinate not in updated_target_hits:
            updated_target_hits.append(coordinate)

        game.target_hits = updated_target_hits
        game.turn = 'ours'

    elif result == 'killed':
        game.target_hits = []
        game.turn = 'ours'

    else:
        game.turn = 'opponent'

    game.pending_shot = None
    db.commit()

    return ShotResultResponse(status='accepted')

@app.post('/game/{session_id}/opponent-shot', response_model=OpponentShotResponse, status_code=status.HTTP_200_OK)
def opponent_shot(
    session_id: UUID,
    shot: OpponentShotRequest,
    db: Session = Depends(get_db)
) -> OpponentShotResponse:
    game = db.get(Game, session_id)

    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Session not found'
        )

    if game.status != 'active':
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail='Session is not active'
        )

    try:
        result = resolve_opponent_shot(
            game.ships,
            game.opponent_shots,
            shot.coordinate
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid coordinate'
        ) from exc

    update_shots = dict(game.opponent_shots)
    update_shots[shot.coordinate] = result
    game.opponent_shots = update_shots

    if result == 'miss':
        game.turn = 'ours'
    else:
        game.turn = 'opponent'

    db.commit()

    return OpponentShotResponse(result=result)

@app.post('/game/{session_id}/close', response_model=CloseGameResponse, status_code=status.HTTP_200_OK)
def close_game(
    session_id: UUID,
    db: Session = Depends(get_db)
) -> CloseGameResponse:
    result = db.execute(
        update(Game)
        .where(Game.session_id == session_id, Game.status == 'active')
        .values(status='closed')
    )

    if result.rowcount == 1:
        db.commit()
        return CloseGameResponse(status='closed')

    game = db.get(Game, session_id)

    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Session not found'
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail='Session is already closed'
    )