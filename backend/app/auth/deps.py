from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Usuario:
    cred_exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail="Credenciales inválidas",
                             headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        nombre = payload.get("sub")
        if nombre is None:
            raise cred_exc
    except JWTError:
        raise cred_exc
    usuario = db.scalar(select(Usuario).where(Usuario.nombre == nombre))
    if usuario is None:
        raise cred_exc
    return usuario
