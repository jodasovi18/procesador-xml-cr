from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.models.entrada_manual import EntradaManual
from app.schemas.entrada_manual import EntradaManualCreate, EntradaManualOut

router = APIRouter(prefix="/api/entradas-manuales", tags=["entradas-manuales"])

@router.post("", response_model=EntradaManualOut, status_code=status.HTTP_201_CREATED)
def crear(data: EntradaManualCreate, db: Session = Depends(get_db),
          _: Usuario = Depends(get_current_user)):
    e = EntradaManual(**data.model_dump())
    db.add(e)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="cliente_id inválido")
    db.refresh(e)
    return e

@router.get("", response_model=list[EntradaManualOut])
def listar(cliente_id: int, periodo: str, rol: str | None = None,
           db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    stmt = select(EntradaManual).where(
        EntradaManual.cliente_id == cliente_id, EntradaManual.periodo == periodo)
    if rol is not None:
        stmt = stmt.where(EntradaManual.rol == rol)
    return list(db.scalars(stmt.order_by(EntradaManual.id)))

@router.delete("/{entrada_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(entrada_id: int, db: Session = Depends(get_db),
             _: Usuario = Depends(get_current_user)):
    e = db.get(EntradaManual, entrada_id)
    if e is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no existe")
    db.delete(e)
    db.commit()
