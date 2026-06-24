from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator


class AgentTokenCreate(BaseModel):
    label: str

    @field_validator("label")
    @classmethod
    def _label(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("label requerido")
        return v


class AgentTokenCreated(BaseModel):
    id: int
    label: str
    token: str   # texto plano, devuelto una sola vez


class AgentTokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    created_at: datetime
