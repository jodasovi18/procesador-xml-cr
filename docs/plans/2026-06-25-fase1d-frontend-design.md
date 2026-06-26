# Fase 1D — Frontend (diseño)

**Fecha:** 2026-06-25
**Estado:** diseño aprobado (brainstorming), pendiente de plan de implementación.

## Objetivo

Primer frontend web del Sistema XML CR sobre la API ya existente y completa. Cubre el
flujo central de la firma contable: **autenticarse → administrar clientes → subir
comprobantes XML → ver el resumen de IVA → ver el D-150**. Marca teal.

Single-tenant (una firma), uso interno. Prioridad: mostrar números correctos
(precisión tributaria) y andar pronto, por sobre estética a medida.

## Alcance

### En alcance (primera tanda)

| Pantalla     | API que consume                                                        |
|--------------|------------------------------------------------------------------------|
| Login        | `POST /auth/login` (form OAuth2), `GET /auth/me`                        |
| Clientes     | `GET /api/clientes`, `POST /api/clientes`                              |
| Subida XML   | `POST /api/ingesta/lote` (multipart; ZIP y/o varios XML)              |
| Resumen      | `GET /api/resumen`, `GET /api/resumen/clasificacion`                  |
| D-150        | `GET /api/d150`                                                        |

### Diferido (NO en esta tanda — fiel a CLAUDE.md)

- CRUD completo de reglas de clasificación (`/api/reglas` ya existe en backend).
- Auto-preclasificación por CABYS.
- Edición de entradas manuales (`/api/entradas-manuales`).
- Gestión de tokens de agente (admin, `/api/agent-tokens`).
- Reportes Excel/PDF (Fase 1E).

Estas quedan fuera, pero el sidebar se diseña para que entren después sin rediseño.

## Stack

- **Vite + React 18 + TypeScript** en `frontend/` (nuevo, separado del backend).
- **Mantine**: `@mantine/core`, `@mantine/hooks`, `@mantine/form`, `@mantine/dropzone`,
  `@mantine/notifications`, `@mantine/dates`.
- **React Router** para navegación.
- **TanStack Query** para todo acceso a la API (cache + estados loading/error).
- **Tema** Mantine con `primaryColor: 'teal'` definido en un único lugar.
- **Dev:** Vite proxy de `/api` y `/auth` → `http://localhost:8000`
  (sin CORS ni URLs hardcodeadas).
- **Pruebas:** Vitest + React Testing Library + MSW.

## Arquitectura — unidades con un propósito claro

- **`api/client.ts`** — wrapper `fetch`: adjunta `Authorization: Bearer <token>`,
  parsea JSON, lanza un error tipado (con status + detalle) en respuestas ≥400.
  Único módulo que conoce la forma de la API.
- **`api/hooks.ts`** — hooks TanStack Query/Mutation por endpoint
  (`useClientes`, `useCrearCliente`, `useResumen`, `useResumenClasificacion`,
  `useD150`, `useIngestaLote`). Las páginas no llaman `fetch` directo.
- **`auth/`** — `AuthContext` (token en `localStorage`), `LoginPage`,
  `RequireAuth` (redirige a `/login` si no hay sesión). En 401 global: limpia
  token y manda a login.
- **`context/SeleccionContext`** — estado global de **cliente / período / rol**,
  manipulado desde la barra superior; lo consumen Subida, Resumen y D-150.
- **`AppShell`** — sidebar (Clientes · Subida · Resumen · D-150) + barra superior
  de contexto (selectores cliente/período/rol + salir). Mantine `AppShell`.
- **Páginas:**
  - `ClientesPage` — tabla de clientes + modal de alta (`@mantine/form`).
  - `SubidaPage` — dropzone XML/ZIP → `/api/ingesta/lote`; tabla de reporte por
    archivo (nuevo / actualizado / omitido / error).
  - `ResumenPage` — tabs *Categoría* (`/api/resumen`) y *Clasificación*
    (`/api/resumen/clasificacion`).
  - `D150Page` — tabla débito / crédito / liquidación + toggle preciso ↔ OVI (entero).

Cada página depende sólo de sus hooks y de `SeleccionContext`: se entiende y se
prueba aislada.

## Navegación / layout

Opción elegida: **sidebar fijo + barra de contexto global**. El usuario elige
cliente y período **una sola vez** y se mantienen al navegar entre pantallas, que
es el flujo real (subir los XML de un cliente → ver su resumen → ver su D-150).

## Flujo de datos

1. Login → token a `localStorage` + `AuthContext`.
2. Usuario elige **cliente / período / rol** en la barra → `SeleccionContext`.
3. Cada página lee la selección y dispara su query; TanStack cachea por
   `[endpoint, cliente, periodo, rol]`.
4. **Dinero como string:** la API serializa `Decimal` → `str`. El front **formatea
   para mostrar y nunca hace aritmética en float**. (Coherente con la regla del
   repo: dinero siempre Decimal/Numeric.)
5. Subida: `FormData` multipart → al terminar invalida las queries de resumen/D-150
   para refrescar números.

### Notas de los selectores

- **Cliente:** `Select` poblado con `GET /api/clientes`.
- **Período:** entrada de mes que produce `"YYYY-MM"` (`@mantine/dates`
  `MonthPickerInput`). No hay endpoint que liste períodos disponibles; el usuario
  elige el mes. (Posible mejora futura: endpoint de períodos con datos.)
- **Rol:** `SegmentedControl` compra ↔ venta. (D-150 no usa rol; el resumen sí.)

## Errores

- **401** (token vencido/ausente) → limpiar sesión, ir a login.
- **422** (XML inválido) y reporte por archivo del lote → notificaciones
  (`@mantine/notifications`) + tabla de resultados por archivo.
- **409** (cédula de cliente duplicada) → mensaje inline en el formulario.
- **Red / 5xx** → estado de error de TanStack con botón "reintentar".

## Testing

- **Vitest + React Testing Library**, **MSW** para mockear la API.
- Cubrir: wrapper de API (incl. manejo de 401), formato de dinero, lógica del
  dropzone (parcial / omitido / error), y que cada página dispara su query con la
  selección correcta.
- TDD donde aplique, fiel a la convención del repo. Sin e2e por ahora.

## Fuera de alcance explícito

- Sin internacionalización (español únicamente).
- Sin tema oscuro.
- Sin tests end-to-end.
- Sin las pantallas diferidas listadas arriba.
