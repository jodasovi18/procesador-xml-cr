from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.usuario import Usuario
from app.auth.security import verify_password, create_access_token, hash_password
from app.schemas.auth import Token
from app.auth.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

# Hash fijo para igualar el tiempo de respuesta cuando el usuario no existe,
# evitando enumeración de usuarios por canal lateral de tiempo.
_DUMMY_HASH = hash_password("tiempo-constante")

@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.scalar(select(Usuario).where(Usuario.nombre == form.username))
    candidate_hash = usuario.password_hash if usuario else _DUMMY_HASH
    pwd_ok = verify_password(form.password, candidate_hash)
    if not usuario or not pwd_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Usuario o contraseña incorrectos",
                            headers={"WWW-Authenticate": "Bearer"})
    token = create_access_token(sub=usuario.nombre)
    return Token(access_token=token)

@router.get("/me")
def me(usuario: Usuario = Depends(get_current_user)):
    return {"id": usuario.id, "nombre": usuario.nombre, "es_admin": usuario.es_admin}
