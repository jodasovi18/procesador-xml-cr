from pathlib import Path
from decimal import Decimal
from sqlalchemy import select
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.auth.security import hash_password
from app.motor.resumen import build_resumen

FIXT = Path(__file__).parent / "fixtures"

def _token(client, db_session):
    db_session.add(Usuario(nombre="res", password_hash=hash_password("clave12345"), es_admin=True))
    db_session.commit()
    return client.post("/auth/login", data={"username": "res", "password": "clave12345"}).json()["access_token"]

def _cliente(db_session):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c

def _subir(client, token, path):
    with open(path, "rb") as fh:
        return client.post("/api/ingesta", files={"archivo": (path.name, fh, "application/xml")},
                           headers={"Authorization": f"Bearer {token}"})

def test_resumen_compra_bienes_13(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    _subir(client, token, FIXT / "fe_almacen_leon.xml")
    comp = db_session.scalar(select(Comprobante).where(Comprobante.cliente_id == cli.id))
    res = build_resumen(db_session, cli.id, comp.periodo, "compra")
    assert set(res.keys()) == {"Bienes 13%"}
    assert res["Bienes 13%"]["base"] == Decimal("1858.40")
    assert res["Bienes 13%"]["iva"] == Decimal("241.59")

def test_resumen_venta_no_sujeto(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    _subir(client, token, FIXT / "venta_nosujeto.xml")
    comp = db_session.scalar(select(Comprobante).where(Comprobante.cliente_id == cli.id))
    res = build_resumen(db_session, cli.id, comp.periodo, "venta")
    assert "No Sujeto" in res
    assert res["No Sujeto"]["base"] == Decimal("137650")   # 62200+31100+8850+35500
    assert res["No Sujeto"]["iva"] == Decimal("0")
