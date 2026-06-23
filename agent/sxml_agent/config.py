"""Carga de configuración del agente desde un archivo TOML."""
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    backend_url: str
    usuario: str
    clave: str
    carpetas: list[str]
    lote_size: int = 100
    estado_path: str = "estado.json"


def cargar_config(path: str) -> Config:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return Config(
        backend_url=str(data["backend_url"]).rstrip("/"),
        usuario=str(data["usuario"]),
        clave=str(data["clave"]),
        carpetas=[str(c) for c in data["carpetas"]],
        lote_size=int(data.get("lote_size", 100)),
        estado_path=str(data.get("estado_path", "estado.json")),
    )
