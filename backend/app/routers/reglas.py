from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="cliente_id inválido o regla duplicada")
    db.refresh(regla)
    return regla

@router.get("", response_model=list[ReglaOut])
def listar_reglas(cliente_id: int, db: Session = Depends(get_db),
                  _: Usuario = Depends(get_current_user)):
    stmt = (select(ReglaClasificacion)
            .where(ReglaClasificacion.cliente_id == cliente_id)
            .order_by(ReglaClasificacion.id))
    return list(db.scalars(stmt))

@router.delete("/{regla_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_regla(regla_id: int, db: Session = Depends(get_db),
                   _: Usuario = Depends(get_current_user)):
    regla = db.get(ReglaClasificacion, regla_id)
    if regla is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no existe")
    db.delete(regla)
    db.commit()

@router.put("/{regla_id}", response_model=ReglaOut)
def editar_regla(regla_id: int, data: ReglaCreate, db: Session = Depends(get_db),
                 _: Usuario = Depends(get_current_user)):
    regla = db.get(ReglaClasificacion, regla_id)
    if regla is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no existe")
    # cliente_id no se reasigna: la regla queda en su cliente original.
    regla.cedula = data.cedula
    regla.cabys = data.cabys
    regla.rol = data.rol
    regla.clasificacion = data.clasificacion
    regla.sub_clasificacion = data.sub_clasificacion
    db.commit()
    db.refresh(regla)
    return regla
