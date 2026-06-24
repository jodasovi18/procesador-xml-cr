from pathlib import Path
from sqlalchemy import select
from app.models.agent_token import AgentToken
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.auth.security import hash_password
from app.auth.tokens import generar_token, hash_token

FIXT = Path(__file__).parent / "fixtures"


def _cliente(db):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db.add(c); db.commit(); db.refresh(c)
    return c


def _files():
    return [("archivos", ("fe.xml", (FIXT / "fe_almacen_leon.xml").read_bytes(), "application/xml"))]


def test_persistir_agent_token(db_session):
    db_session.add(AgentToken(token_hash="a" * 64, label="PC-contador"))
    db_session.commit()
    t = db_session.scalar(select(AgentToken))
    assert t.token_hash == "a" * 64
    assert t.label == "PC-contador"
    assert t.created_at is not None


def test_tokens_helpers():
    assert len(generar_token()) >= 32
    assert generar_token() != generar_token()
    assert hash_token("abc") == hash_token("abc")
    assert len(hash_token("abc")) == 64


def test_ingesta_lote_acepta_agent_token(client, db_session):
    db_session.add(AgentToken(token_hash=hash_token("MITOKEN"), label="x")); db_session.commit()
    _cliente(db_session)
    r = client.post("/api/ingesta/lote", files=_files(), headers={"Authorization": "Bearer MITOKEN"})
    assert r.status_code == 200
    assert r.json()["nuevos"] == 1


def test_ingesta_lote_bearer_invalido_401(client):
    r = client.post("/api/ingesta/lote", files=_files(), headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


def test_ingesta_lote_token_revocado_401(client, db_session):
    at = AgentToken(token_hash=hash_token("REVOK"), label="x")
    db_session.add(at); db_session.commit()
    db_session.delete(at); db_session.commit()
    r = client.post("/api/ingesta/lote", files=_files(), headers={"Authorization": "Bearer REVOK"})
    assert r.status_code == 401


def test_ingesta_lote_jwt_usuario_borrado_401(client, db_session):
    db_session.add(Usuario(nombre="tmp", password_hash=hash_password("clave12345"), es_admin=True))
    db_session.commit()
    tok = client.post("/auth/login", data={"username": "tmp", "password": "clave12345"}).json()["access_token"]
    u = db_session.scalar(select(Usuario).where(Usuario.nombre == "tmp"))
    db_session.delete(u); db_session.commit()
    r = client.post("/api/ingesta/lote", files=_files(), headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401


def test_ingesta_single_acepta_agent_token(client, db_session):
    db_session.add(AgentToken(token_hash=hash_token("TOKSINGLE"), label="x")); db_session.commit()
    _cliente(db_session)
    with open(FIXT / "fe_almacen_leon.xml", "rb") as fh:
        r = client.post("/api/ingesta",
                        files={"archivo": ("fe.xml", fh, "application/xml")},
                        headers={"Authorization": "Bearer TOKSINGLE"})
    assert r.status_code == 200
