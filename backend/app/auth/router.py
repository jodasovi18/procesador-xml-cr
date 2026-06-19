from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.usuario import Usuario
from app.auth.security import verify_password, create_access_token
from app.schemas.auth import Token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.scalar(select(Usuario).where(Usuario.nombre == form.username))
    if not usuario or not verify_password(form.password, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Usuario o contraseña incorrectos")
    token = create_access_token(sub=usuario.nombre)
    return Token(access_token=token)
