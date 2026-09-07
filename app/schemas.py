from uuid import UUID
from pydantic import BaseModel

class StartGameResponse(BaseModel):
    session_id: UUID