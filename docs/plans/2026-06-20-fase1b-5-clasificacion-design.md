# Fase 1B-5: Capa de Clasificación — Diseño

> Documento de diseño (spec). El plan de implementación con pasos TDD va aparte:
> `docs/plans/2026-06-20-fase1b-5-clasificacion.md`.

## Objetivo

Clasificar cada línea de compra/venta según **reglas por proveedor/CABYS** en las
categorías `Compras`, `Gastos`, `Bienes de Capital`, `No Deducibles`
(`Sin Clasificar` como fallback), con **sub-clasificación** opcional (la relevante:
`Combustibles`). La clasificación habilita:

1. Que el **resumen tributario** de compras refleje la realidad contable
   (excluyendo No Deducibles del crédito fiscal y reclasificando Combustibles a
   No Sujeto) — es la pieza que falta para que las **COMPRAS reconcilien**.
2. Una **vista de gestión** Clasificación × Tasa (gastos por categoría).

**Meta de éxito (esta fase):** engine de clasificación + resúmenes con golden
tests verdes que codifiquen la semántica correcta (prioridad de lookup,
Combustibles→No Sujeto, No Deducibles segregado, separación de rol). La
reconciliación completa contra Agrofinca mayo 2026 se difiere (requiere el
`clasificaciones.json` real del contador, que **no está en esta máquina**).

## Contexto

Estado previo (Fase 1B-1…1B-4): parser, tarifa+transforms, ingesta idempotente y
`build_resumen` (agrega líneas por categoría `{tipo} {tarifa_label}`, con
`No Sujeto` para códigos 10/11). Las **VENTAS reconcilian exacto**; las **COMPRAS
no**, porque el sistema viejo aplica una capa de clasificación que el motor nuevo
aún no tiene.

`LineaComprobante` **ya tiene** columnas `clasificacion` y `sub_clasificacion`
(nullable, hoy sin poblar).

### Hallazgos del sistema viejo (`parse_xml.py`)

- **Reglas** en `clasificaciones.json`: por `cedula_emisor`, por `cabys`, o
  combinadas; con separación de rol (proveedor de compra vs. comprador en venta).
- **Lookup con prioridad** (`build_clasificacion_lookup` + `classify_line`):
  `(cédula+cabys) > cabys > cédula`. La cédula sola se separa por rol
  (`by_ced` compra / `by_ced_venta` venta); las reglas con cabys son
  rol-agnósticas. Fallback: `('Sin Clasificar', '')`.
- **Dos resúmenes con semántica distinta de No Sujeto** (clave):
  - `build_resumen` *tributario* (alimenta el D-150; lo usan las ventas que ya
    reconcilian): `No Sujeto` = código 10/11 **o** Combustibles; **No Deducibles
    segregado** del total deducible.
  - `build_resumen_clasificacion` (vista de gestión Sheet 5): `No Sujeto` =
    **solo** Combustibles; los códigos 10/11 caen en Exento.
- **D-150** (`calcular_d150`): usa el `build_resumen` tributario sobre
  `compras_deducibles` (excluye `TiqueteElectronico` por Decreto 44739-H);
  No Deducibles y No Sujeto quedan **fuera del crédito fiscal**.

## Decisiones de diseño

### 1. Clasificación al vuelo (no estampada)

La tabla de reglas es la **fuente de verdad**. Los resúmenes derivan la
clasificación por línea en el momento de la consulta (la query ya une
`Comprobante`, de donde sale la cédula). Las columnas
`clasificacion`/`sub_clasificacion` de `LineaComprobante` quedan **reservadas**
para overrides manuales por línea en una fase futura; no se usan ahora.

**Razón:** la ingesta idempotente borra+reinserta líneas, así que estampar
obligaría a re-aplicar tras cada ingesta/cambio de regla (riesgo de datos
stale). Al vuelo siempre está consistente con las reglas actuales y concentra la
lógica en un único lugar testeable. A esta escala (una firma, miles de líneas/mes)
el costo de recomputar es irrelevante.

### 2. Combustibles → No Sujeto sin importar la tarifa XML

Una línea cuya regla le asigna `sub_clasificacion = "Combustibles"` se trata
como **No Sujeto** (base imponible al bucket No Sujeto, **IVA = 0**),
**aunque su tarifa XML sea 08/13%**. Es la intención documentada en CLAUDE.md
(Ley 9635: combustibles y derivados del petróleo no sujetos a IVA; su IVA no es
crédito fiscal).

> Nota: el `build_resumen` tributario viejo solo hacía esta reclasificación
> cuando la tarifa era 0% — inconsistente con `build_resumen_clasificacion` y con
> la intención documentada. El motor nuevo implementa la intención (reclasifica
> siempre). Esto se valida con golden test y se confirmará en la reconciliación
> completa cuando estén las reglas reales.

### 3. No Deducibles segregado

Las líneas clasificadas `No Deducibles` van a un bucket propio `No Deducibles`
(base + IVA), **excluido** de las categorías deducibles. No generan crédito
fiscal (lo consume el D-150 en la fase siguiente).

### 4. Separación de rol

La clave de clasificación es la **contraparte**: en `compra` = `emisor_cedula`
(proveedor); en `venta` = `receptor_cedula` (comprador). Las reglas de cédula
sola se filtran por rol; las de cabys (solas o con cédula) son rol-agnósticas.

### 5. La vista de clasificación usa `tarifa_label`

`build_resumen_clasificacion` agrupa por `clasificacion` × `tarifa_label`
existente (con el override Combustibles→No Sujeto). Esto deja los códigos
10/11 en `No Sujeto` (no en Exento), divergiendo a propósito del Sheet 5 viejo:
es más consistente con el resto del motor y la vista es informativa, no legal.

## Componentes

### A. Modelo `ReglaClasificacion` (`models/regla_clasificacion.py`)

| campo               | tipo                | nota                                   |
|---------------------|---------------------|----------------------------------------|
| `id`                | int PK              |                                        |
| `cliente_id`        | FK clientes         | reglas por cliente                     |
| `cedula`            | str(20), nullable   | contraparte (proveedor/comprador)      |
| `cabys`             | str(20), nullable   |                                        |
| `rol`               | str(10), nullable   | `compra`/`venta`; solo aplica a regla de cédula sola |
| `clasificacion`     | str(40)             | en `CLASIFICACIONES_VALID`             |
| `sub_clasificacion` | str(60), nullable   | p.ej. `Combustibles`                   |

Validación: al menos uno de `cedula`/`cabys` presente; `clasificacion` válida.
Migración Alembic autogenerada.

### B. Engine `motor/clasificacion.py`

```python
CLASIFICACIONES_VALID = {"Compras", "Gastos", "Bienes de Capital",
                         "No Deducibles", "Sin Clasificar"}
SUBCATEGORIAS_NO_SUJETO = {"Combustibles"}

def build_lookup(reglas: list[ReglaClasificacion]) -> Lookup: ...
def clasificar(cedula: str|None, cabys: str|None, rol: str,
               lookup: Lookup) -> tuple[str, str]:
    # prioridad: (céd+cabys) > cabys > céd(+rol); fallback ("Sin Clasificar", "")
```

`Lookup` = dataclass con los dicts `by_ced_cabys`, `by_cabys`, `by_ced`,
`by_ced_venta`. Puro, sin DB (recibe las reglas ya cargadas).

### C. Resúmenes (`motor/resumen.py`)

- `build_resumen(db, cliente_id, periodo, rol)` — **modificado** para ser
  clasificación-aware: carga reglas del cliente, construye el lookup, y por línea
  aplica: No Deducible → bucket segregado; Combustibles → No Sujeto (IVA 0); resto
  igual que hoy. **Retrocompatible:** las categorías se crean por demanda
  (`setdefault`), igual que hoy; sin reglas, toda línea cae en la rama actual y el
  resultado es idéntico (no se inyectan buckets vacíos → no rompe los asserts de
  claves exactas existentes).
- `build_resumen_clasificacion(db, cliente_id, periodo, rol)` — **nuevo**:
  `{clasificacion: {tarifa_label: {"base", "iva"}}}`.

### D. Endpoints

- `GET /api/resumen/clasificacion?cliente_id&periodo&rol` — la vista nueva.
- `POST /api/reglas` (crear) y `GET /api/reglas?cliente_id` (listar) — mínimo para
  administrar reglas vía API. CRUD completo (editar/borrar) y UI → fase frontend.
- Todos protegidos por JWT (como el resto).

## Flujo de datos

```
ingesta (sin cambios) → líneas crudas en DB (clasificacion = NULL)
                                        │
reglas (POST /api/reglas) → tabla reglas_clasificacion
                                        │
GET /api/resumen[...]  ─┐               ▼
GET /api/resumen/clasif ┴─► build_lookup(reglas del cliente)
                            └─► por línea: clasificar(céd, cabys, rol) → agregar
```

## Estrategia de pruebas (TDD estricto)

Golden tests controlados, portables y deterministas (patrón de la fase resumen):

1. **Lookup/prioridad** — (céd+cabys) gana a cabys gana a céd; separación de rol;
   fallback Sin Clasificar.
2. **No Deducibles** — línea cuyo proveedor es No Deducible sale del total
   deducible y aparece en el bucket `No Deducibles`.
3. **Combustibles→No Sujeto** — línea código 08/13% con sub_clas Combustibles cae
   en `No Sujeto` con IVA 0 (no en `Bienes 13%`).
4. **Resumen por clasificación** — agrupa correcto por clasificación × tarifa.
5. **Endpoints** — `/api/resumen/clasificacion` y `/api/reglas` (POST+GET),
   401 sin token.

Fixtures: reutilizar los XML reales ya presentes en `backend/tests/fixtures`
(`fe_almacen_leon.xml`, `venta_nosujeto.xml`, etc.) + reglas creadas en el test.

## Fuera de alcance (fases posteriores)

- Auto-preclasificación por prefijo CABYS (`preclass_cabys`, sugerencias).
- CRUD completo de reglas (editar/borrar) y UI de clasificación (fase frontend 1D).
- Detección de facturas mixtas (Combustibles + gravado en la misma factura).
- Plan de cuentas / cuenta contable por clasificación.
- D-150 (fase siguiente, consume estos resúmenes).
- Reconciliación completa Agrofinca (requiere el `clasificaciones.json` real).

## Riesgos / supuestos

- **Semántica Combustibles**: se asume la intención documentada (reclasifica a
  No Sujeto siempre), no el comportamiento literal del `build_resumen` tributario
  viejo. A confirmar en la reconciliación completa.
- **Reglas reales ausentes**: la validación fuerte (reconciliación al colón) queda
  pendiente hasta tener el `clasificaciones.json` del contador. Los golden tests
  cubren la lógica, no los montos reales de mayo.
