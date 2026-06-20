from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
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
