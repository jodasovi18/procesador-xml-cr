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
    Lanza zipfile.BadZipFile si el ZIP es inválido, o ValueError si excede los topes.

    Nota: el tope de tamaño usa ZipInfo.file_size (declarado en el ZIP); un ZIP
    malicioso podría mentirlo. Aceptable para esta herramienta interna mono-tenant
    (solo usuarios autenticados suben archivos); un límite incremental al descomprimir
    queda diferido."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as zf:
        infos = [i for i in zf.infolist()
                 if not i.is_dir()
                 and i.filename.lower().endswith(".xml")
                 and not i.filename.startswith("__MACOSX/")]
        if len(infos) > max_entradas:
            raise ValueError(f"el ZIP excede el máximo de {max_entradas} entradas")
        if sum(i.file_size for i in infos) > max_bytes:
            raise ValueError("el ZIP excede el tamaño descomprimido permitido")
        return [(i.filename, zf.read(i)) for i in infos]


def _ingest_uno(db: Session, nombre: str, contenido: bytes) -> dict:
    """Procesa un XML en un savepoint. Devuelve el dict de resultado por archivo."""
    try:
        with db.begin_nested():
            r = ingest_xml(db, contenido)
    except (ParseError, ValueError, InvalidOperation) as e:
        return {"archivo": nombre, "estado": "error", "motivo": f"XML inválido: {e}"}
    except IntegrityError:
        return {"archivo": nombre, "estado": "error", "motivo": "conflicto al guardar"}
    if r.get("omitido"):
        return {"archivo": nombre, "estado": "omitido", "motivo": r.get("motivo", "")}
    estado = "nuevo" if r.get("nuevo") else "actualizado"
    return {"archivo": nombre, "estado": estado, "clave": r.get("clave"),
            "rol": r.get("rol"), "cliente_id": r.get("cliente_id")}


def _resumen(resultados: list[dict]) -> dict:
    c = Counter(r["estado"] for r in resultados)
    return {
        "total": len(resultados),
        "nuevos": c["nuevo"], "actualizados": c["actualizado"],
        "omitidos": c["omitido"], "errores": c["error"],
        "archivos": resultados,
    }


def ingest_lote(db: Session, archivos: list[tuple[str, bytes]]) -> dict:
    """Procesa un lote de archivos (.xml o .zip). Éxito parcial: un archivo malo no
    aborta el lote. Hace un único commit al final. Devuelve resumen + detalle."""
    resultados: list[dict] = []
    for nombre, contenido in archivos:
        low = nombre.lower()
        if low.endswith(".zip"):
            try:
                entradas = _entradas_zip(contenido)
            except (zipfile.BadZipFile, ValueError) as e:
                resultados.append({"archivo": nombre, "estado": "error", "motivo": f"ZIP inválido: {e}"})
                continue
            for sub_nombre, sub_bytes in entradas:
                resultados.append(_ingest_uno(db, sub_nombre, sub_bytes))
        elif low.endswith(".xml"):
            resultados.append(_ingest_uno(db, nombre, contenido))
        # otros tipos: se ignoran silenciosamente
    db.commit()
    return _resumen(resultados)
