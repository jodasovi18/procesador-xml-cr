import io
import zipfile
import pytest
from zipfile import BadZipFile
from pathlib import Path
from sqlalchemy import select
from app.models.cliente import Cliente
from app.motor.ingesta_lote import _entradas_zip

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
