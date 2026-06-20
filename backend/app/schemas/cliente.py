from pydantic import BaseModel, ConfigDict, field_validator

class ClienteCreate(BaseModel):
    cedula: str
    nombre: str
    tipo_cedula: str   # TODO: validar dominio (fisica|juridica|dimex|nite) al confirmar valores CR
    regimen: str = "tradicional"  # TODO: validar dominio (tradicional|simplificado|...) al confirmar

    @field_validator("cedula", "nombre", "tipo_cedula", "regimen")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

class ClienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cedula: str
    nombre: str
    tipo_cedula: str
    regimen: str
