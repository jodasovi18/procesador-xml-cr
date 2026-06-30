# Fase 1D (diferido) — Gestión de tokens de agente (diseño)

**Fecha:** 2026-06-27
**Estado:** diseño aprobado (brainstorming), pendiente de plan de implementación.

## Objetivo

Último diferido de 1D: una página **admin** para crear, listar y revocar los tokens de
agente (los que usa el agente local para subir XML sin password). El backend ya está
completo (`POST`/`GET`/`DELETE /api/agent-tokens`, todo `requiere_admin`); esto es solo
el frontend. El token en claro se muestra **una sola vez** al crearlo (el backend guarda
solo el sha256).

Slice **solo frontend** (sin cambios de backend). Se apoya en los slices previos (ya en main):
patrones de hooks/página, `AuthContext`, `RequireAuth`.

## Alcance

### En alcance
- Extender `AuthContext` para conocer si el usuario es admin (`/auth/me`).
- `RequireAdmin` (guard) + ocultar el ítem del sidebar a no-admins.
- Hooks de tokens + `AgentTokensPage` (crear con revelado único / listar / revocar) + ruta.

### Fuera de alcance
- Cambios de backend (ya completo).
- Edición de tokens (no aplica: se revoca y se crea otro).
- Keyring/rotación automática (diferidos del agente, no de 1D).

## Backend (existente, sin cambios)

- `POST /api/agent-tokens` (admin) — body `AgentTokenCreate{label}` (label no vacío, ≤120);
  responde `AgentTokenCreated{id, label, token}` con el **token en claro una sola vez** (422 si label vacío).
- `GET /api/agent-tokens` (admin) — `list[AgentTokenOut{id, label, created_at}]` (sin token).
- `DELETE /api/agent-tokens/{id}` (admin) — 204; 404 si no existe.
- `GET /auth/me` → `{id, nombre, es_admin}` (ya existe).
- No-admin → 403 en las rutas de tokens (`requiere_admin`).

## Conocer el admin — extensión de `AuthContext`

`main.tsx` monta `QueryClientProvider` por encima de `AuthProvider`, así que el provider
puede usar TanStack Query.

- En `AuthProvider`: agregar una query
  `useQuery({ queryKey: ['me'], queryFn: () => apiFetch<Me>('/auth/me'), enabled: !!token })`
  donde `Me = { id: number; nombre: string; es_admin: boolean }`.
- Exponer en el contexto `esAdmin: boolean = meQuery.data?.es_admin ?? false`.
- En `logout`: además de limpiar el token, `queryClient.removeQueries({ queryKey: ['me'] })`
  para no filtrar el flag admin entre sesiones de usuarios distintos.
- Mientras `/auth/me` carga, `esAdmin` es `false` (el link aparece al confirmarse admin).

## Gating

- **`auth/RequireAdmin.tsx`**: usa `useAuth()`; si `!esAdmin` → `Alert` "Requiere permisos de
  administrador." (no redirige a login: el usuario está autenticado, solo no es admin).
- **`AppShell`**: el ítem `{ to: '/agent-tokens', label: 'Tokens de agente' }` se renderiza
  **solo si `esAdmin`** (los demás links no cambian).
- **`App.tsx`**: la ruta `/agent-tokens` se envuelve con `<RequireAdmin>`.

## Hooks + página

- **Hooks (`api/hooks.ts`):**
  - Tipos `AgentToken { id, label, created_at }`, `AgentTokenCreado { id, label, token }`.
  - `useAgentTokens()` — `GET /api/agent-tokens`, queryKey `['agent-tokens']`.
  - `useCrearAgentToken()` — `POST` con `{label}` → `AgentTokenCreado`; invalida `['agent-tokens']`.
  - `useRevocarAgentToken()` — `DELETE /api/agent-tokens/{id}`; invalida `['agent-tokens']`.
- **`pages/AgentTokensPage.tsx`:**
  - Form: `TextInput` de etiqueta + botón "Crear token". Al crear con éxito, guarda el
    `AgentTokenCreado` en estado y muestra un **bloque de revelado**: el token en
    monoespaciado + botón "Copiar" (`navigator.clipboard.writeText`) + aviso "No se vuelve a
    mostrar". Persistente hasta descartarlo (botón "Listo") o crear otro. Limpia el input.
  - Tabla: Etiqueta · Creado (`created_at` formateado con dayjs `YYYY-MM-DD HH:mm`) · revocar.
  - Revocar: `Modal` de confirmación → `DELETE`.
  - 422 (etiqueta vacía) → inline cerca del form. Loading→Loader; error de carga→Alert+Reintentar.

## Datos y errores

- La página no usa cliente/período/rol (es admin global).
- 422 (label vacío) → mensaje inline. 404 al revocar (token ya borrado) → notificación.
- 403 no debería ocurrir (la página está gateada), pero si una llamada lo devuelve, se
  muestra el `ApiError.detail`.
- Sin dinero en esta página.

## Testing (Vitest + RTL + MSW, wildcard; sin backend nuevo)

- **`AuthContext`**: con `/auth/me` devolviendo `es_admin: true`, `useAuth().esAdmin` es `true`;
  con `false`, es `false`. (Un componente sonda que muestre el flag.)
- **`AppShell`**: con admin, aparece el link "Tokens de agente"; sin admin (o sin `/auth/me`),
  **no** aparece. (MSW para `/auth/me` + `/api/clientes`.)
- **`RequireAdmin`**: con admin renderiza children; sin admin muestra "Requiere permisos de administrador.".
- **Hooks**: `useAgentTokens` lista; `useCrearAgentToken` devuelve `{token}`; `useRevocarAgentToken` hace DELETE al id.
- **`AgentTokensPage`**: crear muestra el token revelado en pantalla; revocar dispara DELETE al id tras confirmar; lista los tokens.

## Notas

- Fiel a los slices previos: `apiFetch`/`ApiError`, hooks TanStack, modal como en `ReglasPage`,
  MSW wildcard, env=test, `renderWithProviders`.
- `RequireAuth` ya envuelve toda la app autenticada; `RequireAdmin` es una segunda capa
  específica para esta ruta.
- El `AuthContext` extendido necesita estar dentro de `QueryClientProvider` (ya lo está en `main.tsx`).
