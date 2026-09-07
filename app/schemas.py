from uuid import UUID
from pydantic import BaseModel


class ShipResponse(BaseModel):
    coordinates: list[str]

class StartGameResponse(BaseModel):
    session_id: UUID
    ships: list[ShipResponse]