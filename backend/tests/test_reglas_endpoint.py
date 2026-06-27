from pathlib import Path
from sqlalchemy import select
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.auth.security import hash_password

FIXT = Path(__file__).parent / "fixtures"

def _token(client, db_session):
    db_session.add(Usuario(nombre="reg", password_hash=hash_password("clave12345"), es_admin=True))
    db_session.commit()
    return client.post("/auth/login", data={"username": "reg", "password": "clave12345"}).json()["access_token"]

def _cliente(db_session):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c

def _auth(t):
    return {"Authorization": f"Bearer {t}"}

def test_crear_y_listar_regla(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    payload = {"cliente_id": cli.id, "cedula": "3101030042", "clasificacion": "No Deducibles"}
    r = client.post("/api/reglas", json=payload, headers=_auth(token))
    assert r.status_code == 201
    assert r.json()["clasificacion"] == "No Deducibles"
    assert r.json()["cedula"] == "3101030042"
    lst = client.get(f"/api/reglas?cliente_id={cli.id}", headers=_auth(token))
    assert lst.status_code == 200
    assert len(lst.json()) == 1

def test_crear_regla_clasificacion_invalida_422(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    payload = {"cliente_id": cli.id, "cedula": "3101030042", "clasificacion": "Inexistente"}
    assert client.post("/api/reglas", json=payload, headers=_auth(token)).status_code == 422

def test_crear_regla_sin_ced_ni_cabys_422(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    payload = {"cliente_id": cli.id, "clasificacion": "Compras"}
    assert client.post("/api/reglas", json=payload, headers=_auth(token)).status_code == 422

def test_reglas_sin_token_401(client):
    assert client.get("/api/reglas?cliente_id=1").status_code == 401
    r = client.post("/api/reglas", json={"cliente_id": 1, "cedula": "1", "clasificacion": "Compras"})
    assert r.status_code == 401

def test_endpoint_resumen_clasificacion(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    with open(FIXT / "fe_almacen_leon.xml", "rb") as fh:
        client.post("/api/ingesta", files={"archivo": ("x.xml", fh, "application/xml")}, headers=_auth(token))
    comp = db_session.scalar(select(Comprobante).where(Comprobante.cliente_id == cli.id))
    client.post("/api/reglas", json={"cliente_id": cli.id, "cedula": "3101030042", "clasificacion": "Compras"}, headers=_auth(token))
    r = client.get(f"/api/resumen/clasificacion?cliente_id={cli.id}&periodo={comp.periodo}&rol=compra", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["Compras"]["13%"]["base"] == "1858.40000"
    assert body["Compras"]["13%"]["iva"] == "241.59000"

def test_endpoint_resumen_clasificacion_sin_token_401(client):
    assert client.get("/api/resumen/clasificacion?cliente_id=1&periodo=202605&rol=compra").status_code == 401

def test_crear_regla_cliente_inexistente_422(client, db_session):
    token = _token(client, db_session)
    payload = {"cliente_id": 999999, "cedula": "3101030042", "clasificacion": "Compras"}
    assert client.post("/api/reglas", json=payload, headers=_auth(token)).status_code == 422

def test_editar_regla(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    r = client.post("/api/reglas", json={"cliente_id": cli.id, "cedula": "3101030042", "clasificacion": "Compras"}, headers=_auth(token))
    rid = r.json()["id"]
    upd = {"cliente_id": cli.id, "cabys": "2310100000000", "clasificacion": "No Deducibles", "sub_clasificacion": "Combustibles"}
    r2 = client.put(f"/api/reglas/{rid}", json=upd, headers=_auth(token))
    assert r2.status_code == 200
    body = r2.json()
    assert body["id"] == rid
    assert body["clasificacion"] == "No Deducibles"
    assert body["cabys"] == "2310100000000"
    assert body["sub_clasificacion"] == "Combustibles"
    assert body["cedula"] is None

def test_editar_regla_inexistente_404(client, db_session):
    token = _token(client, db_session); _cliente(db_session)
    upd = {"cliente_id": 1, "cedula": "3101030042", "clasificacion": "Compras"}
    assert client.put("/api/reglas/999999", json=upd, headers=_auth(token)).status_code == 404

def test_editar_regla_clasificacion_invalida_422(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    rid = client.post("/api/reglas", json={"cliente_id": cli.id, "cedula": "3101030042", "clasificacion": "Compras"}, headers=_auth(token)).json()["id"]
    upd = {"cliente_id": cli.id, "cedula": "3101030042", "clasificacion": "Inexistente"}
    assert client.put(f"/api/reglas/{rid}", json=upd, headers=_auth(token)).status_code == 422

def test_editar_regla_sin_ced_ni_cabys_422(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    rid = client.post("/api/reglas", json={"cliente_id": cli.id, "cedula": "3101030042", "clasificacion": "Compras"}, headers=_auth(token)).json()["id"]
    upd = {"cliente_id": cli.id, "clasificacion": "Compras"}
    assert client.put(f"/api/reglas/{rid}", json=upd, headers=_auth(token)).status_code == 422

def test_editar_regla_sin_token_401(client):
    assert client.put("/api/reglas/1", json={"cliente_id": 1, "cedula": "1", "clasificacion": "Compras"}).status_code == 401

def test_eliminar_regla(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    rid = client.post("/api/reglas", json={"cliente_id": cli.id, "cedula": "3101030042", "clasificacion": "Compras"}, headers=_auth(token)).json()["id"]
    assert client.delete(f"/api/reglas/{rid}", headers=_auth(token)).status_code == 204
    lst = client.get(f"/api/reglas?cliente_id={cli.id}", headers=_auth(token)).json()
    assert all(r["id"] != rid for r in lst)

def test_eliminar_regla_inexistente_404(client, db_session):
    token = _token(client, db_session); _cliente(db_session)
    assert client.delete("/api/reglas/999999", headers=_auth(token)).status_code == 404

def test_eliminar_regla_sin_token_401(client):
    assert client.delete("/api/reglas/1").status_code == 401
