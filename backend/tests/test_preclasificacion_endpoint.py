from datetime import datetime
from decimal import Decimal
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante, LineaComprobante
from app.auth.security import hash_password


def _token(client, db):
    db.add(Usuario(nombre="pre", password_hash=hash_password("clave12345"), es_admin=True))
    db.commit()
    return client.post("/auth/login", data={"username": "pre", "password": "clave12345"}).json()["access_token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _cliente(db):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db.add(c); db.commit(); db.refresh(c)
    return c


def _comp(db, cliente_id, cabys, detalle, base):
    comp = Comprobante(cliente_id=cliente_id, clave=f"k{cabys}{db.query(Comprobante).count()}",
                       tipo_doc="FacturaElectronica", consecutivo="1", fecha=datetime(2026, 5, 1),
                       periodo="202605", rol="compra", emisor_cedula="3101030042", emisor_nombre="Insumos",
                       receptor_cedula="3102858282", receptor_nombre="Agrofinca", xml_raw="<x/>")
    db.add(comp); db.flush()
    db.add(LineaComprobante(comprobante_id=comp.id, numero=1, cabys=cabys, detalle=detalle,
                            base_imponible=Decimal(base), tarifa_label="13%", tipo="Bienes", iva_monto=Decimal("0")))
    db.commit()


def test_preclasificacion_ok(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    _comp(db_session, cli.id, "2310100000000", "Fertilizante", "100")
    r = client.get(f"/api/preclasificacion?cliente_id={cli.id}&periodo=202605&rol=compra&por=cabys", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["clave"] == "2310100000000"
    assert body[0]["lineas"] == 1
    assert Decimal(body[0]["base"]) == Decimal("100")  # string del Decimal, comparado por valor

def test_preclasificacion_por_invalido_422(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    r = client.get(f"/api/preclasificacion?cliente_id={cli.id}&periodo=202605&rol=compra&por=otro", headers=_auth(token))
    assert r.status_code == 422

def test_preclasificacion_rol_invalido_422(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    r = client.get(f"/api/preclasificacion?cliente_id={cli.id}&periodo=202605&rol=otro&por=cabys", headers=_auth(token))
    assert r.status_code == 422

def test_preclasificacion_sin_token_401(client):
    assert client.get("/api/preclasificacion?cliente_id=1&periodo=202605&rol=compra").status_code == 401
