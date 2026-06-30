# Fase 1D (diferido) — Entradas manuales CRUD (diseño)

**Fecha:** 2026-06-27
**Estado:** diseño aprobado (brainstorming), pendiente de plan de implementación.

## Objetivo

Último slice de los diferidos de 1D: una página para gestionar (listar/crear/editar/eliminar)
las **entradas manuales** —ventas/compras que no vienen de XML, p.ej. subastas— que se
mezclan en el D-150. Hoy el backend tiene `POST`/`GET`/`DELETE` pero **no `PUT`**, y no
existe página en el frontend.

Se apoya en los slices anteriores (ya en main): patrones de frontend, `formatColones`,
y el helper `periodoApi` (el período del front es "YYYY-MM", el backend usa "YYYYMM").

## Alcance

### En alcance
- Backend: `EntradaManualOut` gana un campo `iva` calculado; `GET` pasa a devolver un
  objeto con totales; nuevo `PUT /api/entradas-manuales/{id}`.
- Frontend: hooks + `EntradasManualesPage` (tabla con totales + modal crear/editar +
  borrado) + sidebar/ruta.

### Fuera de alcance
- Tokens de agente (slice aparte, el que queda).
- Reglas/CABYS (ya hechos).
- Mostrar entradas manuales dentro de la vista de clasificación/resumen (diferido del D-150).

## Modelo (existente)

`EntradaManual`: `id`, `cliente_id`, `periodo` (YYYYMM), `rol` (compra/venta), `descripcion?`,
`monto` (Numeric 18,5), `tarifa` (Numeric), `no_sujeto` (bool), `deducible` (bool).
`EntradaManualCreate` valida: `rol ∈ {compra,venta}`, `periodo` = YYYYMM (6 dígitos, mes 01–12),
`monto`/`tarifa` ≥ 0. `EntradaManualOut` serializa `monto`/`tarifa` como string.

### IVA de una entrada (espeja `motor/d150.py` `_aplicar_manual`)

El IVA efectivo de una entrada gravada es `monto * tarifa / 100`. Con `tarifa == 0` el IVA es 0
(sea no-sujeta o exenta). Por eso: **`iva = (monto * tarifa / Decimal("100")).quantize(Q5)`**
(con `Q5 = Decimal("0.00001")`, igual que d150). El flag `deducible`/`no_sujeto` afecta el
tratamiento en el D-150 (se muestran como columnas), pero el IVA propio de la entrada es su
IVA bruto.

## Backend

- **`EntradaManualOut`**: agregar un campo calculado `iva` serializado como string. Como
  `EntradaManualOut` usa `from_attributes` desde el modelo ORM (que no tiene `iva`), se
  computa con un `@computed_field`. Decisión: un `@computed_field` `iva` en `EntradaManualOut`
  que lee `self.monto`/`self.tarifa` (ambos `Decimal` en el schema) y **devuelve directamente
  el string** `str((self.monto * self.tarifa / Decimal("100")).quantize(Decimal("0.00001")))`,
  para no depender del `field_serializer` y quedar consistente con cómo se serializan
  `monto`/`tarifa`.
- **Nuevo schema `EntradaManualListOut`**: `{ entradas: list[EntradaManualOut], total_monto: str, total_iva: str }`.
- **`GET /api/entradas-manuales`** (cambia su `response_model` a `EntradaManualListOut`):
  además de la lista, suma `total_monto = Σ monto` y `total_iva = Σ iva` en **Decimal** y los
  serializa como string. `rol` sigue siendo opcional en el query (la página siempre lo manda).
- **`PUT /api/entradas-manuales/{entrada_id}`** → `EntradaManualOut`: body `EntradaManualCreate`
  (reusa validación); actualiza `periodo/rol/descripcion/monto/tarifa/no_sujeto/deducible`;
  `cliente_id` no se reasigna; `404` si no existe; `422` si body inválido.

## Frontend

- **Hooks (`api/hooks.ts`):**
  - Tipos `EntradaManual` (= Out, con `iva`), `EntradaManualCreate`, `EntradasManualesResp`
    (`{ entradas, total_monto, total_iva }`).
  - `useEntradasManuales(clienteId, periodo, rol)` — `GET` con `periodoApi(periodo)`,
    `enabled` con cliente y período, queryKey `['entradas', clienteId, periodo, rol]`.
  - `useCrearEntrada` / `useEditarEntrada` / `useEliminarEntrada` — POST/PUT/DELETE;
    invalidan `['entradas', clienteId, periodo, rol]` y `['d150']` (las entradas alimentan el D-150).
- **`pages/EntradasManualesPage.tsx`:**
  - Lee cliente·período·rol del `SeleccionContext`. Guard si falta cliente o período.
  - Tabla: Descripción · Monto · Tarifa · No sujeto (✓/—) · Deducible (✓/—) · IVA · acciones.
    Montos/IVA con `formatColones`. **Footer:** total de monto y total de IVA (del backend).
  - **Un modal** (`@mantine/form`) para crear/editar (precargado en edición): descripción
    (texto), monto (NumberInput), tarifa (NumberInput), no_sujeto (Checkbox), deducible
    (Checkbox, default true). cliente·período·rol salen del contexto al guardar.
  - Eliminar: `Modal` de confirmación (no `window.confirm`).
  - Loading→Loader; error de carga→Alert con Reintentar.
- **Navegación:** `{ to: '/entradas-manuales', label: 'Entradas manuales' }` en `AppShell` + ruta.

## Datos y errores

- La página depende de cliente·período·rol globales; el período se normaliza con `periodoApi`.
- **422** (cliente inválido / validación) → inline en el modal (`ApiError.detail`).
- **404** al editar/eliminar (entrada borrada en paralelo) → notificación de error.
- Crear/editar/eliminar invalidan la query de entradas y la de `d150`.
- Dinero: monto/tarifa/iva/totales son strings del backend; `formatColones` para mostrar;
  **nunca** aritmética float en el front (por eso los totales vienen del backend).

## Testing

- **Backend (pytest, TDD):**
  - `EntradaManualOut.iva`: una entrada con monto/tarifa devuelve `iva` correcto (str);
    con tarifa 0 → iva "0...".
  - `GET` devuelve `{entradas, total_monto, total_iva}` con totales sumados en Decimal
    (varias entradas, incl. una no_sujeta tarifa 0).
  - `PUT`: edita (200 + cambios persistidos); 404 inexistente; 422 con body inválido
    (rol/período/monto negativo); 401 sin token.
- **Frontend (Vitest + RTL + MSW, wildcard):**
  - `useEntradasManuales` manda `periodo=YYYYMM` (periodoApi) y devuelve `{entradas, totales}`.
  - `EntradasManualesPage`: lista filas + footer de totales; crear; editar (PUT al id correcto);
    eliminar (DELETE al id correcto tras confirmar); guard sin cliente/período; 422 inline.

## Notas

- Fiel a los slices previos: `apiFetch`/`ApiError`, hooks TanStack, modal como en `ReglasPage`,
  MSW wildcard, env=test, dinero como string, `periodoApi` para el período.
- El cambio de forma del `GET` (lista → objeto con totales) no rompe a nadie: no hay consumidor
  actual de ese endpoint.
