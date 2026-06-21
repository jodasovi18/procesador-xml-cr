from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.models.regla_clasificacion import ReglaClasificacion
from app.schemas.regla import ReglaCreate, ReglaOut

router = APIRouter(prefix="/api/reglas", tags=["reglas"])

@router.post("", response_model=ReglaOut, status_code=status.HTTP_201_CREATED)
def crear_regla(data: ReglaCreate, db: Session = Depends(get_db),
                _: Usuario = Depends(get_current_user)):
    regla = ReglaClasificacion(**data.model_dump())
    db.add(regla)
    db.commit()
    db.refresh(regla)
    return regla

@router.get("", response_model=list[ReglaOut])
def listar_reglas(cliente_id: int, db: Session = Depends(get_db),
                  _: Usuario = Depends(get_current_user)):
    stmt = (select(ReglaClasificacion)
            .where(ReglaClasificacion.cliente_id == cliente_id)
            .order_by(ReglaClasificacion.id))
    return list(db.scalars(stmt))
