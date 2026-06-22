from decimal import Decimal
from sqlalchemy import select
from app.models.cliente import Cliente
from app.models.entrada_manual import EntradaManual

def _cliente(db):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db.add(c); db.commit(); db.refresh(c)
    return c

def test_persistir_entrada_manual(db_session):
    cli = _cliente(db_session)
    db_session.add(EntradaManual(
        cliente_id=cli.id, periodo="202605", rol="compra", descripcion="Subasta ganado",
        monto=Decimal("2000"), tarifa=Decimal("13"), no_sujeto=False, deducible=False))
    db_session.commit()
    e = db_session.scalar(select(EntradaManual).where(EntradaManual.cliente_id == cli.id))
    assert e.rol == "compra"
    assert e.monto == Decimal("2000")
    assert e.tarifa == Decimal("13")
    assert e.deducible is False
    assert e.no_sujeto is False
    assert e.descripcion == "Subasta ganado"

from app.models.usuario import Usuario
from app.auth.security import hash_password

def _token(client, db_session):
    db_session.add(Usuario(nombre="em", password_hash=hash_password("clave12345"), es_admin=True))
    db_session.commit()
    return client.post("/auth/login", data={"username": "em", "password": "clave12345"}).json()["access_token"]

def _auth(t):
    return {"Authorization": f"Bearer {t}"}

def test_crear_listar_eliminar_entrada(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    payload = {"cliente_id": cli.id, "periodo": "202605", "rol": "compra",
               "descripcion": "Subasta", "monto": "2000", "tarifa": "13", "deducible": False}
    r = client.post("/api/entradas-manuales", json=payload, headers=_auth(token))
    assert r.status_code == 201
    eid = r.json()["id"]
    assert r.json()["rol"] == "compra"
    lst = client.get(f"/api/entradas-manuales?cliente_id={cli.id}&periodo=202605", headers=_auth(token))
    assert lst.status_code == 200 and len(lst.json()) == 1
    d = client.delete(f"/api/entradas-manuales/{eid}", headers=_auth(token))
    assert d.status_code == 204
    lst2 = client.get(f"/api/entradas-manuales?cliente_id={cli.id}&periodo=202605", headers=_auth(token))
    assert len(lst2.json()) == 0

def test_crear_entrada_rol_invalido_422(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    payload = {"cliente_id": cli.id, "periodo": "202605", "rol": "otro", "monto": "10", "tarifa": "13"}
    assert client.post("/api/entradas-manuales", json=payload, headers=_auth(token)).status_code == 422

def test_entradas_sin_token_401(client):
    assert client.get("/api/entradas-manuales?cliente_id=1&periodo=202605").status_code == 401
