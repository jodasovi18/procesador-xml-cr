from app.models.usuario import Usuario
from app.auth.security import hash_password

def _token(client, db_session):
    db_session.add(Usuario(nombre="cata", password_hash=hash_password("clave12345"), es_admin=True))
    db_session.commit()
    r = client.post("/auth/login", data={"username": "cata", "password": "clave12345"})
    return r.json()["access_token"]

def _auth(token):
    return {"Authorization": f"Bearer {token}"}

def test_crear_y_listar_cliente(client, db_session):
    token = _token(client, db_session)
    nuevo = {"cedula": "3102858282", "nombre": "Agrofinca La Flor S&C Ltda",
             "tipo_cedula": "juridica", "regimen": "tradicional"}
    r = client.post("/api/clientes", json=nuevo, headers=_auth(token))
    assert r.status_code == 201
    assert r.json()["cedula"] == "3102858282"

    r2 = client.get("/api/clientes", headers=_auth(token))
    assert r2.status_code == 200
    cedulas = [c["cedula"] for c in r2.json()]
    assert "3102858282" in cedulas

def test_cedula_duplicada_409(client, db_session):
    token = _token(client, db_session)
    nuevo = {"cedula": "3101030042", "nombre": "Almacén León Rojas",
             "tipo_cedula": "juridica", "regimen": "tradicional"}
    assert client.post("/api/clientes", json=nuevo, headers=_auth(token)).status_code == 201
    dup = client.post("/api/clientes", json=nuevo, headers=_auth(token))
    assert dup.status_code == 409

def test_listar_sin_token_401(client):
    assert client.get("/api/clientes").status_code == 401


def test_crear_cliente_tipo_cedula_invalido_422(client, db_session):
    token = _token(client, db_session)
    payload = {"cedula": "3101777777", "nombre": "X S.A.", "tipo_cedula": "foo", "regimen": "tradicional"}
    assert client.post("/api/clientes", json=payload, headers=_auth(token)).status_code == 422


def test_crear_cliente_regimen_invalido_422(client, db_session):
    token = _token(client, db_session)
    payload = {"cedula": "3101777778", "nombre": "Y S.A.", "tipo_cedula": "juridica", "regimen": "foo"}
    assert client.post("/api/clientes", json=payload, headers=_auth(token)).status_code == 422


def test_crear_cliente_dimex_simplificado_201(client, db_session):
    token = _token(client, db_session)
    payload = {"cedula": "155812345678", "nombre": "Z", "tipo_cedula": "dimex", "regimen": "simplificado"}
    r = client.post("/api/clientes", json=payload, headers=_auth(token))
    assert r.status_code == 201
    assert r.json()["tipo_cedula"] == "dimex"
    assert r.json()["regimen"] == "simplificado"
