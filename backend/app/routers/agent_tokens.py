from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import requiere_admin
from app.models.usuario import Usuario
from app.models.agent_token import AgentToken
from app.auth.tokens import generar_token, hash_token
from app.schemas.agent_token import AgentTokenCreate, AgentTokenCreated, AgentTokenOut

router = APIRouter(prefix="/api/agent-tokens", tags=["agent-tokens"])

@router.post("", response_model=AgentTokenCreated, status_code=status.HTTP_201_CREATED)
def crear(data: AgentTokenCreate, db: Session = Depends(get_db),
          _: Usuario = Depends(requiere_admin)):
    token = generar_token()
    at = AgentToken(token_hash=hash_token(token), label=data.label)
    db.add(at)
    db.commit()
    db.refresh(at)
    return AgentTokenCreated(id=at.id, label=at.label, token=token)

@router.get("", response_model=list[AgentTokenOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(requiere_admin)):
    return list(db.scalars(select(AgentToken).order_by(AgentToken.id)))

@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revocar(token_id: int, db: Session = Depends(get_db),
            _: Usuario = Depends(requiere_admin)):
    at = db.get(AgentToken, token_id)
    if at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no existe")
    db.delete(at)
    db.commit()
