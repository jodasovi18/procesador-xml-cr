import io
import zipfile
import pytest
from zipfile import BadZipFile
from pathlib import Path
from sqlalchemy import select
from app.models.cliente import Cliente
from app.motor.ingesta_lote import _entradas_zip, ingest_lote
from app.models.comprobante import Comprobante

FIXT = Path(__file__).parent / "fixtures"

def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()

def test_entradas_zip_filtra_solo_xml():
    z = _zip_bytes({
        "sub/fac.xml": b"<x/>",
        "nota.txt": b"hola",
        "__MACOSX/._fac.xml": b"junk",
        "raiz.xml": b"<y/>",
    })
    nombres = sorted(n for n, _ in _entradas_zip(z))
    assert nombres == ["raiz.xml", "sub/fac.xml"]

def test_entradas_zip_corrupto_lanza_badzip():
    with pytest.raises(BadZipFile):
        _entradas_zip(b"no soy un zip")

def test_entradas_zip_tope_entradas():
    z = _zip_bytes({f"f{i}.xml": b"<x/>" for i in range(3)})
    with pytest.raises(ValueError):
        _entradas_zip(z, max_entradas=2)

def test_entradas_zip_tope_bytes():
    z = _zip_bytes({"a.xml": b"x" * 100, "b.xml": b"y" * 100})  # 200 bytes descomprimidos
    with pytest.raises(ValueError):
        _entradas_zip(z, max_bytes=150)


def _cliente(db):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db.add(c); db.commit(); db.refresh(c)
    return c

def _leer(nombre):
    return (nombre, (FIXT / nombre).read_bytes())

def test_ingest_lote_exito_parcial(db_session):
    _cliente(db_session)
    archivos = [
        _leer("fe_almacen_leon.xml"),
        _leer("mensaje_hacienda.xml"),
        ("roto.xml", b"<noEsValido"),
    ]
    res = ingest_lote(db_session, archivos)
    assert res["total"] == 3
    assert res["nuevos"] == 1
    assert res["omitidos"] == 1
    assert res["errores"] == 1
    estados = {a["archivo"]: a["estado"] for a in res["archivos"]}
    assert estados["fe_almacen_leon.xml"] == "nuevo"
    assert estados["mensaje_hacienda.xml"] == "omitido"
    assert estados["roto.xml"] == "error"
    assert db_session.scalar(select(Comprobante)) is not None

def test_ingest_lote_idempotente(db_session):
    _cliente(db_session)
    archivos = [_leer("fe_almacen_leon.xml")]
    ingest_lote(db_session, archivos)
    res2 = ingest_lote(db_session, archivos)
    assert res2["actualizados"] == 1
    assert res2["archivos"][0]["estado"] == "actualizado"

def test_ingest_lote_zip(db_session):
    _cliente(db_session)
    z = _zip_bytes({
        "carpeta/fe_almacen_leon.xml": (FIXT / "fe_almacen_leon.xml").read_bytes(),
        "mensaje_hacienda.xml": (FIXT / "mensaje_hacienda.xml").read_bytes(),
    })
    res = ingest_lote(db_session, [("mayo.zip", z)])
    assert res["total"] == 2
    assert res["nuevos"] == 1
    assert res["omitidos"] == 1

def test_ingest_lote_zip_corrupto(db_session):
    res = ingest_lote(db_session, [("malo.zip", b"no soy un zip")])
    assert res["total"] == 1
    assert res["errores"] == 1
    assert res["archivos"][0]["estado"] == "error"
