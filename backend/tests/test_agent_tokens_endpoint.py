from pathlib import Path
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.auth.security import hash_password

FIXT = Path(__file__).parent / "fixtures"

def _login(client, db_session, nombre, es_admin):
    db_session.add(Usuario(nombre=nombre, password_hash=hash_password("clave12345"), es_admin=es_admin))
    db_session.commit()
    return client.post("/auth/login", data={"username": nombre, "password": "clave12345"}).json()["access_token"]

def _auth(t):
    return {"Authorization": f"Bearer {t}"}

def _cliente(db):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db.add(c); db.commit(); db.refresh(c)
    return c

def _files():
    return [("archivos", ("fe.xml", (FIXT / "fe_almacen_leon.xml").read_bytes(), "application/xml"))]

def test_crear_y_usar_token(client, db_session):
    adm = _login(client, db_session, "adm", True)
    r = client.post("/api/agent-tokens", json={"label": "PC"}, headers=_auth(adm))
    assert r.status_code == 201
    plano = r.json()["token"]
    assert r.json()["label"] == "PC"
    _cliente(db_session)
    ri = client.post("/api/ingesta/lote", files=_files(), headers={"Authorization": f"Bearer {plano}"})
    assert ri.status_code == 200

def test_listar_no_expone_token(client, db_session):
    adm = _login(client, db_session, "adm", True)
    client.post("/api/agent-tokens", json={"label": "PC"}, headers=_auth(adm))
    lst = client.get("/api/agent-tokens", headers=_auth(adm))
    assert lst.status_code == 200 and len(lst.json()) == 1
    assert "token" not in lst.json()[0]
    assert "token_hash" not in lst.json()[0]

def test_revocar_token(client, db_session):
    adm = _login(client, db_session, "adm", True)
    c = client.post("/api/agent-tokens", json={"label": "PC"}, headers=_auth(adm))
    plano, tid = c.json()["token"], c.json()["id"]
    assert client.delete(f"/api/agent-tokens/{tid}", headers=_auth(adm)).status_code == 204
    r = client.post("/api/ingesta/lote", files=_files(), headers={"Authorization": f"Bearer {plano}"})
    assert r.status_code == 401

def test_crear_no_admin_403(client, db_session):
    user = _login(client, db_session, "user", False)
    assert client.post("/api/agent-tokens", json={"label": "PC"}, headers=_auth(user)).status_code == 403

def test_agent_tokens_sin_token_401(client):
    assert client.get("/api/agent-tokens").status_code == 401
