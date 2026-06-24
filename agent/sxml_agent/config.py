"""Carga de configuración del agente desde un archivo TOML."""
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    backend_url: str
    carpetas: list[str]
    usuario: str = ""
    clave: str = ""
    lote_size: int = 100
    estado_path: str = "estado.json"
    intervalo: int = 300  # segundos entre pasadas en modo watch
    token: str | None = None  # token de agente (alternativa a usuario/clave)


def cargar_config(path: str) -> Config:
    ruta = Path(path)
    try:
        texto = ruta.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {ruta}")
    try:
        data = tomllib.loads(texto)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"TOML inválido en {ruta}: {e}") from e
    faltantes = {"backend_url", "carpetas"} - data.keys()
    if faltantes:
        raise ValueError(f"Faltan claves requeridas en {ruta}: {sorted(faltantes)}")
    token = data.get("token")
    usuario = str(data.get("usuario", ""))
    clave = str(data.get("clave", ""))
    if not token and not (usuario and clave):
        raise ValueError(f"En {ruta}: se requiere 'token' o ('usuario' y 'clave')")
    return Config(
        backend_url=str(data["backend_url"]).rstrip("/"),
        usuario=usuario,
        clave=clave,
        carpetas=[str(c) for c in data["carpetas"]],
        lote_size=int(data.get("lote_size", 100)),
        estado_path=str(data.get("estado_path", "estado.json")),
        intervalo=int(data.get("intervalo", 300)),
        token=str(token) if token else None,
    )
