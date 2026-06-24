from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models.usuario import Usuario
from app.models.agent_token import AgentToken
from app.auth.tokens import hash_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Usuario:
    cred_exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail="Credenciales inválidas",
                             headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        if sub is None:
            raise cred_exc
        user_id = int(sub)
    except (JWTError, ValueError):
        raise cred_exc
    usuario = db.get(Usuario, user_id)
    if usuario is None:
        raise cred_exc
    return usuario


def get_actor(token: str = Depends(oauth2_scheme),
              db: Session = Depends(get_db)) -> "Usuario | AgentToken":
    """Acepta un JWT de usuario o un token de agente. Usar solo en rutas de ingesta."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        if sub is not None:
            usuario = db.get(Usuario, int(sub))
            if usuario is not None:
                return usuario
    except (JWTError, ValueError):
        pass
    at = db.scalar(select(AgentToken).where(AgentToken.token_hash == hash_token(token)))
    if at is not None:
        return at
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Credenciales inválidas",
                        headers={"WWW-Authenticate": "Bearer"})


def requiere_admin(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    if not usuario.es_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere admin")
    return usuario
