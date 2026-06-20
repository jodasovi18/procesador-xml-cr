# Fase 1B-4: Resumen por categoría + endpoint

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Agrupar las líneas guardadas por categoría tributaria (Bienes/Servicios × tarifa, con No Sujeto) para un cliente, período y rol, y exponerlo como `GET /api/resumen`. Es la base del D-150.

**Architecture:** `app/motor/resumen.py` con `build_resumen(db, cliente_id, periodo, rol)` (consulta las líneas guardadas y agrega). Router `app/routers/resumen.py`. Después de implementar, el controlador corre una verificación de reconciliación sobre los totales reales de Agrofinca mayo.

**Tech Stack:** SQLAlchemy 2.0, Pydantic, pytest. Postgres local 5433 (ver memoria).

---

## Contexto

Rebuild del Sistema XML. Hecho: 1A, 1B-1 (parser), 1B-2 (tarifa+transforms), 1B-3 (ingesta: `POST /api/ingesta` guarda comprobantes con `cliente_id`, `rol`, `periodo`, y líneas con `tipo` Bienes/Servicios + `tarifa_label` + `tarifa_pct` efectiva + `iva_monto` + `base_imponible`). Verificado: `base_imponible` está poblado también en líneas No Sujeto (= el monto). Este plan agrega la agregación por categoría.

**Categorías** (igual que el sistema viejo, SIN la etiqueta "Combustibles"):
- Si `tarifa_label == "No Sujeto"` → categoría `"No Sujeto"` (no se separa por tipo).
- Si no → `f"{tipo} {tarifa_label}"`, ej. `"Bienes 13%"`, `"Bienes 1%"`, `"Servicios 13%"`, `"Bienes Exento"`.
- `base` suma `base_imponible`; `iva` suma `iva_monto`.

Entorno: `backend\.venv\Scripts\python.exe`, Postgres local 5433 `sistemaxml`/`devpassword`, pip `--trusted-host pypi.org --trusted-host files.pythonhosted.org`, sin Docker, nunca el `python` pelado.

---

## Tarea 1: `build_resumen` + golden test controlado

**Files:**
- Create: `backend/app/motor/resumen.py`
- Create: `backend/tests/test_resumen.py`

- [ ] **Step 1: Escribir el test que falla `tests/test_resumen.py`**
```python
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
```

- [ ] **Step 2: Correr, confirmar que FALLA** (no existe `app.motor.resumen`).

- [ ] **Step 3: Crear `app/motor/resumen.py`**
```python
"""Resumen por categoría tributaria sobre las líneas guardadas.
Categoría: 'No Sujeto' para esos códigos, si no '{tipo} {tarifa_label}'."""
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.comprobante import Comprobante, LineaComprobante

def build_resumen(db: Session, cliente_id: int, periodo: str, rol: str) -> dict[str, dict[str, Decimal]]:
    stmt = (
        select(LineaComprobante)
        .join(Comprobante, LineaComprobante.comprobante_id == Comprobante.id)
        .where(
            Comprobante.cliente_id == cliente_id,
            Comprobante.periodo == periodo,
            Comprobante.rol == rol,
        )
    )
    cats: dict[str, dict[str, Decimal]] = {}
    for ln in db.scalars(stmt):
        if ln.tarifa_label == "No Sujeto":
            cat = "No Sujeto"
        else:
            cat = f"{ln.tipo} {ln.tarifa_label}".strip()
        d = cats.setdefault(cat, {"base": Decimal("0"), "iva": Decimal("0")})
        d["base"] += ln.base_imponible
        d["iva"] += ln.iva_monto
    return cats
```

- [ ] **Step 4: Correr, confirmar que PASA** (2 passed). Suite completa → 29 passed.

- [ ] **Step 5: Commit**
```
git add backend && git commit -m "feat(resumen): build_resumen por categoria con golden test controlado"
```

---

## Tarea 2: Endpoint `GET /api/resumen`

**Files:**
- Create: `backend/app/routers/resumen.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_resumen_endpoint.py`

- [ ] **Step 1: Escribir el test que falla `tests/test_resumen_endpoint.py`**
```python
from pathlib import Path
from sqlalchemy import select
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.auth.security import hash_password

FIXT = Path(__file__).parent / "fixtures"

def _token(client, db_session):
    db_session.add(Usuario(nombre="re2", password_hash=hash_password("clave12345"), es_admin=True))
    db_session.commit()
    return client.post("/auth/login", data={"username": "re2", "password": "clave12345"}).json()["access_token"]

def _cliente(db_session):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c

def _auth(t):
    return {"Authorization": f"Bearer {t}"}

def test_endpoint_resumen_compra(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    with open(FIXT / "fe_almacen_leon.xml", "rb") as fh:
        client.post("/api/ingesta", files={"archivo": ("x.xml", fh, "application/xml")}, headers=_auth(token))
    comp = db_session.scalar(select(Comprobante).where(Comprobante.cliente_id == cli.id))
    r = client.get(f"/api/resumen?cliente_id={cli.id}&periodo={comp.periodo}&rol=compra", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["Bienes 13%"]["base"] == "1858.40000"
    assert body["Bienes 13%"]["iva"] == "241.59000"

def test_endpoint_resumen_sin_token_401(client):
    assert client.get("/api/resumen?cliente_id=1&periodo=202605&rol=compra").status_code == 401
```

- [ ] **Step 2: Correr, confirmar que FALLA** (404).

- [ ] **Step 3: Crear `app/routers/resumen.py`**
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.motor.resumen import build_resumen

router = APIRouter(prefix="/api/resumen", tags=["resumen"])

@router.get("")
def resumen(cliente_id: int, periodo: str, rol: str,
            db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    cats = build_resumen(db, cliente_id, periodo, rol)
    return {cat: {"base": str(v["base"]), "iva": str(v["iva"])} for cat, v in cats.items()}
```

- [ ] **Step 4: Incluir el router en `app/main.py`** (junto a los otros)
```python
from app.routers.resumen import router as resumen_router
app.include_router(resumen_router)
```

- [ ] **Step 5: Correr el test, confirmar que PASA** (2 passed). Suite completa → 31 passed.

Nota sobre el assert `"1858.40000"`: `str(Decimal)` de un `Numeric(18,5)` conserva los ceros de escala. Si el valor real difiere en ceros finales, ajustar el assert al string exacto que produzca `str()` (ej. correr el test, ver el valor, fijarlo).

- [ ] **Step 6: Commit**
```
git add backend && git commit -m "feat(resumen): endpoint GET /api/resumen"
```

---

## Self-Review

- **Agregación por categoría con No Sujeto sin 'Combustibles'** → `build_resumen` (Tarea 1). ✅
- **Suma desde `base_imponible`/`iva_monto`** (verificado que base_imponible está poblado en No Sujeto). ✅
- **Golden test controlado, portable, exacto** (2 fixtures reales: compra Bienes 13% y venta No Sujeto). ✅
- **Endpoint protegido** (Tarea 2). ✅
- **Sin placeholders:** código completo de `resumen.py` y router; tests con valores reales. ✅

**Resultado:** se puede consultar el resumen por categoría de un cliente/período/rol. Falta la verificación de reconciliación sobre el período completo (la corre el controlador después).

---

## Verificación de reconciliación (la corre el controlador, no es tarea de subagente)
Tras Tarea 2: registrar el cliente Agrofinca (3102858282), ingestar TODOS los XML de `...\Agrofinca La Flor S&C Ltda\2026\5-May\`, correr `build_resumen` para compra y venta, y comparar contra los totales reales: compras bienes 1% base 34.947.266 / 13% base 1.269.904 / no sujeto 1.370.942; ventas bienes 1% base 34.749.174 / 13% base 1.824.800 / no sujeto 699.750. Si reconcilia → validación fuerte del motor completo. Si no → investigar la diferencia (no forzar los asserts).

## Próximo plan (1B-5 / 1C)
Estructura D-150 (débito/crédito, saldo) sobre el resumen; subida manual de ZIP/múltiples XML; luego el agente local (1C).
