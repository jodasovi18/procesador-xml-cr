from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from app.motor.clasificacion import CLASIFICACIONES_VALID

class ReglaCreate(BaseModel):
    cliente_id: int
    cedula: str | None = None
    cabys: str | None = None
    rol: str | None = None
    clasificacion: str
    sub_clasificacion: str | None = None

    @field_validator("cedula", "cabys", "sub_clasificacion")
    @classmethod
    def _empty_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip() or None

    @field_validator("rol")
    @classmethod
    def _valid_rol(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip() or None
        if v is not None and v not in {"compra", "venta"}:
            raise ValueError("rol debe ser 'compra' o 'venta'")
        return v

    @field_validator("clasificacion")
    @classmethod
    def _valid_clas(cls, v: str) -> str:
        v = v.strip()
        if v not in CLASIFICACIONES_VALID:
            raise ValueError(f"clasificacion inválida: {v}")
        return v

    @model_validator(mode="after")
    def _ced_o_cabys(self):
        if not self.cedula and not self.cabys:
            raise ValueError("se requiere al menos cedula o cabys")
        return self

class ReglaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente_id: int
    cedula: str | None
    cabys: str | None
    rol: str | None
    clasificacion: str
    sub_clasificacion: str | None
