from app.models.usuario import Usuario
from app.auth.security import hash_password

def _crear_usuario(db, nombre="ana", password="secreta123", es_admin=True):
    u = Usuario(nombre=nombre, password_hash=hash_password(password), es_admin=es_admin)
    db.add(u); db.commit(); db.refresh(u)
    return u

def test_login_correcto_devuelve_token(client, db_session):
    _crear_usuario(db_session)
    resp = client.post("/auth/login", data={"username": "ana", "password": "secreta123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"].count(".") == 2  # estructura JWT: header.payload.signature

def test_login_password_incorrecta_401(client, db_session):
    _crear_usuario(db_session)
    resp = client.post("/auth/login", data={"username": "ana", "password": "mala"})
    assert resp.status_code == 401
