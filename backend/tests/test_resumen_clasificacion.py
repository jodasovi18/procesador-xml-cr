from pathlib import Path
from decimal import Decimal
from sqlalchemy import select
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.models.regla_clasificacion import ReglaClasificacion
from app.auth.security import hash_password
from app.motor.resumen import build_resumen

FIXT = Path(__file__).parent / "fixtures"
PROV = "3101030042"  # emisor de fe_almacen_leon.xml

def _token(client, db_session):
    db_session.add(Usuario(nombre="clas", password_hash=hash_password("clave12345"), es_admin=True))
    db_session.commit()
    return client.post("/auth/login", data={"username": "clas", "password": "clave12345"}).json()["access_token"]

def _cliente(db_session):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c

def _ingest_leon(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    with open(FIXT / "fe_almacen_leon.xml", "rb") as fh:
        client.post("/api/ingesta", files={"archivo": ("x.xml", fh, "application/xml")},
                    headers={"Authorization": f"Bearer {token}"})
    comp = db_session.scalar(select(Comprobante).where(Comprobante.cliente_id == cli.id))
    return cli, comp

def test_resumen_sin_reglas_sin_cambios(client, db_session):
    cli, comp = _ingest_leon(client, db_session)
    res = build_resumen(db_session, cli.id, comp.periodo, "compra")
    assert res["Bienes 13%"]["base"] == Decimal("1858.40")
    assert res["Bienes 13%"]["iva"] == Decimal("241.59")
    assert "No Deducibles" not in res

def test_resumen_no_deducible_segregado(client, db_session):
    cli, comp = _ingest_leon(client, db_session)
    db_session.add(ReglaClasificacion(cliente_id=cli.id, cedula=PROV, clasificacion="No Deducibles"))
    db_session.commit()
    res = build_resumen(db_session, cli.id, comp.periodo, "compra")
    assert "Bienes 13%" not in res
    assert res["No Deducibles"]["base"] == Decimal("1858.40")
    assert res["No Deducibles"]["iva"] == Decimal("241.59")

def test_resumen_combustibles_a_no_sujeto(client, db_session):
    cli, comp = _ingest_leon(client, db_session)
    db_session.add(ReglaClasificacion(cliente_id=cli.id, cedula=PROV,
                                      clasificacion="Gastos", sub_clasificacion="Combustibles"))
    db_session.commit()
    res = build_resumen(db_session, cli.id, comp.periodo, "compra")
    assert "Bienes 13%" not in res
    assert res["No Sujeto"]["base"] == Decimal("1858.40")
    assert res["No Sujeto"]["iva"] == Decimal("0")
