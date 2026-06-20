from pathlib import Path
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.auth.security import hash_password
from sqlalchemy import select

FIXT = Path(__file__).parent / "fixtures"

def _token(client, db_session):
    db_session.add(Usuario(nombre="ing", password_hash=hash_password("clave12345"), es_admin=True))
    db_session.commit()
    return client.post("/auth/login", data={"username": "ing", "password": "clave12345"}).json()["access_token"]

def _cliente_agrofinca(db_session):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c

def _subir(client, token, path):
    with open(path, "rb") as fh:
        return client.post("/api/ingesta",
                           files={"archivo": (path.name, fh, "application/xml")},
                           headers={"Authorization": f"Bearer {token}"})

def test_ingesta_compra_guarda_con_rol_y_periodo(client, db_session):
    token = _token(client, db_session)
    cli = _cliente_agrofinca(db_session)
    r = _subir(client, token, FIXT / "fe_almacen_leon.xml")
    assert r.status_code == 200
    body = r.json()
    assert body["rol"] == "compra" and body["nuevo"] is True
    comp = db_session.scalar(select(Comprobante).where(Comprobante.clave == body["clave"]))
    assert comp is not None
    assert comp.cliente_id == cli.id
    assert comp.rol == "compra"
    assert comp.periodo == "202605"
    assert comp.lineas[0].tarifa_label == "13%"

def test_ingesta_venta_por_emisor(client, db_session):
    token = _token(client, db_session)
    _cliente_agrofinca(db_session)
    r = _subir(client, token, FIXT / "venta_nosujeto.xml")
    assert r.status_code == 200
    assert r.json()["rol"] == "venta"

def test_ingesta_idempotente_por_clave(client, db_session):
    token = _token(client, db_session)
    _cliente_agrofinca(db_session)
    _subir(client, token, FIXT / "fe_almacen_leon.xml")
    r2 = _subir(client, token, FIXT / "fe_almacen_leon.xml")
    assert r2.json()["nuevo"] is False
    comps = db_session.scalars(select(Comprobante).where(
        Comprobante.clave == "50604052600310103004200100001010000324943131803899")).all()
    assert len(comps) == 1   # no duplica

def test_ingesta_sin_token_401(client):
    with open(FIXT / "fe_almacen_leon.xml", "rb") as fh:
        r = client.post("/api/ingesta", files={"archivo": ("x.xml", fh, "application/xml")})
    assert r.status_code == 401

def test_ingesta_idempotente_no_duplica_lineas(client, db_session):
    token = _token(client, db_session)
    _cliente_agrofinca(db_session)
    _subir(client, token, FIXT / "fe_almacen_leon.xml")
    _subir(client, token, FIXT / "fe_almacen_leon.xml")
    from sqlalchemy import select
    comp = db_session.scalar(select(Comprobante).where(
        Comprobante.clave == "50604052600310103004200100001010000324943131803899"))
    assert len(comp.lineas) == 1   # la reingesta no deja líneas huérfanas

def test_ingesta_omite_mensaje_hacienda(client, db_session):
    token = _token(client, db_session)
    r = _subir(client, token, FIXT / "mensaje_hacienda.xml")
    assert r.status_code == 200
    assert r.json()["omitido"] is True

def test_ingesta_xml_invalido_422(client, db_session):
    token = _token(client, db_session)
    r = client.post("/api/ingesta",
                    files={"archivo": ("malo.xml", b"esto no es xml", "application/xml")},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422
