from decimal import InvalidOperation
from xml.etree.ElementTree import ParseError
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.motor.ingesta import ingest_xml
from app.motor.ingesta_lote import ingest_lote

router = APIRouter(prefix="/api/ingesta", tags=["ingesta"])

@router.post("")
def ingesta(archivo: UploadFile, db: Session = Depends(get_db),
            _: Usuario = Depends(get_current_user)):
    contenido = archivo.file.read()
    try:
        resultado = ingest_xml(db, contenido)
        db.commit()
        return resultado
    except (ParseError, ValueError, InvalidOperation) as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=f"XML inválido: {e}")
    except IntegrityError:
        db.rollback()
        # Carrera con otra ingesta del mismo comprobante: reintentar una vez.
        try:
            resultado = ingest_xml(db, contenido)
            db.commit()
            return resultado
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Conflicto al guardar el comprobante")

@router.post("/lote")
def ingesta_lote(archivos: list[UploadFile], db: Session = Depends(get_db),
                 _: Usuario = Depends(get_current_user)):
    pares = [(a.filename or "", a.file.read()) for a in archivos]
    return ingest_lote(db, pares)
