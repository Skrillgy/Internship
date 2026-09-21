from uuid import UUID
from pydantic import BaseModel
from typing import Literal


class ShipResponse(BaseModel):
    coordinates: list[str]

class StartGameResponse(BaseModel):
    session_id: UUID
    ships: list[ShipResponse]

class OpponentShotRequest(BaseModel):
    coordinate: str

class OpponentShotResponse(BaseModel):
    result: Literal['miss', 'hit', 'killed']

class ShotResponse(BaseModel):
    coordinate: str

class ShotResultRequest(BaseModel):
    result: Literal['miss', 'hit', 'killed']

class ShotResultResponse(BaseModel):
    status: Literal['accepted']