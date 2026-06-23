# Subida masiva (ZIP / múltiples XML) — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subir un ZIP (o varios XML) de una vez y procesarlos con la ingesta existente, con éxito parcial (un archivo malo no aborta el lote) y un reporte por archivo, vía `POST /api/ingesta/lote`.

**Architecture:** `motor/ingesta_lote.py` reutiliza `ingest_xml` por archivo: `_entradas_zip` expande los `.xml` de un ZIP (con topes anti-zip-bomb); `ingest_lote` itera, procesa cada XML en un savepoint (`db.begin_nested()`) para éxito parcial, y arma un resumen + detalle. El endpoint single-file actual queda igual.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, pytest, `zipfile` (stdlib). Postgres local 5433.

> **Diseño:** `docs/plans/2026-06-22-subida-masiva-design.md`.

---

## Contexto y entorno (CRÍTICO)

- **Venv en worktree:** no hay `.venv` propio. Correr con `C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\backend\.venv\Scripts\python.exe` y `PYTHONPATH` al `backend\` del worktree, desde el `backend\` del worktree. Nunca el `python` pelado.
  - PowerShell: `$env:PYTHONPATH="<worktree>\backend"; & "C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\backend\.venv\Scripts\python.exe" -m pytest -q`
- Tests usan `Base.metadata.create_all` (sin migraciones). Suite baseline en esta rama (main con 1B-6): **65 pruebas verdes**.
- Reutiliza: `ingest_xml(db, xml_bytes) -> dict` en `motor/ingesta.py` (devuelve `{clave, rol, cliente_id, nuevo, omitido}`; para no-comprobante `{clave: None, omitido: True, motivo}`; lanza `ParseError`/`ValueError`/`InvalidOperation`). Router pattern: `routers/ingesta.py`.
- Fixtures en `backend/tests/fixtures/`: `fe_almacen_leon.xml` (compra real, receptor Agrofinca `3102858282`), `mensaje_hacienda.xml` (MensajeHacienda → omitido), `venta_nosujeto.xml`.

## File Structure

- Create: `backend/app/motor/ingesta_lote.py` — `_entradas_zip`, `ingest_lote`, `_ingest_uno`, `_resumen`, constantes de tope.
- Modify: `backend/app/routers/ingesta.py` — agregar `POST /api/ingesta/lote`.
- Test: `backend/tests/test_ingesta_lote.py`.

---

## Tarea 1: `_entradas_zip` (expansión de ZIP + topes)

**Files:**
- Create: `backend/app/motor/ingesta_lote.py`
- Test: `backend/tests/test_ingesta_lote.py` (nuevo)

- [ ] **Step 1: Escribir el test que falla** `backend/tests/test_ingesta_lote.py`

```python
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
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: pytest `tests/test_ingesta_lote.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.motor.ingesta_lote'`.

- [ ] **Step 3: Crear `backend/app/motor/ingesta_lote.py`**

```python
"""Subida masiva: expande ZIP a entradas .xml y procesa un lote reutilizando
ingest_xml, con éxito parcial (savepoint por archivo) y reporte por archivo."""
import io
import zipfile
from collections import Counter
from decimal import InvalidOperation
from xml.etree.ElementTree import ParseError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.motor.ingesta import ingest_xml

MAX_ENTRADAS_ZIP = 5000
MAX_BYTES_DESCOMPRIMIDO = 200 * 1024 * 1024  # 200 MB


def _entradas_zip(contenido: bytes, max_entradas: int = MAX_ENTRADAS_ZIP,
                  max_bytes: int = MAX_BYTES_DESCOMPRIMIDO) -> list[tuple[str, bytes]]:
    """Devuelve las entradas .xml de un ZIP (ignora directorios, no-.xml y __MACOSX).
    Lanza zipfile.BadZipFile si el ZIP es inválido, o ValueError si excede los topes."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as zf:
        infos = [i for i in zf.infolist()
                 if not i.is_dir()
                 and i.filename.lower().endswith(".xml")
                 and "__MACOSX" not in i.filename]
        if len(infos) > max_entradas:
            raise ValueError(f"el ZIP excede el máximo de {max_entradas} entradas")
        if sum(i.file_size for i in infos) > max_bytes:
            raise ValueError("el ZIP excede el tamaño descomprimido permitido")
        return [(i.filename, zf.read(i)) for i in infos]
```

- [ ] **Step 4: Correr, confirmar que PASA**

Run: pytest `tests/test_ingesta_lote.py -q`. Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(lote): _entradas_zip expande XML de un ZIP con topes anti-zip-bomb"
```

---

## Tarea 2: `ingest_lote` (orquestación con éxito parcial)

**Files:**
- Modify: `backend/app/motor/ingesta_lote.py`
- Test: `backend/tests/test_ingesta_lote.py` (agregar import + tests)

- [ ] **Step 1: Agregar el import y los tests que fallan** en `backend/tests/test_ingesta_lote.py`

Agregar al import existente:
```python
from app.motor.ingesta_lote import _entradas_zip, ingest_lote
from app.models.comprobante import Comprobante
```
Y agregar al final:
```python
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
    # el bueno quedó persistido pese al malo
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
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: pytest `tests/test_ingesta_lote.py -q`
Expected: FAIL — `ImportError: cannot import name 'ingest_lote'`.

- [ ] **Step 3: Agregar al final de `backend/app/motor/ingesta_lote.py`**

```python
def _ingest_uno(db: Session, nombre: str, contenido: bytes) -> dict:
    """Procesa un XML en un savepoint. Devuelve el dict de resultado por archivo."""
    try:
        with db.begin_nested():
            r = ingest_xml(db, contenido)
    except (ParseError, ValueError, InvalidOperation) as e:
        return {"archivo": nombre, "estado": "error", "motivo": f"XML inválido: {e}"}
    except IntegrityError:
        return {"archivo": nombre, "estado": "error", "motivo": "conflicto al guardar"}
    if r.get("omitido"):
        return {"archivo": nombre, "estado": "omitido", "motivo": r.get("motivo", "")}
    estado = "nuevo" if r.get("nuevo") else "actualizado"
    return {"archivo": nombre, "estado": estado, "clave": r.get("clave"),
            "rol": r.get("rol"), "cliente_id": r.get("cliente_id")}


def _resumen(resultados: list[dict]) -> dict:
    c = Counter(r["estado"] for r in resultados)
    return {
        "total": len(resultados),
        "nuevos": c["nuevo"], "actualizados": c["actualizado"],
        "omitidos": c["omitido"], "errores": c["error"],
        "archivos": resultados,
    }


def ingest_lote(db: Session, archivos: list[tuple[str, bytes]]) -> dict:
    """Procesa un lote de archivos (.xml o .zip). Éxito parcial: un archivo malo no
    aborta el lote. Hace un único commit al final. Devuelve resumen + detalle."""
    resultados: list[dict] = []
    for nombre, contenido in archivos:
        low = nombre.lower()
        if low.endswith(".zip"):
            try:
                entradas = _entradas_zip(contenido)
            except (zipfile.BadZipFile, ValueError) as e:
                resultados.append({"archivo": nombre, "estado": "error", "motivo": f"ZIP inválido: {e}"})
                continue
            for sub_nombre, sub_bytes in entradas:
                resultados.append(_ingest_uno(db, sub_nombre, sub_bytes))
        elif low.endswith(".xml"):
            resultados.append(_ingest_uno(db, nombre, contenido))
        # otros tipos: se ignoran silenciosamente
    db.commit()
    return _resumen(resultados)
```

- [ ] **Step 4: Correr, confirmar que PASA**

Run: pytest `tests/test_ingesta_lote.py -q`. Expected: PASS (7 passed).
Suite completa: pytest `-q` → Expected: 72 passed (65 baseline + 3 Tarea 1 + 4 Tarea 2).

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(lote): ingest_lote con exito parcial (savepoint por archivo) y reporte"
```

---

## Tarea 3: Endpoint `POST /api/ingesta/lote`

**Files:**
- Modify: `backend/app/routers/ingesta.py`
- Test: `backend/tests/test_ingesta_lote.py` (agregar tests)

- [ ] **Step 1: Agregar los tests que fallan** al final de `backend/tests/test_ingesta_lote.py`

```python
from app.models.usuario import Usuario
from app.auth.security import hash_password

def _token(client, db_session):
    db_session.add(Usuario(nombre="lote", password_hash=hash_password("clave12345"), es_admin=True))
    db_session.commit()
    return client.post("/auth/login", data={"username": "lote", "password": "clave12345"}).json()["access_token"]

def _auth(t):
    return {"Authorization": f"Bearer {t}"}

def test_endpoint_ingesta_lote(client, db_session):
    token = _token(client, db_session); _cliente(db_session)
    z = _zip_bytes({"fe_almacen_leon.xml": (FIXT / "fe_almacen_leon.xml").read_bytes()})
    files = [
        ("archivos", ("mayo.zip", z, "application/zip")),
        ("archivos", ("mensaje_hacienda.xml", (FIXT / "mensaje_hacienda.xml").read_bytes(), "application/xml")),
    ]
    r = client.post("/api/ingesta/lote", files=files, headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["nuevos"] == 1
    assert body["omitidos"] == 1

def test_endpoint_ingesta_lote_sin_token_401(client):
    files = [("archivos", ("x.xml", b"<x/>", "application/xml"))]
    assert client.post("/api/ingesta/lote", files=files).status_code == 401
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: pytest `tests/test_ingesta_lote.py -q -k endpoint`
Expected: FAIL — 404 (la ruta `/api/ingesta/lote` no existe).

- [ ] **Step 3: Extender `backend/app/routers/ingesta.py`**

Agregar el import de `ingest_lote` (junto al de `ingest_xml`):
```python
from app.motor.ingesta import ingest_xml
from app.motor.ingesta_lote import ingest_lote
```
Y agregar el endpoint (debajo del `POST ""` existente):
```python
@router.post("/lote")
def ingesta_lote(archivos: list[UploadFile], db: Session = Depends(get_db),
                 _: Usuario = Depends(get_current_user)):
    pares = [(a.filename or "", a.file.read()) for a in archivos]
    return ingest_lote(db, pares)
```

- [ ] **Step 4: Correr, confirmar que PASA**

Run: pytest `tests/test_ingesta_lote.py -q`. Expected: PASS (9 passed).
Suite completa: pytest `-q` → Expected: 74 passed.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(lote): endpoint POST /api/ingesta/lote"
```

---

## Self-Review (cobertura del spec)

- **Endpoint unificado `/lote` (ZIP + XML sueltos)** → Tarea 3. ✅
- **Expansión de ZIP (solo .xml, ignora no-.xml/__MACOSX) + tope anti-zip-bomb** → Tarea 1 (`_entradas_zip`). ✅
- **Éxito parcial (savepoint por archivo, un único commit)** → Tarea 2 (`_ingest_uno` con `db.begin_nested()`, `ingest_lote` commit al final). ✅
- **Reporte por archivo + resumen (`estado` nuevo/actualizado/omitido/error)** → Tarea 2 (`_resumen`, `_ingest_uno`). ✅
- **Manejo de errores por archivo (ParseError/ValueError/InvalidOperation/IntegrityError; ZIP corrupto)** → Tarea 2. ✅
- **El single-file actual sin cambios** → Tarea 3 solo agrega `/lote`. ✅

**Consistencia de tipos:** `_entradas_zip(contenido, max_entradas, max_bytes) -> list[(str, bytes)]`; `_ingest_uno(db, nombre, contenido) -> dict`; `ingest_lote(db, archivos: list[(str, bytes)]) -> dict` (resumen con claves `total/nuevos/actualizados/omitidos/errores/archivos`). El endpoint arma `pares: list[(str, bytes)]` desde `list[UploadFile]`. Usados consistentemente en tests y router. ✅

**Sin placeholders:** todo el código completo; comandos y valores esperados explícitos. ✅

## Diferido (fuera de alcance)
Background para lotes enormes, ZIP anidados, dry-run, reporte de duplicados intra-lote, límite de tamaño del request a nivel servidor.
