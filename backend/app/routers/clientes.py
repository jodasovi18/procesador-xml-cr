from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.schemas.cliente import ClienteCreate, ClienteOut

router = APIRouter(prefix="/api/clientes", tags=["clientes"])

@router.post("", response_model=ClienteOut, status_code=status.HTTP_201_CREATED)
def crear_cliente(data: ClienteCreate, db: Session = Depends(get_db),
                  _: Usuario = Depends(get_current_user)):
    cliente = Cliente(**data.model_dump())
    db.add(cliente)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Ya existe un cliente con esa cédula")
    db.refresh(cliente)
    return cliente

@router.get("", response_model=list[ClienteOut])
def listar_clientes(db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    return list(db.scalars(select(Cliente).order_by(Cliente.nombre)))
