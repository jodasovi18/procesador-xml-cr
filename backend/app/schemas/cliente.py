from pydantic import BaseModel, ConfigDict

class ClienteCreate(BaseModel):
    cedula: str
    nombre: str
    tipo_cedula: str
    regimen: str = "tradicional"

class ClienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cedula: str
    nombre: str
    tipo_cedula: str
    regimen: str
