from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.motor.d150 import build_d150, d150_ovi, jsonify_preciso

router = APIRouter(prefix="/api/d150", tags=["d150"])

@router.get("")
def d150(cliente_id: int, periodo: str, db: Session = Depends(get_db),
         _: Usuario = Depends(get_current_user)):
    preciso = build_d150(db, cliente_id, periodo)
    return {"preciso": jsonify_preciso(preciso), "ovi": d150_ovi(preciso)}
