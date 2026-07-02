from pydantic import BaseModel, ConfigDict, field_validator

TIPOS_CEDULA_VALID = {"fisica", "juridica", "dimex", "nite"}
REGIMENES_VALID = {"tradicional", "simplificado"}


class ClienteCreate(BaseModel):
    cedula: str
    nombre: str
    tipo_cedula: str
    regimen: str = "tradicional"

    @field_validator("cedula", "nombre")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("tipo_cedula")
    @classmethod
    def _tipo_cedula(cls, v: str) -> str:
        v = v.strip()
        if v not in TIPOS_CEDULA_VALID:
            raise ValueError(f"tipo_cedula inválido: {v}")
        return v

    @field_validator("regimen")
    @classmethod
    def _regimen(cls, v: str) -> str:
        v = v.strip()
        if v not in REGIMENES_VALID:
            raise ValueError(f"regimen inválido: {v}")
        return v


class ClienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cedula: str
    nombre: str
    tipo_cedula: str
    regimen: str
