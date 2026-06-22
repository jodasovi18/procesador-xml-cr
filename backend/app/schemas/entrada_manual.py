from decimal import Decimal
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

class EntradaManualCreate(BaseModel):
    cliente_id: int
    periodo: str
    rol: str
    descripcion: str | None = None
    monto: Decimal
    tarifa: Decimal = Decimal("0")
    no_sujeto: bool = False
    deducible: bool = True

    @field_validator("rol")
    @classmethod
    def _rol(cls, v: str) -> str:
        v = v.strip()
        if v not in {"compra", "venta"}:
            raise ValueError("rol debe ser 'compra' o 'venta'")
        return v

    @field_validator("periodo")
    @classmethod
    def _periodo(cls, v: str) -> str:
        v = v.strip()
        if len(v) != 6 or not v.isdigit():
            raise ValueError("periodo debe ser YYYYMM")
        return v

    @field_validator("monto", "tarifa")
    @classmethod
    def _no_neg(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("monto y tarifa no pueden ser negativos")
        return v

class EntradaManualOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente_id: int
    periodo: str
    rol: str
    descripcion: str | None
    monto: Decimal
    tarifa: Decimal
    no_sujeto: bool
    deducible: bool

    @field_serializer("monto", "tarifa")
    def _ser_dec(self, v: Decimal) -> str:
        return str(v)
