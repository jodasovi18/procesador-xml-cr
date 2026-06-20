# Fase 1B-2: Lógica tributaria (tarifa + transforms)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Portar la lógica tributaria por línea: el tratamiento efectivo de IVA (con exoneración y el fix de "No Sujeto" sin "Combustibles") y las transformaciones a nivel comprobante (signo de nota de crédito, conversión USD, clasificación Bienes/Servicios). Todo con golden tests sobre datos reales.

**Architecture:** Módulos puros en `app/motor/`: `tarifa.py` (tratamiento por línea) y `transforms.py` (nivel comprobante). Operan sobre los objetos `ComprobanteParsed`/`LineaParsed` que produce el parser de 1B-1. La agregación por categoría (resumen/D-150) y la ingesta van en el Plan 1B-3.

**Tech Stack:** Pydantic v2 (Decimal), pytest. PostgreSQL local (puerto 5433, ver memoria del proyecto).

---

## Contexto

Rebuild del Sistema XML. 1A (backend) y 1B-1 (modelos `Comprobante`/`LineaComprobante` + parser de XML) ✅. El parser emite por línea: `tarifa_codigo` (cruda, ej. "08"/"10"), `tarifa_pct` (cruda del XML, ej. 13.00), `exon_tarifa`, `exon_monto`, `iva_monto`, `iva_neto`. **No** aplica signo de NC ni etiquetas — eso es ESTE plan.

**El bug que esto arregla:** en el sistema viejo las ventas agropecuarias (CodigoTarifaIVA `10`) salían etiquetadas como **"No Sujeto (Combustibles)"**. El "(Combustibles)" era una etiqueta hardcodeada de presentación (parse_xml.py viejo, línea 2046). El código 10/11 es "No Sujeto" a secas — puede ser agropecuario, combustible, u otra cosa.

**Lógica de referencia (parse_xml.py viejo):** `TARIFA_MAP` (líneas 27-36), `CODIGOS_NO_SUJETO = {'10','11'}` (línea 68), exoneración (líneas 992-1001: `pct_efectiva = max(0, tarifa - tarifa_exonerada)`), `_apply_transforms` (líneas 1052-1085: signo NC, USD, Bienes/Servicios).

Entorno: `backend\.venv\Scripts\python.exe`, `.venv\Scripts\alembic.exe`, Postgres local 5433 `sistemaxml`/`devpassword`, pip con `--trusted-host pypi.org --trusted-host files.pythonhosted.org`, sin Docker, nunca el `python` pelado.

---

## Tarea 1: Ajustes de modelo + migración

**Files:**
- Modify: `backend/app/models/comprobante.py`
- Modify: `backend/app/motor/parser.py` (un comentario)

- [ ] **Step 1: Agregar columnas a `LineaComprobante`** en `app/models/comprobante.py`

Dentro de la clase `LineaComprobante`, agregar estas dos columnas después de `tarifa_pct`:
```python
    tarifa_label: Mapped[str] = mapped_column(String(20), default="")   # Exento|1%|2%|4%|13%|No Sujeto (efectivo)
    tipo: Mapped[str] = mapped_column(String(10), default="")            # Bienes|Servicios
```

- [ ] **Step 2: Corregir el `ondelete` de la FK `cliente_id`** en `Comprobante`

Cambiar la columna `cliente_id` para que al borrar un cliente los comprobantes queden huérfanos (cédula se conserva en el propio comprobante) en vez de fallar:
```python
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True, index=True)
```

- [ ] **Step 3: Comentar el guard de `tipo_cambio`** en `app/motor/parser.py`

Reemplazar la línea `tipo_cambio = tc if tc else Decimal("1")` por:
```python
            # Decimal("0") es falsy: si TipoCambio falta o es 0 se asume 1 (port del viejo `or 1.0`).
            tipo_cambio = tc if tc else Decimal("1")
```

- [ ] **Step 4: Generar y aplicar la migración**
```
.venv\Scripts\alembic.exe revision --autogenerate -m "lineas: tarifa_label y tipo; FK cliente_id SET NULL"
.venv\Scripts\alembic.exe upgrade head
```
Abrir la migración. Confirmar que: (a) agrega las columnas `tarifa_label` y `tipo` a `lineas_comprobante`; (b) ajusta la FK `cliente_id` a `ondelete='SET NULL'`. Si autogenerate NO detecta el cambio de la FK, agregarlo a mano en la migración con `op.drop_constraint(...)` + `op.create_foreign_key(..., ondelete='SET NULL')` (la tabla está vacía, no hay riesgo de datos). Luego aplicar.

- [ ] **Step 5: Verificar suite** → `.venv\Scripts\python.exe -m pytest -q` → 9 passed.

- [ ] **Step 6: Commit**
```
git add backend && git commit -m "feat(motor): columnas tarifa_label/tipo y FK cliente_id SET NULL"
```

---

## Tarea 2: Módulo `tarifa` (tratamiento por línea) + golden tests

**Files:**
- Create: `backend/app/motor/tarifa.py`
- Create: `backend/tests/fixtures/venta_nosujeto.xml` (copia de un XML real con línea código 10)
- Create: `backend/tests/test_tarifa.py`

- [ ] **Step 1: Escribir el test que falla `tests/test_tarifa.py`**
```python
from pathlib import Path
from decimal import Decimal
from app.motor.parser import parse_comprobante_xml
from app.motor.tarifa import tratamiento_linea, tratamiento_de

FIXT = Path(__file__).parent / "fixtures"

def test_codigo_08_es_13pct():
    comp = parse_comprobante_xml((FIXT / "fe_almacen_leon.xml").read_bytes())
    t = tratamiento_de(comp.lineas[0])
    assert t.label == "13%"
    assert t.pct_efectiva == Decimal("13")
    assert t.es_no_sujeto is False

def test_codigo_10_es_no_sujeto_sin_combustibles():
    comp = parse_comprobante_xml((FIXT / "venta_nosujeto.xml").read_bytes())
    no_sujetas = [l for l in comp.lineas if l.tarifa_codigo == "10"]
    assert no_sujetas, "el fixture debe tener al menos una linea codigo 10"
    for l in no_sujetas:
        t = tratamiento_de(l)
        assert t.label == "No Sujeto"          # EL FIX: nunca 'No Sujeto (Combustibles)'
        assert t.es_no_sujeto is True
        assert t.pct_efectiva == Decimal("0")

def test_exoneracion_resta_tarifa():
    # 13% con TarifaExonerada 12% -> 1% efectivo (Ley 9635 agropecuaria)
    t = tratamiento_linea("08", Decimal("13"), Decimal("12"))
    assert t.label == "1%"
    assert t.pct_efectiva == Decimal("1")
    assert t.es_no_sujeto is False

def test_codigo_01_exento():
    t = tratamiento_linea("01", Decimal("0"))
    assert t.label == "Exento"
    assert t.es_no_sujeto is False
```

- [ ] **Step 2: Copiar el fixture de venta con código 10**

Buscar en `C:\Users\Usuario\OneDrive\OFICINA\CONTAS\IVA\Agrofinca La Flor S&C Ltda\2026\5-May\` (con subcarpetas) un XML `FacturaElectronicaCompra` emitido por el cliente (`3102858282`) que tenga al menos una `LineaDetalle` con `CodigoTarifaIVA` = `10` — por ejemplo el consecutivo que contiene `0000001555` (líneas de Papa) o `0000001518` (Zanahoria). Copiarlo a `backend\tests\fixtures\venta_nosujeto.xml`. Verificar con un parseo rápido que tiene una línea código 10.

- [ ] **Step 3: Correr el test, confirmar que FALLA** (no existe `app.motor.tarifa`).

- [ ] **Step 4: Crear `app/motor/tarifa.py`**
```python
"""Tratamiento de IVA por línea: tarifa efectiva, etiqueta y No Sujeto.
Port de TARIFA_MAP y la lógica de exoneración del parse_xml.py viejo.
El No Sujeto (códigos 10/11) NO lleva la etiqueta 'Combustibles' del sistema viejo."""
from decimal import Decimal
from pydantic import BaseModel
from app.motor.schemas import LineaParsed

TARIFA_MAP: dict[str, tuple[str, Decimal]] = {
    "01": ("Exento", Decimal("0")),
    "02": ("1%", Decimal("1")),
    "03": ("2%", Decimal("2")),
    "04": ("4%", Decimal("4")),
    "08": ("13%", Decimal("13")),
    "10": ("No Sujeto", Decimal("0")),
    "11": ("No Sujeto", Decimal("0")),
    "13": ("13%", Decimal("13")),
}
CODIGOS_NO_SUJETO = {"10", "11"}

def _pct_label(pct: Decimal) -> str:
    if pct == pct.to_integral_value():
        return f"{int(pct)}%"
    return f"{pct.normalize()}%"

class Tratamiento(BaseModel):
    label: str            # Exento | 1% | 2% | 4% | 13% | No Sujeto
    pct_efectiva: Decimal
    es_no_sujeto: bool

def tratamiento_linea(tarifa_codigo: str, tarifa_pct: Decimal,
                      exon_tarifa: Decimal = Decimal("0")) -> Tratamiento:
    if tarifa_codigo in CODIGOS_NO_SUJETO:
        return Tratamiento(label="No Sujeto", pct_efectiva=Decimal("0"), es_no_sujeto=True)
    pct = tarifa_pct
    if exon_tarifa > 0:
        pct = max(Decimal("0"), tarifa_pct - exon_tarifa)
    if pct > 0:
        return Tratamiento(label=_pct_label(pct), pct_efectiva=pct, es_no_sujeto=False)
    return Tratamiento(label="Exento", pct_efectiva=Decimal("0"), es_no_sujeto=False)

def tratamiento_de(linea: LineaParsed) -> Tratamiento:
    return tratamiento_linea(linea.tarifa_codigo, linea.tarifa_pct, linea.exon_tarifa)
```

- [ ] **Step 5: Correr el test, confirmar que PASA** (4 passed). Luego toda la suite → 13 passed.

- [ ] **Step 6: Commit**
```
git add backend && git commit -m "feat(motor): tratamiento de IVA por linea con fix No Sujeto (sin Combustibles)"
```

---

## Tarea 3: Módulo `transforms` (nivel comprobante) + golden tests

**Files:**
- Modify: `backend/app/motor/schemas.py` (agregar `tipo` a `LineaParsed`)
- Create: `backend/app/motor/transforms.py`
- Create: `backend/tests/test_transforms.py`

- [ ] **Step 1: Agregar `tipo` a `LineaParsed`** en `app/motor/schemas.py`

Dentro de `class LineaParsed(BaseModel):`, agregar al final de los campos:
```python
    tipo: str = ""   # Bienes | Servicios (lo asigna apply_transforms)
```

- [ ] **Step 2: Escribir el test que falla `tests/test_transforms.py`**
```python
from decimal import Decimal
from pathlib import Path
from app.motor.parser import parse_comprobante_xml
from app.motor.transforms import apply_transforms

FIXT = Path(__file__).parent / "fixtures"

def test_factura_compra_es_bienes_y_positiva():
    comp = parse_comprobante_xml((FIXT / "fe_almacen_leon.xml").read_bytes())
    out = apply_transforms(comp)
    # No es nota de crédito: montos quedan positivos
    assert out.total_comprobante == Decimal("2099.99")
    # La factura es solo mercancías -> líneas tipo Bienes
    assert out.lineas[0].tipo == "Bienes"

def test_nota_credito_invierte_signo():
    comp = parse_comprobante_xml((FIXT / "fe_almacen_leon.xml").read_bytes())
    # Forzamos el tipo a nota de crédito para probar el signo (mismo monto, signo negativo)
    comp.tipo_doc = "NotaCreditoElectronica"
    out = apply_transforms(comp)
    assert out.total_comprobante == Decimal("-2099.99")
    assert out.total_iva == Decimal("-241.59")

def test_usd_se_convierte_a_crc():
    comp = parse_comprobante_xml((FIXT / "fe_almacen_leon.xml").read_bytes())
    comp.moneda = "USD"
    comp.tipo_cambio = Decimal("500")
    out = apply_transforms(comp)
    assert out.total_comprobante == Decimal("2099.99") * Decimal("500")
```

- [ ] **Step 3: Correr el test, confirmar que FALLA** (no existe `app.motor.transforms`).

- [ ] **Step 4: Crear `app/motor/transforms.py`**
```python
"""Transformaciones a nivel comprobante: conversión USD->CRC, signo negativo de
notas de crédito, y clasificación de líneas en Bienes/Servicios.
Port de _apply_transforms del parse_xml.py viejo. Devuelve una copia transformada."""
from decimal import Decimal
from app.motor.schemas import ComprobanteParsed

_SERV_UNITS = {"Sp", "h", "Al", "Os", "St", "I"}

_MONEY_FIELDS = [
    "total_serv_grav", "total_serv_exento", "total_serv_exon", "total_serv_no_sujeto",
    "total_merc_grav", "total_merc_exento", "total_merc_exon", "total_merc_no_sujeto",
    "total_gravado", "total_exento", "total_exonerado",
    "total_venta_neta", "total_descuentos", "total_iva",
    "total_otros_cargos", "total_comprobante",
]
_LINE_MONEY = ["monto_total", "descuento", "subtotal", "base_imponible",
               "iva_monto", "iva_neto", "precio_unitario"]

def apply_transforms(comp: ComprobanteParsed) -> ComprobanteParsed:
    c = comp.model_copy(deep=True)
    fx = c.tipo_cambio if (c.moneda == "USD" and c.tipo_cambio > 0) else Decimal("1")
    sign = Decimal("-1") if c.tipo_doc == "NotaCreditoElectronica" else Decimal("1")
    factor = fx * sign

    for fld in _MONEY_FIELDS:
        setattr(c, fld, getattr(c, fld) * factor)

    is_only_merc = abs(c.total_merc_grav) > 0 and c.total_serv_grav == 0
    is_only_serv = abs(c.total_serv_grav) > 0 and c.total_merc_grav == 0

    for ln in c.lineas:
        for lf in _LINE_MONEY:
            setattr(ln, lf, getattr(ln, lf) * factor)
        if sign == Decimal("-1"):
            ln.cantidad *= Decimal("-1")
        if is_only_merc:
            ln.tipo = "Bienes"
        elif is_only_serv:
            ln.tipo = "Servicios"
        else:
            ln.tipo = "Servicios" if ln.unidad in _SERV_UNITS else "Bienes"
    return c
```

Nota: `LineaParsed` no tiene campo `unidad` (1B-1 no lo extrajo). En el `else` usar `getattr(ln, "unidad", "")` para no romper; si más adelante se agrega `unidad` al parser, esta rama lo usará. Por ahora, como la mayoría de comprobantes son solo-bienes o solo-servicios, las dos primeras ramas cubren el caso común.

- [ ] **Step 5: Ajustar el `else` del tipo** para ser robusto sin `unidad`:
```python
        else:
            ln.tipo = "Servicios" if getattr(ln, "unidad", "") in _SERV_UNITS else "Bienes"
```

- [ ] **Step 6: Correr el test, confirmar que PASA** (3 passed). Luego toda la suite → 16 passed.

- [ ] **Step 7: Commit**
```
git add backend && git commit -m "feat(motor): transforms de comprobante (signo NC, USD, Bienes/Servicios)"
```

---

## Self-Review

- **Fix de No Sujeto** → Tarea 2: `tratamiento_linea` devuelve "No Sujeto" para códigos 10/11, y el test `test_codigo_10_es_no_sujeto_sin_combustibles` lo verifica sobre un XML real de venta agropecuaria. ✅ (resuelve el bug reportado)
- **Exoneración** → Tarea 2: `pct_efectiva = max(0, tarifa - exon_tarifa)`, con test 13%→1%. ✅
- **Signo de nota de crédito + USD** → Tarea 3: `apply_transforms`, con tests de signo negativo y conversión. ✅
- **Bienes/Servicios** → Tarea 3, port de la lógica vieja. ✅
- **Pendientes de la revisión 1B-1 cerrados** → Tarea 1: columnas que el resumen necesitará (`tarifa_label`, `tipo`), FK `cliente_id` SET NULL, comentario de `tipo_cambio`. ✅
- **Sin placeholders:** todo el código de `tarifa.py` y `transforms.py` está completo; los golden tests traen valores reales (208.../2099.99) y sintéticos. ✅
- **Consistencia:** `Tratamiento` y `apply_transforms` operan sobre `LineaParsed`/`ComprobanteParsed` de 1B-1; `tarifa_pct` cruda de entrada, `pct_efectiva` de salida. ✅

**Resultado:** el motor calcula el tratamiento de IVA correcto por línea (con el fix de No Sujeto) y aplica las transformaciones de comprobante. Base para el Plan 1B-3 (resumen por categoría + D-150 + ingesta).

---

## Próximo plan (1B-3)
Resumen por categoría (`build_resumen`/`build_resumen_ventas`: agrupa líneas en Bienes/Servicios × tarifa, con No Sujeto) → estructura del D-150 → golden test sobre los totales reales de Agrofinca mayo 2026 (compras: bienes 1% base 34.947.266, 13% base 1.269.904, no sujeto 1.370.942; ventas: bienes 1% base 34.749.174, 13% base 1.824.800, no sujeto 699.750). Luego el endpoint de ingesta (identificar cliente/rol por cédula, mapear parsed→ORM aplicando tarifa+transforms, período desde la fecha, upsert por clave, xml_raw).
