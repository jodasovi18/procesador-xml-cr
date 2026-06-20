# Fase 1B-1: Modelos de comprobante + parser de XML

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Modelar `Comprobante` y `LineaComprobante` en PostgreSQL, y portar el extractor de XML de Hacienda (de `parse_xml.py`) a una función tipada `parse_comprobante_xml`, fijada con un golden test sobre un XML real.

**Architecture:** El parser es una función pura `bytes -> ComprobanteParsed` (Pydantic), sin tocar la base de datos — separa la extracción de la persistencia. Los modelos ORM viven aparte. La clasificación y los totales-resumen vienen en el Plan 1B-2; la ingesta (identificar cliente/rol, upsert) en el 1B-3.

**Tech Stack:** SQLAlchemy 2.0 (Numeric para dinero), Pydantic v2 (Decimal), xml.etree.ElementTree, pytest.

---

## Contexto

Rebuild del Sistema XML (ver `2026-06-19-fase1-backend-foundation.md` para el entorno: Postgres local puerto 5433, `.venv\Scripts\python.exe`, pip con `--trusted-host`, no Docker). El Plan 1A (backend + auth + clientes) está hecho. Este plan agrega el corazón: leer los XML de Hacienda.

**Fuente del port:** el extractor viejo está en `C:\Users\Usuario\Desktop\Sistemas\Sistema XML\parse_xml.py`:
- `TARIFA_MAP` (líneas ~27-36)
- `_extract_record(root, nsp, doc_type, hacienda_resp)` (líneas ~900-1014) — lee TODOS los nombres de elementos del XML CR (ResumenFactura y LineaDetalle). Es la **fuente de verdad de los nombres de campo** — portarlos exactamente.
- El parseo de líneas con exoneración (líneas ~962-1014).

**XML real de referencia (para el golden test):** en `C:\Users\Usuario\OneDrive\OFICINA\CONTAS\IVA\Agrofinca La Flor S&C Ltda\2026\5-May\` hay un archivo cuyo nombre contiene `00100001010000324943` (FacturaElectronica de ALMACEN LEON ROJAS). Valores conocidos verificados:
- esquema namespace `https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4`
- Clave `50604052600310103004200100001010000324943131803899`
- NumeroConsecutivo `00100001010000324943`, FechaEmision `2026-05-04T10:43:08-06:00`
- Emisor `ALMACEN LEON ROJAS` / `3101030042`; Receptor `AGROFINCA LA FLOR DE ZARCERO SYC LIMITADA` / `3102858282`
- TotalGravado `1858.40`, TotalImpuesto `241.59`, TotalComprobante `2099.99`
- 1 línea: CABYS `4651006000000`, Detalle `BOMBI LED WELLMAX 15W`, MontoTotal `1858.40`, BaseImponible `1858.40`, CodigoTarifaIVA `08`, Tarifa `13.00`

---

## Estructura de archivos (se crea/modifica)

```
backend/app/models/comprobante.py        # Comprobante + LineaComprobante (ORM)
backend/app/models/__init__.py           # registrar los nuevos modelos
backend/app/motor/__init__.py            # paquete del motor tributario
backend/app/motor/schemas.py             # ComprobanteParsed + LineaParsed (Pydantic)
backend/app/motor/parser.py              # parse_comprobante_xml(bytes) -> ComprobanteParsed
backend/tests/fixtures/fe_almacen_leon.xml   # copia del XML real
backend/tests/test_parser.py             # golden test
```

---

## Tarea 1: Modelos Comprobante y LineaComprobante

**Files:**
- Create: `backend/app/models/comprobante.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Crear `app/models/comprobante.py`**
```python
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, Numeric, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

class Comprobante(Base):
    __tablename__ = "comprobantes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"), nullable=True, index=True)
    clave: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    tipo_doc: Mapped[str] = mapped_column(String(40), nullable=False)
    consecutivo: Mapped[str] = mapped_column(String(30), nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    periodo: Mapped[str] = mapped_column(String(6), nullable=False, index=True)  # YYYYMM (de la fecha)
    rol: Mapped[str | None] = mapped_column(String(10), nullable=True)  # 'compra' | 'venta'
    emisor_nombre: Mapped[str] = mapped_column(String(255), default="")
    emisor_cedula: Mapped[str] = mapped_column(String(20), default="", index=True)
    receptor_nombre: Mapped[str] = mapped_column(String(255), default="")
    receptor_cedula: Mapped[str] = mapped_column(String(20), default="", index=True)
    moneda: Mapped[str] = mapped_column(String(3), default="CRC")
    tipo_cambio: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("1"))
    total_gravado: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    total_exento: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    total_exonerado: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    total_no_sujeto: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    total_iva: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    total_comprobante: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    estado_hacienda: Mapped[str | None] = mapped_column(String(20), nullable=True)
    xml_raw: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    lineas: Mapped[list["LineaComprobante"]] = relationship(
        back_populates="comprobante", cascade="all, delete-orphan")

class LineaComprobante(Base):
    __tablename__ = "lineas_comprobante"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comprobante_id: Mapped[int] = mapped_column(
        ForeignKey("comprobantes.id", ondelete="CASCADE"), nullable=False, index=True)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    cabys: Mapped[str] = mapped_column(String(20), default="")
    detalle: Mapped[str] = mapped_column(Text, default="")
    cantidad: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    base_imponible: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    tarifa_codigo: Mapped[str] = mapped_column(String(4), default="")
    tarifa_pct: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0"))
    iva_monto: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    clasificacion: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sub_clasificacion: Mapped[str | None] = mapped_column(String(60), nullable=True)
    comprobante: Mapped["Comprobante"] = relationship(back_populates="lineas")
```

- [ ] **Step 2: Registrar en `app/models/__init__.py`** (mantener Usuario y Cliente)
```python
from app.models.usuario import Usuario  # noqa: F401
from app.models.cliente import Cliente  # noqa: F401
from app.models.comprobante import Comprobante, LineaComprobante  # noqa: F401
```

- [ ] **Step 3: Generar y aplicar la migración**
```
.venv\Scripts\alembic.exe revision --autogenerate -m "crear tablas comprobantes y lineas"
.venv\Scripts\alembic.exe upgrade head
```
Abrir la migración y confirmar que crea ambas tablas, los índices (clave única, periodo, cedulas, comprobante_id) y la FK con ondelete CASCADE. Luego aplicarla.

- [ ] **Step 4: Verificar que la suite sigue verde** (los modelos nuevos no rompen nada)
Run: `.venv\Scripts\python.exe -m pytest -q` → 8 passed.

- [ ] **Step 5: Commit**
```
git add backend && git commit -m "feat(motor): modelos Comprobante y LineaComprobante"
```

---

## Tarea 2: Parser de XML (port) + golden test

**Files:**
- Create: `backend/app/motor/__init__.py` (vacío)
- Create: `backend/app/motor/schemas.py`
- Create: `backend/app/motor/parser.py`
- Create: `backend/tests/fixtures/fe_almacen_leon.xml` (copia del XML real)
- Create: `backend/tests/test_parser.py`

- [ ] **Step 1: Crear `app/motor/schemas.py`** (tipos de salida del parser)
```python
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel

class LineaParsed(BaseModel):
    numero: int
    cabys: str = ""
    detalle: str = ""
    cantidad: Decimal = Decimal("0")
    precio_unitario: Decimal = Decimal("0")
    monto_total: Decimal = Decimal("0")
    descuento: Decimal = Decimal("0")
    subtotal: Decimal = Decimal("0")
    base_imponible: Decimal = Decimal("0")
    tarifa_codigo: str = ""
    tarifa_pct: Decimal = Decimal("0")
    iva_monto: Decimal = Decimal("0")
    iva_neto: Decimal = Decimal("0")
    exon_tarifa: Decimal = Decimal("0")
    exon_monto: Decimal = Decimal("0")

class ComprobanteParsed(BaseModel):
    clave: str
    tipo_doc: str
    consecutivo: str
    fecha: datetime
    cond_venta: str = ""
    emisor_nombre: str = ""
    emisor_cedula: str = ""
    receptor_nombre: str = ""
    receptor_cedula: str = ""
    moneda: str = "CRC"
    tipo_cambio: Decimal = Decimal("1")
    total_serv_grav: Decimal = Decimal("0")
    total_serv_exento: Decimal = Decimal("0")
    total_serv_exon: Decimal = Decimal("0")
    total_serv_no_sujeto: Decimal = Decimal("0")
    total_merc_grav: Decimal = Decimal("0")
    total_merc_exento: Decimal = Decimal("0")
    total_merc_exon: Decimal = Decimal("0")
    total_merc_no_sujeto: Decimal = Decimal("0")
    total_gravado: Decimal = Decimal("0")
    total_exento: Decimal = Decimal("0")
    total_exonerado: Decimal = Decimal("0")
    total_descuentos: Decimal = Decimal("0")
    total_venta_neta: Decimal = Decimal("0")
    total_iva: Decimal = Decimal("0")
    total_otros_cargos: Decimal = Decimal("0")
    total_comprobante: Decimal = Decimal("0")
    lineas: list[LineaParsed] = []
```

- [ ] **Step 2: Crear `app/motor/parser.py`** — PORT del extractor

Portá la lógica de extracción de `C:\Users\Usuario\Desktop\Sistemas\Sistema XML\parse_xml.py` función `_extract_record` (líneas ~900-1014) y el parseo de líneas con exoneración, a esta función tipada. **Reglas del port:**
- Abrí el archivo viejo y copiá los **nombres exactos de elementos XML** que lee (ResumenFactura: `TotalServGravados`, `TotalServExentos`, `TotalServExonerado`, `TotalServNoSujeto`, los `TotalMercancias*`/`TotalMerc*`, `TotalGravado`, `TotalExento`, `TotalExonerado`, `TotalDescuentos`, `TotalVentaNeta`, `TotalImpuesto`, `OtrosCargos`/`TotalOtrosCargos`, `TotalComprobante`; LineaDetalle: `NumeroLinea`, `CodigoCABYS`, `Detalle`, `Cantidad`, `UnidadMedida`, `PrecioUnitario`, `MontoTotal`, `Descuento/MontoDescuento`, `SubTotal`, `BaseImponible`, `Impuesto/CodigoTarifaIVA`, `Impuesto/Tarifa`, `Impuesto/Monto`, `Impuesto/ImpuestoNeto`, `Impuesto/Exoneracion/TarifaExonerada`, `Impuesto/Exoneracion/MontoExoneracion`). NO inventes nombres — usá los del archivo viejo.
- Usá `Decimal(str(...))` para todos los montos (no float). Strings vacíos/ausentes → `Decimal("0")`.
- `tipo_doc` = tag raíz sin namespace (FacturaElectronica, NotaCreditoElectronica, FacturaElectronicaCompra, TiqueteElectronico, etc.).
- `fecha` = `datetime.fromisoformat(FechaEmision)`.
- El namespace se detecta del tag raíz (igual que `get_ns` en el viejo).
- **NO** apliques el signo negativo de notas de crédito ni etiquetas de tarifa ni clasificación — eso es del Plan 1B-2. Este parser extrae los valores crudos tal como están en el XML.

Interfaz exacta que debe exponer:
```python
def parse_comprobante_xml(xml_bytes: bytes) -> ComprobanteParsed: ...
```

- [ ] **Step 3: Copiar el XML real como fixture**
Buscá en `C:\Users\Usuario\OneDrive\OFICINA\CONTAS\IVA\Agrofinca La Flor S&C Ltda\2026\5-May\` (incluyendo subcarpetas) el archivo cuyo nombre contiene `00100001010000324943` y copialo a `backend\tests\fixtures\fe_almacen_leon.xml`. Verificá que el destino contiene la clave `50604052600310103004200100001010000324943131803899`.

- [ ] **Step 4: Crear el golden test `tests/test_parser.py`**
```python
from pathlib import Path
from decimal import Decimal
from app.motor.parser import parse_comprobante_xml

FIXT = Path(__file__).parent / "fixtures" / "fe_almacen_leon.xml"

def test_parse_fe_compra_real():
    comp = parse_comprobante_xml(FIXT.read_bytes())
    assert comp.tipo_doc == "FacturaElectronica"
    assert comp.clave == "50604052600310103004200100001010000324943131803899"
    assert comp.consecutivo == "00100001010000324943"
    assert comp.fecha.year == 2026 and comp.fecha.month == 5 and comp.fecha.day == 4
    assert comp.emisor_cedula == "3101030042"
    assert comp.receptor_cedula == "3102858282"
    assert comp.total_gravado == Decimal("1858.40")
    assert comp.total_iva == Decimal("241.59")
    assert comp.total_comprobante == Decimal("2099.99")
    assert len(comp.lineas) == 1
    ln = comp.lineas[0]
    assert ln.numero == 1
    assert ln.cabys == "4651006000000"
    assert ln.base_imponible == Decimal("1858.40")
    assert ln.tarifa_codigo == "08"
    assert ln.tarifa_pct == Decimal("13.00")
```

- [ ] **Step 5: Correr el golden test**
Run: `.venv\Scripts\python.exe -m pytest tests/test_parser.py -v`
Expected: PASS. Si algún Decimal no coincide (ej. `1858.40` vs `1858.40000`), normalizá comparando con `==` sobre Decimal (Decimal("1858.40") == Decimal("1858.40000") es True en Python, así que está OK). Si falla por nombres de elemento, revisá el archivo viejo para el nombre exacto.

- [ ] **Step 6: Correr toda la suite**
Run: `.venv\Scripts\python.exe -m pytest -q` → 9 passed.

- [ ] **Step 7: Commit**
```
git add backend && git commit -m "feat(motor): parser de XML de Hacienda con golden test sobre XML real"
```

---

## Self-Review

- **Modelos Comprobante/Linea con dinero en Numeric** → Tarea 1. ✅ (paridad de precisión decimal, el motivo de Postgres)
- **Período derivado de la fecha** → columna `periodo` en el modelo; se llena en la ingesta (1B-3) desde `fecha`. ✅
- **Parser tipado, separado de la DB** → Tarea 2 (función pura bytes→Pydantic). ✅
- **Golden test sobre XML real con valores verificados** → Tarea 2 Step 4. ✅
- **Sin placeholders:** modelos, schemas y golden test traen código completo; el cuerpo del parser es un port con referencias exactas al archivo viejo + nombres de elemento listados + interfaz fijada por el golden test. ✅
- **Consistencia de tipos:** `ComprobanteParsed`/`LineaParsed` (Pydantic, Decimal) vs `Comprobante`/`LineaComprobante` (ORM, Numeric) — nombres de campo alineados; el mapeo parsed→ORM se hace en la ingesta (1B-3). ✅

**Resultado:** la app puede leer un XML de Hacienda a objetos tipados, fijado por un golden test con datos reales. Base para el Plan 1B-2 (etiquetas de tarifa + clasificación + resumen) y 1B-3 (ingesta).

---

## Próximos planes (después de 1B-1)
- **1B-2 — Lógica tributaria:** portar `TARIFA_MAP`, el etiquetado de tarifa (con el fix de "No Sujeto" sin "Combustibles"), las transformaciones (signo de nota de crédito, conversión USD), y los builders de resumen (`build_resumen`/`build_resumen_ventas`), con golden tests sobre los totales por tarifa de un período real (Agrofinca mayo 2026: gravado 1% base 34.749.174, 13% base 1.824.800, etc.).
- **1B-3 — Ingesta:** endpoint `POST /api/ingesta` (recibe XML → identifica cliente y rol por cédula emisor/receptor → mapea ComprobanteParsed a ORM → calcula período de la fecha → upsert por clave → guarda con xml_raw); subida manual de ZIP/múltiples XML.
