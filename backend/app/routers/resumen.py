from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.motor.resumen import build_resumen, build_resumen_clasificacion

router = APIRouter(prefix="/api/resumen", tags=["resumen"])

@router.get("")
def resumen(cliente_id: int, periodo: str, rol: str,
            db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    cats = build_resumen(db, cliente_id, periodo, rol)
    return {cat: {"base": str(v["base"]), "iva": str(v["iva"])} for cat, v in cats.items()}

@router.get("/clasificacion")
def resumen_clasificacion(cliente_id: int, periodo: str, rol: str,
                          db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    data = build_resumen_clasificacion(db, cliente_id, periodo, rol)
    return {
        clas: {tasa: {"base": str(v["base"]), "iva": str(v["iva"])} for tasa, v in tasas.items()}
        for clas, tasas in data.items()
    }
