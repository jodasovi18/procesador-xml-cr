from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.motor.preclasificacion import grupos_sin_clasificar

router = APIRouter(prefix="/api/preclasificacion", tags=["preclasificacion"])


@router.get("")
def preclasificacion(cliente_id: int, periodo: str, rol: str, por: str = "cabys",
                     db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    if rol not in ("compra", "venta"):
        raise HTTPException(status_code=422, detail="rol debe ser 'compra' o 'venta'")
    if por not in ("cabys", "cedula"):
        raise HTTPException(status_code=422, detail="por debe ser 'cabys' o 'cedula'")
    grupos = grupos_sin_clasificar(db, cliente_id, periodo, rol, por)
    return [{"clave": g.clave, "etiqueta": g.etiqueta, "lineas": g.lineas, "base": str(g.base)}
            for g in grupos]
