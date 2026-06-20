# Fase 1B-3: Ingesta (pipeline XML → base de datos)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Implementar el pipeline de ingesta: recibir un XML de Hacienda, identificar el cliente y el rol (compra/venta) por cédula, parsearlo, aplicar tarifa + transforms, y guardarlo en PostgreSQL (idempotente por clave). Exponerlo como `POST /api/ingesta`.

**Architecture:** Un módulo `app/motor/ingesta.py` con funciones puras de mapeo (`periodo_de`, `construir_comprobante`) y un servicio (`ingest_xml`) que usa la sesión de DB. Un router `app/routers/ingesta.py` con el endpoint protegido. La agregación por categoría (resumen/D-150) es el Plan 1B-4.

**Tech Stack:** FastAPI (UploadFile), SQLAlchemy 2.0, Pydantic, pytest. Postgres local 5433 (ver memoria del proyecto).

---

## Contexto

Rebuild del Sistema XML. Hecho: 1A (backend+auth+clientes), 1B-1 (modelos `Comprobante`/`LineaComprobante` + `parse_comprobante_xml`), 1B-2 (`tarifa.tratamiento_de`, `transforms.apply_transforms`). Este plan los une y persiste.

**Decisiones (del diseño):**
- El cliente de un comprobante se determina por **cédula**, no por carpeta: si la cédula del **receptor** coincide con un `Cliente` registrado → rol `compra`; si coincide la del **emisor** → rol `venta` (prioridad al receptor). Si ninguna coincide → se guarda con `cliente_id=NULL`, `rol=NULL` (no asignado / excluido), conservando el `xml_raw`.
- El **período** sale de la fecha del comprobante (`YYYYMM`), no de la carpeta.
- **Idempotente por `clave`**: reingestar el mismo XML no duplica (se reemplaza).
- Solo se ingestan tipos de comprobante; los `MensajeHacienda` (respuestas) se omiten en este plan (el `estado_hacienda` se cablea en un plan posterior).

Entorno: `backend\.venv\Scripts\python.exe`, `.venv\Scripts\alembic.exe`, Postgres local 5433 `sistemaxml`/`devpassword`, pip `--trusted-host pypi.org --trusted-host files.pythonhosted.org`, sin Docker, nunca el `python` pelado.

---

## Tarea 1: Mapeo parsed → ORM (`construir_comprobante`)

**Files:**
- Create: `backend/app/motor/ingesta.py`
- Create: `backend/tests/test_ingesta_mapeo.py`

- [ ] **Step 1: Escribir el test que falla `tests/test_ingesta_mapeo.py`**
```python
from pathlib import Path
from decimal import Decimal
from app.motor.parser import parse_comprobante_xml
from app.motor.ingesta import periodo_de, construir_comprobante

FIXT = Path(__file__).parent / "fixtures"

def test_periodo_de_la_fecha():
    comp = parse_comprobante_xml((FIXT / "fe_almacen_leon.xml").read_bytes())
    assert periodo_de(comp.fecha) == "202605"

def test_construir_comprobante_compra():
    comp = parse_comprobante_xml((FIXT / "fe_almacen_leon.xml").read_bytes())
    orm = construir_comprobante(comp, cliente_id=7, rol="compra", xml_raw="<xml/>")
    assert orm.clave == "50604052600310103004200100001010000324943131803899"
    assert orm.periodo == "202605"
    assert orm.rol == "compra"
    assert orm.cliente_id == 7
    assert orm.total_comprobante == Decimal("2099.99")
    assert len(orm.lineas) == 1
    ln = orm.lineas[0]
    assert ln.tarifa_label == "13%"
    assert ln.tarifa_pct == Decimal("13")
    assert ln.tipo == "Bienes"

def test_construir_comprobante_venta_no_sujeto():
    comp = parse_comprobante_xml((FIXT / "venta_nosujeto.xml").read_bytes())
    orm = construir_comprobante(comp, cliente_id=7, rol="venta", xml_raw="<xml/>")
    no_sujetas = [l for l in orm.lineas if l.tarifa_codigo == "10"]
    assert no_sujetas
    for l in no_sujetas:
        assert l.tarifa_label == "No Sujeto"
```

- [ ] **Step 2: Correr, confirmar que FALLA** (no existe `app.motor.ingesta`).

- [ ] **Step 3: Crear `app/motor/ingesta.py`**
```python
"""Pipeline de ingesta: mapeo de ComprobanteParsed a los modelos ORM,
aplicando transforms (signo NC, USD, Bienes/Servicios) y tarifa por línea."""
from datetime import datetime
from app.motor.schemas import ComprobanteParsed
from app.motor.transforms import apply_transforms
from app.motor.tarifa import tratamiento_de
from app.models.comprobante import Comprobante, LineaComprobante

def periodo_de(fecha: datetime) -> str:
    return f"{fecha.year}{fecha.month:02d}"

def construir_comprobante(comp: ComprobanteParsed, cliente_id: int | None,
                          rol: str | None, xml_raw: str) -> Comprobante:
    c = apply_transforms(comp)  # signo NC, USD, tipo Bienes/Servicios por línea
    orm = Comprobante(
        clave=c.clave, tipo_doc=c.tipo_doc, consecutivo=c.consecutivo,
        fecha=c.fecha, periodo=periodo_de(c.fecha), rol=rol, cliente_id=cliente_id,
        emisor_nombre=c.emisor_nombre, emisor_cedula=c.emisor_cedula,
        receptor_nombre=c.receptor_nombre, receptor_cedula=c.receptor_cedula,
        moneda=c.moneda, tipo_cambio=c.tipo_cambio,
        total_gravado=c.total_gravado, total_exento=c.total_exento,
        total_exonerado=c.total_exonerado,
        total_no_sujeto=c.total_serv_no_sujeto + c.total_merc_no_sujeto,
        total_iva=c.total_iva, total_comprobante=c.total_comprobante,
        xml_raw=xml_raw,
    )
    for ln in c.lineas:
        t = tratamiento_de(ln)
        orm.lineas.append(LineaComprobante(
            numero=ln.numero, cabys=ln.cabys, detalle=ln.detalle,
            cantidad=ln.cantidad, base_imponible=ln.base_imponible,
            tarifa_codigo=ln.tarifa_codigo, tarifa_pct=t.pct_efectiva,
            tarifa_label=t.label, tipo=ln.tipo, iva_monto=ln.iva_monto,
        ))
    return orm
```

- [ ] **Step 4: Correr, confirmar que PASA** (3 passed). Suite completa → 19 passed.

- [ ] **Step 5: Commit**
```
git add backend && git commit -m "feat(ingesta): mapeo parsed->ORM con periodo, tarifa y transforms"
```

---

## Tarea 2: Servicio de ingesta + endpoint `POST /api/ingesta`

**Files:**
- Modify: `backend/app/motor/ingesta.py` (agregar `ingest_xml`)
- Create: `backend/app/routers/ingesta.py`
- Modify: `backend/app/main.py` (incluir el router)
- Create: `backend/tests/test_ingesta_endpoint.py`

- [ ] **Step 1: Escribir el test que falla `tests/test_ingesta_endpoint.py`**
```python
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
```

- [ ] **Step 2: Correr, confirmar que FALLA** (404 en /api/ingesta).

- [ ] **Step 3: Agregar `ingest_xml` al final de `app/motor/ingesta.py`**
```python
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.cliente import Cliente
from app.motor.parser import parse_comprobante_xml

DOC_TYPES_COMPROBANTE = {
    "FacturaElectronica", "FacturaElectronicaCompra", "NotaCreditoElectronica",
    "NotaDebitoElectronica", "TiqueteElectronico",
}

def ingest_xml(db: Session, xml_bytes: bytes) -> dict:
    comp = parse_comprobante_xml(xml_bytes)
    if comp.tipo_doc not in DOC_TYPES_COMPROBANTE:
        return {"clave": comp.clave, "omitido": True, "motivo": f"tipo {comp.tipo_doc}"}

    # Determinar cliente y rol por cédula (prioridad al receptor = compra)
    cliente = db.scalar(select(Cliente).where(Cliente.cedula == comp.receptor_cedula))
    rol = "compra" if cliente else None
    if cliente is None:
        cliente = db.scalar(select(Cliente).where(Cliente.cedula == comp.emisor_cedula))
        rol = "venta" if cliente else None
    cliente_id = cliente.id if cliente else None

    xml_raw = xml_bytes.decode("utf-8", errors="replace")

    # Upsert idempotente por clave: si existe, se borra (cascade) y se reinserta
    existing = db.scalar(select(Comprobante).where(Comprobante.clave == comp.clave))
    es_nuevo = existing is None
    if existing is not None:
        db.delete(existing)
        db.flush()

    orm = construir_comprobante(comp, cliente_id, rol, xml_raw)
    db.add(orm)
    db.commit()
    return {"clave": comp.clave, "rol": rol, "cliente_id": cliente_id, "nuevo": es_nuevo}
```

- [ ] **Step 4: Crear `app/routers/ingesta.py`**
```python
from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.motor.ingesta import ingest_xml

router = APIRouter(prefix="/api/ingesta", tags=["ingesta"])

@router.post("")
def ingesta(archivo: UploadFile, db: Session = Depends(get_db),
            _: Usuario = Depends(get_current_user)):
    contenido = archivo.file.read()
    return ingest_xml(db, contenido)
```

- [ ] **Step 5: Incluir el router en `app/main.py`** (mantener health + auth + clientes)
```python
from app.routers.ingesta import router as ingesta_router
app.include_router(ingesta_router)
```
(Agregar el import junto a los otros routers y el `include_router` junto a los demás.)

- [ ] **Step 6: Correr el test, confirmar que PASA** (4 passed). Suite completa → 23 passed.

- [ ] **Step 7: Verificación manual (servidor real)**
Levantar `.venv\Scripts\uvicorn app.main:app` y en `/docs` confirmar que aparece `POST /api/ingesta` con upload de archivo. (Opcional, no bloqueante.)

- [ ] **Step 8: Commit**
```
git add backend && git commit -m "feat(ingesta): servicio ingest_xml y endpoint POST /api/ingesta (idempotente)"
```

---

## Self-Review

- **Identificación cliente/rol por cédula** → Tarea 2 `ingest_xml` (receptor→compra, emisor→venta, ninguno→null). ✅
- **Período desde la fecha** → `periodo_de` (Tarea 1). ✅
- **Aplica tarifa + transforms al persistir** → `construir_comprobante` (Tarea 1). ✅
- **Idempotente por clave** → Tarea 2 (delete+reinsert), test `test_ingesta_idempotente`. ✅
- **xml_raw conservado** → sí (para reprocesar). ✅
- **Endpoint protegido** → `get_current_user`, test 401. ✅
- **Sin placeholders:** todo el código de `ingesta.py` y el router está completo; tests de integración con DB real sobre fixtures reales. ✅
- **Consistencia:** usa `apply_transforms`/`tratamiento_de` de 1B-2 y `Comprobante`/`LineaComprobante` de 1B-1; `rol` ∈ {compra, venta, None}. ✅

**Resultado:** se puede subir un XML al endpoint y queda guardado correctamente (cliente, rol, período, líneas con su tarifa efectiva), idempotente. Base para 1B-4 (resumen/D-150 sobre datos guardados) y 1C (agente que sube XMLs a este endpoint).

---

## Próximo plan (1B-4)
Resumen por categoría sobre datos guardados (`build_resumen`/`build_resumen_ventas`: agrupa líneas en Bienes/Servicios × tarifa, con No Sujeto) → estructura D-150 → golden test de reconciliación sobre los totales reales de Agrofinca mayo 2026. Luego subida manual de ZIP/múltiples XML.
