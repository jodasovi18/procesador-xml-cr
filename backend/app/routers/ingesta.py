from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.motor.ingesta import ingest_xml

router = APIRouter(prefix="/api/ingesta", tags=["ingesta"])

@router.post("")
def ingesta(archivo: UploadFile, db: Session = Depends(get_db),
            _: Usuario = Depends(get_current_user)):
    contenido = archivo.file.read()
    return ingest_xml(db, contenido)
