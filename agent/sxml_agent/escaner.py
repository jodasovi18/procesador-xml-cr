"""Escaneo de carpetas: encuentra los .xml (recursivo) y calcula su hash de contenido."""
import hashlib
from pathlib import Path


def escanear(carpetas: list[str]) -> list[Path]:
    """Devuelve todos los .xml (recursivo) de las carpetas dadas, sin duplicados,
    ordenados. Las carpetas inexistentes se omiten."""
    vistos: set[Path] = set()
    for carpeta in carpetas:
        base = Path(carpeta)
        if not base.is_dir():
            continue
        for p in base.rglob("*.xml"):
            if p.is_file():
                vistos.add(p.resolve())
    return sorted(vistos)


def hash_archivo(path: Path) -> str:
    """sha256 hex del contenido del archivo (lectura por bloques)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()
