# Fase 1D (diferido) — Reglas de clasificación CRUD (diseño)

**Fecha:** 2026-06-26
**Estado:** diseño aprobado (brainstorming), pendiente de plan de implementación.

## Objetivo

Primer slice de los diferidos de 1D: gestión completa (alta/listado/edición/baja) de las
**reglas de clasificación** por cliente, desde el frontend. Hoy el backend solo expone
`GET`/`POST /api/reglas`; falta editar y eliminar, y no existe página en el frontend.

Las reglas alimentan el engine de clasificación (`motor/clasificacion.py`) que segrega
gastos/compras/no-deducibles y aplica el tratamiento No Sujeto (Combustibles). Poder
editarlas desde la UI es la base de los demás diferidos (la auto-preclasificación por
CABYS, slice siguiente, se apoya en este CRUD).

## Alcance

### En alcance
- Backend: `PUT /api/reglas/{id}` (editar) y `DELETE /api/reglas/{id}` (eliminar).
- Frontend: página `ReglasPage` (listar/crear/editar/eliminar) + entrada "Reglas" en el sidebar.

### Fuera de alcance (otros slices / futuro)
- Auto-preclasificación por CABYS (slice siguiente).
- Edición de entradas manuales (slice aparte).
- Gestión de tokens de agente (slice aparte).
- Reordenar reglas / prioridad manual (la prioridad es por especificidad del match, no editable).

## Modelo de una regla (existente)

`ReglaClasificacion`: `id`, `cliente_id`, `cedula?`, `cabys?`, `rol?`, `clasificacion`,
`sub_clasificacion?`. Reglas de validación (en `schemas/regla.py`):
- `clasificacion` ∈ `{Compras, Gastos, Bienes de Capital, No Deducibles, Sin Clasificar}`.
- `rol` ∈ `{compra, venta}` o nulo (cualquiera).
- Se requiere **al menos** `cedula` o `cabys`.
- `sub_clasificacion` libre; `"Combustibles"` fuerza tratamiento No Sujeto.
- Prioridad de match en el engine: `céd+cabys` > `cabys` > `céd(+rol)`.

## Backend

Dos endpoints nuevos en `backend/app/routers/reglas.py` (auth: `get_current_user`, como el resto):

- **`PUT /api/reglas/{regla_id}`** → `ReglaOut`
  - Body: `ReglaCreate` (reusa la validación: clasificación válida, rol válido, al menos
    cédula o cabys). Actualiza `cedula/cabys/rol/clasificacion/sub_clasificacion` de la fila.
  - `cliente_id` del body se ignora para reasignar dueño: la regla queda en su `cliente_id`
    original (no se permite mover una regla de cliente en la edición).
  - `404` si la regla no existe. `422` si el body es inválido (reusa validadores del schema).
- **`DELETE /api/reglas/{regla_id}`** → `204`
  - `404` si no existe.

## Frontend

- **Sidebar:** agregar `{ to: '/reglas', label: 'Reglas' }` a `AppShell` y la ruta en `App.tsx`.
- **`api/hooks.ts`:** tipos `Regla` (= `ReglaOut`) y `ReglaCreate`; hooks:
  - `useReglas(clienteId)` — `GET /api/reglas?cliente_id=...`, `enabled` solo con cliente,
    `queryKey ['reglas', clienteId]`.
  - `useCrearRegla()` — `POST`, invalida `['reglas', clienteId]`.
  - `useEditarRegla()` — `PUT /api/reglas/{id}`, invalida `['reglas', clienteId]`.
  - `useEliminarRegla()` — `DELETE /api/reglas/{id}`, invalida `['reglas', clienteId]`.
- **`pages/ReglasPage.tsx`:**
  - Lee `clienteId` de `SeleccionContext`. Si es null → `Alert` "Elegí un cliente en la barra superior."
  - Tabla: Cédula · CABYS · Rol · Clasificación · Sub-clasif. · acciones (editar/eliminar).
    Valores nulos se muestran como "—". Orden por id (orden de creación).
  - **Un modal** (`@mantine/form`) para crear y editar: en edición se precargan los valores
    de la regla; al guardar llama crear o editar según el caso. Campos: cédula, CABYS
    (al menos uno — validación inline), rol (Select compra/venta/—), clasificación (Select
    con los 5 valores), sub-clasificación (texto, hint Combustibles→No Sujeto).
  - Eliminar: confirmación con un `Modal` de Mantine (no `window.confirm`, que no se testea
    bien; sin agregar `@mantine/modals`) antes del DELETE.
  - Estados: loading → `Loader`; error de carga → `Alert` con Reintentar.

## Datos y errores

- La página depende de `clienteId` global; no usa período ni rol (las reglas no son por período).
- **422** (clasificación inválida o falta cédula/cabys) → mensaje inline (`ApiError.detail`) en el modal.
- **404** al editar/eliminar (regla borrada en paralelo) → notificación de error.
- Las mutaciones invalidan la query de reglas del cliente para refrescar la tabla.
- Dinero: no aplica en esta página (las reglas no manejan montos).

## Testing

- **Backend (pytest, TDD):**
  - PUT: edita una regla existente (200 + cambios persistidos); 404 si no existe;
    422 con clasificación inválida; 422 si se deja sin cédula y sin cabys.
  - DELETE: 204 y la regla desaparece; 404 si no existe.
- **Frontend (Vitest + RTL + MSW, convención `*/...` wildcard):**
  - Lista las reglas del cliente.
  - Crear: abre modal, completa, guarda, aparece en la tabla (o invalida y refetchea).
  - Editar: abre modal precargado, cambia clasificación, guarda → PUT con el id correcto.
  - Eliminar: confirma → DELETE con el id correcto.
  - Guard: sin cliente seleccionado muestra el mensaje, no dispara la query.
  - 422 inline en el modal al recibir error de validación.

## Notas

- Seguir patrones de 1D: `apiFetch`/`ApiError`, hooks TanStack, `renderWithProviders`
  (env=test), modal igual que `ClientesPage`, MSW wildcard, sin aritmética de dinero.
- El backend valida dominios de `clasificacion`/`rol`; el frontend usa Selects para no
  enviar valores inválidos, pero igual maneja el 422 por robustez.
