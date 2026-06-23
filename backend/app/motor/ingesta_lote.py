"""Subida masiva: expande ZIP a entradas .xml y procesa un lote reutilizando
ingest_xml, con éxito parcial (savepoint por archivo) y reporte por archivo."""
import io
import zipfile
from collections import Counter
from decimal import InvalidOperation
from xml.etree.ElementTree import ParseError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.motor.ingesta import ingest_xml

MAX_ENTRADAS_ZIP = 5000
MAX_BYTES_DESCOMPRIMIDO = 200 * 1024 * 1024  # 200 MB


def _entradas_zip(contenido: bytes, max_entradas: int = MAX_ENTRADAS_ZIP,
                  max_bytes: int = MAX_BYTES_DESCOMPRIMIDO) -> list[tuple[str, bytes]]:
    """Devuelve las entradas .xml de un ZIP (ignora directorios, no-.xml y __MACOSX).
    Lanza zipfile.BadZipFile si el ZIP es inválido, o ValueError si excede los topes."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as zf:
        infos = [i for i in zf.infolist()
                 if not i.is_dir()
                 and i.filename.lower().endswith(".xml")
                 and "__MACOSX" not in i.filename]
        if len(infos) > max_entradas:
            raise ValueError(f"el ZIP excede el máximo de {max_entradas} entradas")
        if sum(i.file_size for i in infos) > max_bytes:
            raise ValueError("el ZIP excede el tamaño descomprimido permitido")
        return [(i.filename, zf.read(i)) for i in infos]
