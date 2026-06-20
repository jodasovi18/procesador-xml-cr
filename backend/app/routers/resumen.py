from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.motor.resumen import build_resumen

router = APIRouter(prefix="/api/resumen", tags=["resumen"])

@router.get("")
def resumen(cliente_id: int, periodo: str, rol: str,
            db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    cats = build_resumen(db, cliente_id, periodo, rol)
    return {cat: {"base": str(v["base"]), "iva": str(v["iva"])} for cat, v in cats.items()}
