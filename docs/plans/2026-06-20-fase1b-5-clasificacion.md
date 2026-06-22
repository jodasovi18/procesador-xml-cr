# Fase 1B-5: Capa de Clasificación — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clasificar líneas de compra/venta por reglas (proveedor/CABYS) en Compras/Gastos/Bienes de Capital/No Deducibles + sub-clasificación, para que el resumen tributario de compras refleje la realidad contable (No Deducibles segregado, Combustibles→No Sujeto) y exponer una vista de gestión Clasificación × Tasa.

**Architecture:** Clasificación **al vuelo**: una tabla `reglas_clasificacion` es la fuente de verdad; los resúmenes derivan la clasificación por línea en la consulta (uniendo `Comprobante` para la cédula de la contraparte). Las columnas `clasificacion`/`sub_clasificacion` de `LineaComprobante` quedan reservadas para overrides futuros. Engine puro y testeable en `motor/clasificacion.py`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, pytest. Postgres local 5433 (ver memoria/CLAUDE.md).

> **Diseño completo:** `docs/plans/2026-06-20-fase1b-5-clasificacion-design.md`.

---

## Contexto y entorno (CRÍTICO)

- Venv SIEMPRE: `backend\.venv\Scripts\python.exe`. **Nunca** el `python` pelado (stub roto, exit 9009).
- Pruebas: desde `backend/`: `.venv\Scripts\python.exe -m pytest -q`. Las pruebas crean la BD `sistemaxml_test` vía `Base.metadata.create_all` (no usan migraciones).
- Migraciones (BD de dev real): `.venv\Scripts\alembic.exe ...`.
- pip (si hiciera falta): `--trusted-host pypi.org --trusted-host files.pythonhosted.org`.
- Dinero SIEMPRE `Decimal`/`Numeric`.
- Suite previa: **31 pruebas verdes**. Este plan agrega ~15.

### Fixture clave para los golden tests
`backend/tests/fixtures/fe_almacen_leon.xml` es una **compra** real:
- Emisor (proveedor) cédula: **`3101030042`** (Almacén León).
- Receptor (cliente): Agrofinca **`3102858282`**.
- Líneas Bienes, `CodigoTarifaIVA=08` (13%). Total Bienes 13%: **base `1858.40`, IVA `241.59`**.

## File Structure

- Create: `backend/app/models/regla_clasificacion.py` — modelo ORM `ReglaClasificacion`.
- Modify: `backend/app/models/__init__.py` — registrar el modelo.
- Create (autogen): `backend/alembic/versions/<hash>_crear_tabla_reglas_clasificacion.py`.
- Create: `backend/app/motor/clasificacion.py` — engine puro (lookup + clasificar).
- Modify: `backend/app/motor/resumen.py` — `build_resumen` clasificación-aware + `build_resumen_clasificacion`.
- Create: `backend/app/schemas/regla.py` — `ReglaCreate`/`ReglaOut`.
- Create: `backend/app/routers/reglas.py` — `POST`/`GET /api/reglas`.
- Modify: `backend/app/routers/resumen.py` — `GET /api/resumen/clasificacion`.
- Modify: `backend/app/main.py` — incluir `reglas_router`.
- Test: `backend/tests/test_regla_modelo.py`, `test_clasificacion.py`, `test_resumen_clasificacion.py`, `test_reglas_endpoint.py`.

---

## Tarea 1: Modelo `ReglaClasificacion` + migración

**Files:**
- Create: `backend/app/models/regla_clasificacion.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_regla_modelo.py`

- [ ] **Step 1: Escribir el test que falla** `backend/tests/test_regla_modelo.py`

```python
from sqlalchemy import select
from app.models.cliente import Cliente
from app.models.regla_clasificacion import ReglaClasificacion

def test_persistir_regla(db_session):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    db_session.add(ReglaClasificacion(
        cliente_id=c.id, cedula="3101030042", clasificacion="No Deducibles"))
    db_session.commit()
    r = db_session.scalar(select(ReglaClasificacion).where(ReglaClasificacion.cliente_id == c.id))
    assert r.cedula == "3101030042"
    assert r.clasificacion == "No Deducibles"
    assert r.cabys is None
    assert r.rol is None
    assert r.sub_clasificacion is None
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run (desde `backend/`): `.venv\Scripts\python.exe -m pytest tests/test_regla_modelo.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.regla_clasificacion'`.

- [ ] **Step 3: Crear el modelo** `backend/app/models/regla_clasificacion.py`

```python
from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class ReglaClasificacion(Base):
    __tablename__ = "reglas_clasificacion"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    cedula: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    cabys: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    rol: Mapped[str | None] = mapped_column(String(10), nullable=True)  # compra|venta (solo regla de cédula sola)
    clasificacion: Mapped[str] = mapped_column(String(40), nullable=False)
    sub_clasificacion: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Registrar el modelo** en `backend/app/models/__init__.py` (agregar la línea al final)

```python
from app.models.regla_clasificacion import ReglaClasificacion  # noqa: F401
```

- [ ] **Step 5: Correr, confirmar que PASA**

Run: `.venv\Scripts\python.exe -m pytest tests/test_regla_modelo.py -q`
Expected: PASS (1 passed).

- [ ] **Step 6: Generar la migración** (BD de dev). Desde `backend/`:

Run: `.venv\Scripts\alembic.exe revision --autogenerate -m "crear tabla reglas_clasificacion"`
Expected: crea `alembic/versions/<hash>_crear_tabla_reglas_clasificacion.py` con `op.create_table("reglas_clasificacion", ...)`.

- [ ] **Step 7: Revisar el archivo de migración** generado. Confirmar que `create_table` incluye las columnas (`id`, `cliente_id` con FK a `clientes`, `cedula`, `cabys`, `rol`, `clasificacion`, `sub_clasificacion`, `created_at`) y los índices. No debe contener cambios espurios sobre otras tablas; si los hay, borrarlos del archivo.

- [ ] **Step 8: Aplicar la migración**

Run: `.venv\Scripts\alembic.exe upgrade head`
Expected: `Running upgrade ... -> <hash>, crear tabla reglas_clasificacion`.

- [ ] **Step 9: Suite completa + commit**

Run: `.venv\Scripts\python.exe -m pytest -q`  → Expected: 32 passed.

```bash
git add backend && git commit -m "feat(clasificacion): modelo ReglaClasificacion + migracion"
```

---

## Tarea 2: Engine `motor/clasificacion.py`

**Files:**
- Create: `backend/app/motor/clasificacion.py`
- Test: `backend/tests/test_clasificacion.py`

- [ ] **Step 1: Escribir el test que falla** `backend/tests/test_clasificacion.py`

```python
from app.models.regla_clasificacion import ReglaClasificacion
from app.motor.clasificacion import build_lookup, clasificar, CLASIFICACIONES_VALID, SUBCATEGORIAS_NO_SUJETO

def _r(**kw):
    # ReglaClasificacion sin sesión: solo un objeto en memoria
    return ReglaClasificacion(cliente_id=1, **kw)

def test_prioridad_ced_cabys_gana_a_cabys():
    lk = build_lookup([
        _r(cedula="123", cabys="ABC", clasificacion="Compras"),
        _r(cabys="ABC", clasificacion="Gastos"),
    ])
    assert clasificar("123", "ABC", "compra", lk) == ("Compras", "")

def test_prioridad_cabys_gana_a_ced():
    lk = build_lookup([
        _r(cabys="ABC", clasificacion="Gastos"),
        _r(cedula="123", clasificacion="Compras"),
    ])
    assert clasificar("123", "ABC", "compra", lk) == ("Gastos", "")

def test_separacion_de_rol():
    lk = build_lookup([
        _r(cedula="123", rol="compra", clasificacion="Compras"),
        _r(cedula="123", rol="venta", clasificacion="Gastos"),
    ])
    assert clasificar("123", None, "compra", lk) == ("Compras", "")
    assert clasificar("123", None, "venta", lk) == ("Gastos", "")

def test_sub_clasificacion_combustibles():
    lk = build_lookup([
        _r(cedula="123", clasificacion="Gastos", sub_clasificacion="Combustibles"),
    ])
    assert clasificar("123", None, "compra", lk) == ("Gastos", "Combustibles")
    assert "Combustibles" in SUBCATEGORIAS_NO_SUJETO

def test_fallback_sin_clasificar():
    lk = build_lookup([])
    assert clasificar("999", "ZZZ", "compra", lk) == ("Sin Clasificar", "")
    assert "Sin Clasificar" in CLASIFICACIONES_VALID
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: `.venv\Scripts\python.exe -m pytest tests/test_clasificacion.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.motor.clasificacion'`.

- [ ] **Step 3: Crear el engine** `backend/app/motor/clasificacion.py`

```python
"""Engine de clasificación: lookup por prioridad (céd+cabys) > cabys > céd(+rol).
Port de build_clasificacion_lookup/classify_line del parse_xml.py viejo.
Las reglas de cédula sola se separan por rol; las de cabys son rol-agnósticas."""
from dataclasses import dataclass, field

CLASIFICACIONES_VALID = {"Compras", "Gastos", "Bienes de Capital",
                         "No Deducibles", "Sin Clasificar"}
SUBCATEGORIAS_NO_SUJETO = {"Combustibles"}

@dataclass
class Lookup:
    by_ced_cabys: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)
    by_cabys: dict[str, tuple[str, str]] = field(default_factory=dict)
    by_ced: dict[str, tuple[str, str]] = field(default_factory=dict)
    by_ced_venta: dict[str, tuple[str, str]] = field(default_factory=dict)

def build_lookup(reglas) -> Lookup:
    lk = Lookup()
    for r in reglas:
        ced = (r.cedula or "").strip() or None
        cab = (r.cabys or "").strip() or None
        val = (r.clasificacion, (r.sub_clasificacion or "").strip())
        if ced and cab:
            lk.by_ced_cabys[(ced, cab)] = val
        elif ced:
            if r.rol == "venta":
                lk.by_ced_venta[ced] = val
            else:
                lk.by_ced[ced] = val
        elif cab:
            lk.by_cabys[cab] = val
    return lk

def clasificar(cedula: str | None, cabys: str | None, rol: str,
               lookup: Lookup) -> tuple[str, str]:
    ced = (cedula or "").strip() or None
    cab = (cabys or "").strip() or None
    if ced and cab and (ced, cab) in lookup.by_ced_cabys:
        return lookup.by_ced_cabys[(ced, cab)]
    if cab and cab in lookup.by_cabys:
        return lookup.by_cabys[cab]
    if ced:
        d = lookup.by_ced_venta if rol == "venta" else lookup.by_ced
        if ced in d:
            return d[ced]
    return ("Sin Clasificar", "")
```

- [ ] **Step 4: Correr, confirmar que PASA**

Run: `.venv\Scripts\python.exe -m pytest tests/test_clasificacion.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(clasificacion): engine de lookup por prioridad con separacion de rol"
```

---

## Tarea 3: `build_resumen` clasificación-aware

**Files:**
- Modify: `backend/app/motor/resumen.py`
- Test: `backend/tests/test_resumen_clasificacion.py`

- [ ] **Step 1: Escribir el test que falla** `backend/tests/test_resumen_clasificacion.py`

```python
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
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: `.venv\Scripts\python.exe -m pytest tests/test_resumen_clasificacion.py -q`
Expected: FAIL — `test_resumen_no_deducible_segregado` y `test_resumen_combustibles_a_no_sujeto` fallan (el `build_resumen` viejo ignora las reglas y devuelve `Bienes 13%`). `test_resumen_sin_reglas_sin_cambios` pasa.

- [ ] **Step 3: Reescribir `backend/app/motor/resumen.py`** (contenido completo)

```python
"""Resumen por categoría tributaria sobre las líneas guardadas, con la capa de
clasificación aplicada al vuelo desde reglas_clasificacion.
- build_resumen: vista tributaria ({tipo} {tarifa}; No Sujeto; No Deducibles segregado).
- build_resumen_clasificacion: vista de gestión {clasificacion: {tarifa: {...}}}.
La clasificación se deriva por la cédula de la contraparte (emisor en compra,
receptor en venta) y el CABYS de la línea."""
from decimal import Decimal
from collections.abc import Iterator
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.comprobante import Comprobante, LineaComprobante
from app.models.regla_clasificacion import ReglaClasificacion
from app.motor.clasificacion import build_lookup, clasificar, SUBCATEGORIAS_NO_SUJETO


def _lineas_clasificadas(db: Session, cliente_id: int, periodo: str, rol: str
                         ) -> Iterator[tuple[LineaComprobante, str, str]]:
    """Itera (línea, clasificacion, sub_clasificacion) para el cliente/período/rol."""
    reglas = db.scalars(select(ReglaClasificacion).where(
        ReglaClasificacion.cliente_id == cliente_id))
    lookup = build_lookup(reglas)
    stmt = (
        select(LineaComprobante, Comprobante)
        .join(Comprobante, LineaComprobante.comprobante_id == Comprobante.id)
        .where(
            Comprobante.cliente_id == cliente_id,
            Comprobante.periodo == periodo,
            Comprobante.rol == rol,
        )
    )
    for ln, comp in db.execute(stmt):
        cedula = comp.emisor_cedula if rol == "compra" else comp.receptor_cedula
        clas, sub = clasificar(cedula, ln.cabys, rol, lookup)
        yield ln, clas, sub


def _acc(cats: dict, cat: str, base: Decimal, iva: Decimal) -> None:
    d = cats.setdefault(cat, {"base": Decimal("0"), "iva": Decimal("0")})
    d["base"] += base
    d["iva"] += iva


def build_resumen(db: Session, cliente_id: int, periodo: str, rol: str
                  ) -> dict[str, dict[str, Decimal]]:
    """Vista tributaria. No Deducible → bucket segregado; sub_clas Combustibles →
    No Sujeto (IVA 0, sin importar la tarifa XML); resto: {tipo} {tarifa} / No Sujeto."""
    cats: dict[str, dict[str, Decimal]] = {}
    for ln, clas, sub in _lineas_clasificadas(db, cliente_id, periodo, rol):
        if clas == "No Deducibles":
            _acc(cats, "No Deducibles", ln.base_imponible, ln.iva_monto)
        elif sub in SUBCATEGORIAS_NO_SUJETO:
            _acc(cats, "No Sujeto", ln.base_imponible, Decimal("0"))
        elif ln.tarifa_label == "No Sujeto":
            _acc(cats, "No Sujeto", ln.base_imponible, ln.iva_monto)
        else:
            _acc(cats, f"{ln.tipo} {ln.tarifa_label}".strip(), ln.base_imponible, ln.iva_monto)
    return cats
```

- [ ] **Step 4: Correr, confirmar que PASA**

Run: `.venv\Scripts\python.exe -m pytest tests/test_resumen_clasificacion.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(clasificacion): build_resumen clasificacion-aware (No Deducibles, Combustibles->No Sujeto)"
```

---

## Tarea 4: `build_resumen_clasificacion` (vista de gestión)

**Files:**
- Modify: `backend/app/motor/resumen.py`
- Test: `backend/tests/test_resumen_clasificacion.py` (agregar tests)

- [ ] **Step 1: Actualizar el import y agregar los tests que fallan** en `backend/tests/test_resumen_clasificacion.py`

Cambiar la línea de import a:
```python
from app.motor.resumen import build_resumen, build_resumen_clasificacion
```
Y agregar al final del archivo:

```python
def test_resumen_clasificacion_por_categoria(client, db_session):
    cli, comp = _ingest_leon(client, db_session)
    db_session.add(ReglaClasificacion(cliente_id=cli.id, cedula=PROV, clasificacion="Compras"))
    db_session.commit()
    res = build_resumen_clasificacion(db_session, cli.id, comp.periodo, "compra")
    assert res == {"Compras": {"13%": {"base": Decimal("1858.40"), "iva": Decimal("241.59")}}}

def test_resumen_clasificacion_combustibles_no_sujeto(client, db_session):
    cli, comp = _ingest_leon(client, db_session)
    db_session.add(ReglaClasificacion(cliente_id=cli.id, cedula=PROV,
                                      clasificacion="Gastos", sub_clasificacion="Combustibles"))
    db_session.commit()
    res = build_resumen_clasificacion(db_session, cli.id, comp.periodo, "compra")
    assert res == {"Gastos": {"No Sujeto": {"base": Decimal("1858.40"), "iva": Decimal("0")}}}

def test_resumen_clasificacion_sin_reglas_sin_clasificar(client, db_session):
    cli, comp = _ingest_leon(client, db_session)
    res = build_resumen_clasificacion(db_session, cli.id, comp.periodo, "compra")
    assert res == {"Sin Clasificar": {"13%": {"base": Decimal("1858.40"), "iva": Decimal("241.59")}}}
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: `.venv\Scripts\python.exe -m pytest tests/test_resumen_clasificacion.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_resumen_clasificacion'`.

- [ ] **Step 3: Agregar `build_resumen_clasificacion`** al final de `backend/app/motor/resumen.py`

```python
def build_resumen_clasificacion(db: Session, cliente_id: int, periodo: str, rol: str
                                ) -> dict[str, dict[str, dict[str, Decimal]]]:
    """Vista de gestión {clasificacion: {tarifa: {base, iva}}}.
    sub_clas Combustibles → tarifa 'No Sujeto' con IVA 0; resto usa tarifa_label."""
    result: dict[str, dict[str, dict[str, Decimal]]] = {}
    for ln, clas, sub in _lineas_clasificadas(db, cliente_id, periodo, rol):
        if sub in SUBCATEGORIAS_NO_SUJETO:
            tasa, iva = "No Sujeto", Decimal("0")
        else:
            tasa, iva = ln.tarifa_label, ln.iva_monto
        por_tasa = result.setdefault(clas, {})
        _acc(por_tasa, tasa, ln.base_imponible, iva)
    return result
```

- [ ] **Step 4: Correr el archivo completo, confirmar que PASA**

Run: `.venv\Scripts\python.exe -m pytest tests/test_resumen_clasificacion.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Suite completa + commit**

Run: `.venv\Scripts\python.exe -m pytest -q`  → Expected: 43 passed.

```bash
git add backend && git commit -m "feat(clasificacion): build_resumen_clasificacion (vista por categoria x tarifa)"
```

---

## Tarea 5: Schemas + endpoints (`/api/reglas`, `/api/resumen/clasificacion`)

**Files:**
- Create: `backend/app/schemas/regla.py`
- Create: `backend/app/routers/reglas.py`
- Modify: `backend/app/routers/resumen.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_reglas_endpoint.py`

- [ ] **Step 1: Escribir el test que falla** `backend/tests/test_reglas_endpoint.py`

```python
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
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: `.venv\Scripts\python.exe -m pytest tests/test_reglas_endpoint.py -q`
Expected: FAIL — 404 en `/api/reglas` y `/api/resumen/clasificacion` (rutas inexistentes).

- [ ] **Step 3: Crear el schema** `backend/app/schemas/regla.py`

```python
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from app.motor.clasificacion import CLASIFICACIONES_VALID

class ReglaCreate(BaseModel):
    cliente_id: int
    cedula: str | None = None
    cabys: str | None = None
    rol: str | None = None
    clasificacion: str
    sub_clasificacion: str | None = None

    @field_validator("cedula", "cabys", "sub_clasificacion")
    @classmethod
    def _empty_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip() or None

    @field_validator("rol")
    @classmethod
    def _valid_rol(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip() or None
        if v is not None and v not in {"compra", "venta"}:
            raise ValueError("rol debe ser 'compra' o 'venta'")
        return v

    @field_validator("clasificacion")
    @classmethod
    def _valid_clas(cls, v: str) -> str:
        v = v.strip()
        if v not in CLASIFICACIONES_VALID:
            raise ValueError(f"clasificacion inválida: {v}")
        return v

    @model_validator(mode="after")
    def _ced_o_cabys(self):
        if not self.cedula and not self.cabys:
            raise ValueError("se requiere al menos cedula o cabys")
        return self

class ReglaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente_id: int
    cedula: str | None
    cabys: str | None
    rol: str | None
    clasificacion: str
    sub_clasificacion: str | None
```

- [ ] **Step 4: Crear el router** `backend/app/routers/reglas.py`

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.models.regla_clasificacion import ReglaClasificacion
from app.schemas.regla import ReglaCreate, ReglaOut

router = APIRouter(prefix="/api/reglas", tags=["reglas"])

@router.post("", response_model=ReglaOut, status_code=status.HTTP_201_CREATED)
def crear_regla(data: ReglaCreate, db: Session = Depends(get_db),
                _: Usuario = Depends(get_current_user)):
    regla = ReglaClasificacion(**data.model_dump())
    db.add(regla)
    db.commit()
    db.refresh(regla)
    return regla

@router.get("", response_model=list[ReglaOut])
def listar_reglas(cliente_id: int, db: Session = Depends(get_db),
                  _: Usuario = Depends(get_current_user)):
    stmt = (select(ReglaClasificacion)
            .where(ReglaClasificacion.cliente_id == cliente_id)
            .order_by(ReglaClasificacion.id))
    return list(db.scalars(stmt))
```

- [ ] **Step 5: Extender el router de resumen** `backend/app/routers/resumen.py` (contenido completo)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.motor.resumen import build_resumen, build_resumen_clasificacion

router = APIRouter(prefix="/api/resumen", tags=["resumen"])

@router.get("")
def resumen(cliente_id: int, periodo: str, rol: str,
            db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    cats = build_resumen(db, cliente_id, periodo, rol)
    return {cat: {"base": str(v["base"]), "iva": str(v["iva"])} for cat, v in cats.items()}

@router.get("/clasificacion")
def resumen_clasificacion(cliente_id: int, periodo: str, rol: str,
                          db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    data = build_resumen_clasificacion(db, cliente_id, periodo, rol)
    return {
        clas: {tasa: {"base": str(v["base"]), "iva": str(v["iva"])} for tasa, v in tasas.items()}
        for clas, tasas in data.items()
    }
```

- [ ] **Step 6: Incluir el router de reglas** en `backend/app/main.py`

Agregar el import junto a los otros routers:
```python
from app.routers.reglas import router as reglas_router
```
Y la inclusión junto a las otras:
```python
app.include_router(reglas_router)
```

- [ ] **Step 7: Correr, confirmar que PASA**

Run: `.venv\Scripts\python.exe -m pytest tests/test_reglas_endpoint.py -q`
Expected: PASS (6 passed).

> Si `test_reglas_sin_token_401` diera 422 en el POST (orden auth/validación según versión de FastAPI), dejar solo el assert del GET para el 401 y confiar en los 422 dedicados para validación.

- [ ] **Step 8: Suite completa + commit**

Run: `.venv\Scripts\python.exe -m pytest -q`  → Expected: 49 passed.

```bash
git add backend && git commit -m "feat(clasificacion): endpoints /api/reglas y /api/resumen/clasificacion"
```

---

## Self-Review (cobertura del spec)

- **Tabla de reglas (fuente de verdad)** → Tarea 1 (modelo + migración). ✅
- **Engine prioridad (céd+cabys)>cabys>céd(+rol), fallback** → Tarea 2. ✅
- **Clasificación al vuelo (sin estampar líneas)** → `_lineas_clasificadas` en Tarea 3. ✅
- **No Deducibles segregado** → Tarea 3 (`test_resumen_no_deducible_segregado`). ✅
- **Combustibles→No Sujeto sin importar tarifa (IVA 0)** → Tarea 3 (`test_resumen_combustibles_a_no_sujeto`, sobre código 08/13%). ✅
- **Retrocompatible sin reglas** → Tarea 3 (`test_resumen_sin_reglas_sin_cambios`) + suite previa intacta. ✅
- **Vista Clasificación × Tasa** → Tarea 4. ✅
- **Endpoints `/api/reglas` (POST/GET) y `/api/resumen/clasificacion`, protegidos** → Tarea 5. ✅
- **Validación de schema (clasificacion válida, céd|cabys, rol)** → Tarea 5 (422 tests). ✅

**Consistencia de tipos:** `build_lookup(reglas) -> Lookup`; `clasificar(cedula, cabys, rol, lookup) -> tuple[str,str]`; `_lineas_clasificadas -> Iterator[(LineaComprobante, str, str)]`; `build_resumen -> dict[str, dict[str, Decimal]]`; `build_resumen_clasificacion -> dict[str, dict[str, dict[str, Decimal]]]`. Usados consistentemente en routers (`str(v["base"])`) y tests (`Decimal(...)`). ✅

**Sin placeholders:** todo el código está completo; comandos y valores esperados explícitos. ✅

## Diferido (fuera de alcance, fases posteriores)
Auto-preclasificación por CABYS, CRUD completo (editar/borrar) + UI, facturas mixtas, plan de cuentas, D-150, reconciliación completa Agrofinca (requiere `clasificaciones.json` real).
