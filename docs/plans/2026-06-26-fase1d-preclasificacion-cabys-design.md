# Fase 1D (diferido) — Auto-preclasificación por CABYS y proveedor (diseño)

**Fecha:** 2026-06-26
**Estado:** diseño aprobado (brainstorming), pendiente de plan de implementación.

## Objetivo

Acelerar la clasificación: en vez de crear reglas una por una, surface las líneas que
hoy quedan **"Sin Clasificar"** para un cliente·período·rol, agrupadas por **CABYS** o
por **cédula del proveedor**, y permitir asignarles una clasificación en lote. Cada
asignación crea una regla (`reglas_clasificacion`), así que el efecto persiste para
períodos futuros (es la "memoria" del sistema). No hay catálogo CABYS→clasificación: es
un **asistente de asignación**, no adivinación automática.

Se apoya en el slice anterior (Reglas CRUD, ya en main): reutiliza `POST /api/reglas`,
el engine de clasificación y los patrones de frontend.

## Alcance

### En alcance
- Motor: agrupar las líneas "Sin Clasificar" por CABYS o por cédula.
- Endpoint: `GET /api/preclasificacion`.
- Frontend: `PreclasificarPage` (dos pestañas, asignación en lote) + sidebar/ruta.
- Guardado: reusa `POST /api/reglas` (sin endpoint de lote nuevo).

### Fuera de alcance
- Catálogo CABYS→clasificación / sugerencia automática (otro slice si se quiere).
- Edición de entradas manuales; tokens de agente (slices aparte).
- Endpoint de creación de reglas en lote (se reusa el POST existente).

## Concepto: qué es "Sin Clasificar"

El engine `clasificar(cedula, cabys, rol, lookup)` (en `motor/clasificacion.py`) devuelve
`("Sin Clasificar", "")` cuando ninguna regla del cliente matchea. La preclasificación
recorre las líneas guardadas (`LineaComprobante` join `Comprobante`) del cliente·período·rol
y se queda con esas. La cédula de la contraparte es `emisor_cedula` en compra y
`receptor_cedula` en venta (igual que en `motor/resumen.py`).

Prioridad del engine: `céd+CABYS` > `CABYS` > `céd(+rol)`. Por eso reglas por CABYS y por
cédula conviven; CABYS gana sobre cédula cuando ambas aplican.

## Motor — `backend/app/motor/preclasificacion.py`

```
grupos_sin_clasificar(db, cliente_id, periodo, rol, por) -> list[Grupo]
```
- `por ∈ {"cabys", "cedula"}`.
- Reusa `build_lookup(reglas del cliente)` + `clasificar(...)` para filtrar las líneas
  cuya clasificación es `"Sin Clasificar"`.
- Agrupa por la clave elegida:
  - `cabys`: clave = `linea.cabys`; etiqueta = un `linea.detalle` de muestra (el primero no vacío).
  - `cedula`: clave = cédula de la contraparte; etiqueta = nombre de la contraparte
    (`emisor_nombre`/`receptor_nombre`).
- Cada `Grupo`: `{clave: str, etiqueta: str, lineas: int, base: Decimal}` donde `base` es la
  suma de `base_imponible`. Líneas con clave vacía (`cabys`/cédula en blanco) se omiten o
  se agrupan bajo clave vacía — **decisión: omitir las de clave vacía** (no se puede crear
  una regla útil sin clave).
- Devuelve la lista ordenada por `base` descendente.

Unidad pura sobre la sesión de DB; se prueba con datos reales/fixtures.

## Endpoint

`GET /api/preclasificacion?cliente_id={int}&periodo={YYYYMM}&rol={compra|venta}&por={cabys|cedula}`
- Auth `get_current_user`.
- `por` default `"cabys"`; valida `por ∈ {cabys, cedula}` y `rol ∈ {compra, venta}`
  (422 si inválidos).
- Responde `[{clave, etiqueta, lineas, base}]` con `base` serializado como string
  (Decimal→str, coherente con el resto de la API).

## Guardado (reusa `POST /api/reglas`)

No se agrega endpoint de lote. El frontend, al guardar la pestaña activa, hace un
`POST /api/reglas` por cada fila asignada, con `Promise.allSettled` y reporte por fila:
- Pestaña **CABYS** → `{cliente_id, cabys: clave, clasificacion, sub_clasificacion?, rol: null}`
  (las reglas por CABYS son rol-agnósticas).
- Pestaña **cédula** → `{cliente_id, cedula: clave, clasificacion, sub_clasificacion?, rol: <rol actual>}`
  (las reglas por cédula se separan por rol en el engine).
Tras guardar, invalida las queries de `preclasificacion`, `reglas` y `resumen` para que lo
asignado desaparezca del asistente y se refleje en el resumen.

## Frontend

- **Hook** `usePreclasificacion(clienteId, periodo, rol, por)` — `GET /api/preclasificacion`,
  `enabled` solo con cliente y período, queryKey `['preclasificacion', clienteId, periodo, rol, por]`.
- **`pages/PreclasificarPage.tsx`:**
  - Guard si falta cliente o período → `Alert` "Elegí cliente y período en la barra superior."
  - `Tabs`: **Por CABYS** / **Por proveedor**. Cada panel usa `usePreclasificacion` con su `por`.
  - Tabla por grupo: clave · etiqueta · líneas · base (`formatColones`) · `Select` de clasificación
    (los 5 valores) · (solo CABYS) input de sub-clasificación opcional.
  - Estado local de asignaciones (clave→{clasificacion, sub}); botón **"Guardar"** que hace los
    POST de las filas con clasificación elegida. Reporte de resultado (n creadas, errores) por
    `@mantine/notifications`.
  - Empty-state cuando no hay grupos: "No hay líneas sin clasificar para este período/rol."
  - Estados loading/error con Reintentar.
- **Navegación:** entrada `{ to: '/preclasificar', label: 'Preclasificar' }` en `AppShell` + ruta en `App.tsx`.

Reusa: `formatColones`, `apiFetch`/`ApiError`, `useCrearRegla` (o un wrapper que haga los POST),
`SeleccionContext`, patrón de tabla/tabs, MSW wildcard, `renderWithProviders` (env=test).

## Errores

- Endpoint: `por`/`rol` inválidos → 422; sin token → 401.
- Guardado: cada POST puede fallar (p.ej. 422 si la regla ya existe por carrera) →
  `Promise.allSettled`; se notifica cuántas se crearon y cuántas fallaron, sin abortar el resto.
- Frontend: guard sin cliente/período; loading/error con reintentar; empty-state.
- Dinero: la base se muestra con `formatColones` (string), nunca aritmética float.

## Testing

- **Backend (pytest, TDD):**
  - Motor `grupos_sin_clasificar`: agrupa por CABYS y por cédula; excluye líneas ya cubiertas
    por una regla existente; suma `base`; omite clave vacía; ordena por base desc. Usar un
    fixture de comprobante real (`fe_almacen_leon.xml`) + alguna regla para verificar exclusión.
  - Endpoint: 200 con datos; `por` inválido → 422; `rol` inválido → 422; 401 sin token.
- **Frontend (Vitest + RTL + MSW, wildcard):**
  - `usePreclasificacion` pasa `cliente_id/periodo/rol/por` y devuelve grupos; idle sin cliente/período.
  - `PreclasificarPage`: lista grupos de la pestaña CABYS; cambia a "Por proveedor" y lista por cédula;
    asignar una clasificación + Guardar dispara `POST /api/reglas` con `cabys` y `rol:null` (pestaña CABYS)
    y con `cedula` y `rol` del contexto (pestaña proveedor); empty-state; guard sin selección.

## Notas

- Fiel a 1D: `apiFetch`/`ApiError`, hooks TanStack, Mantine, MSW wildcard, env=test, dinero como string.
- El motor de preclasificación NO escribe en la columna `clasificacion` de la línea (esa columna
  queda sin usar, como hoy); la clasificación vive en reglas y se aplica al vuelo.
