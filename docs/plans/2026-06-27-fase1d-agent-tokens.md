# Gestión de tokens de agente (diferido 1D) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Página admin para crear (con revelado único del token), listar y revocar tokens de agente, gateada por un nuevo `esAdmin` derivado de `/auth/me`.

**Architecture:** Solo frontend (el backend `/api/agent-tokens` y `/auth/me` ya existen). `AuthContext` gana `esAdmin` vía una query `['me']`. `RequireAdmin` gatea la ruta y `AppShell` oculta el link a no-admins. Hooks TanStack + `AgentTokensPage`.

**Tech Stack:** React/Mantine 7/TanStack Query/Vitest+RTL+MSW. Sin backend nuevo.

---

## Convenciones (leer antes de empezar)

- Spec: `docs/plans/2026-06-27-fase1d-agent-tokens-design.md`.
- Worktree: `C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\.claude\worktrees\reverent-lederberg-08f91d`. Rama `claude/fase1d-agent-tokens` (desde main).
- **Frontend** (desde `frontend/`): `npx vitest run <file>`, `npx tsc -b`, `npm run build`. Vitest globals on. MSW `*/...` wildcard. `renderWithProviders` (Mantine env=test + Notifications + QueryClient retry:false + MemoryRouter). **No se necesita PostgreSQL** (no hay tests de backend en este slice).
- Backend existente: `POST /api/agent-tokens` (admin) `{label}` → `{id,label,token}` (token en claro 1 vez; 422 si label vacío); `GET /api/agent-tokens` (admin) → `[{id,label,created_at}]`; `DELETE /api/agent-tokens/{id}` (admin) 204/404; `GET /auth/me` → `{id,nombre,es_admin}`.
- `main.tsx` monta `QueryClientProvider` por encima de `AuthProvider` → el provider puede usar `useQuery`.
- Commits: uno por tarea, español.

## Estructura de archivos

```
frontend/src/auth/AuthContext.tsx       # + esAdmin vía query ['me']; logout limpia ['me']
frontend/src/auth/RequireAdmin.tsx       # nuevo guard
frontend/src/auth/RequireAdmin.test.tsx  # esAdmin + gating
frontend/src/api/hooks.ts                # hooks de agent-tokens + tipos
frontend/src/api/hooks.test.tsx          # test de hooks
frontend/src/pages/AgentTokensPage.tsx
frontend/src/pages/AgentTokensPage.test.tsx
frontend/src/components/AppShell.tsx      # link condicional a esAdmin
frontend/src/components/AppShell.test.tsx # link con/sin admin
frontend/src/App.tsx                      # ruta /agent-tokens con RequireAdmin
```

---

### Task 1: `AuthContext.esAdmin` + `RequireAdmin`

**Files:**
- Modify: `frontend/src/auth/AuthContext.tsx`
- Create: `frontend/src/auth/RequireAdmin.tsx`
- Test: `frontend/src/auth/RequireAdmin.test.tsx`

- [ ] **Step 1: Escribir el test que falla** (`frontend/src/auth/RequireAdmin.test.tsx`)

```tsx
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../test/utils';
import { AuthProvider, useAuth } from './AuthContext';
import { RequireAdmin } from './RequireAdmin';
import { setToken, clearToken } from '../api/client';

const server = setupServer();
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => { server.resetHandlers(); clearToken(); });

function Sonda() {
  const { esAdmin } = useAuth();
  return <div>admin:{String(esAdmin)}</div>;
}

it('expone esAdmin=true desde /auth/me', async () => {
  server.use(http.get('*/auth/me', () => HttpResponse.json({ id: 1, nombre: 'a', es_admin: true })));
  setToken('tok');
  renderWithProviders(<AuthProvider><Sonda /></AuthProvider>);
  expect(await screen.findByText('admin:true')).toBeInTheDocument();
});

it('RequireAdmin bloquea a no-admin', async () => {
  server.use(http.get('*/auth/me', () => HttpResponse.json({ id: 1, nombre: 'a', es_admin: false })));
  setToken('tok');
  renderWithProviders(<AuthProvider><RequireAdmin><div>secreto admin</div></RequireAdmin></AuthProvider>);
  expect(await screen.findByText('Requiere permisos de administrador.')).toBeInTheDocument();
});

it('RequireAdmin deja pasar a admin', async () => {
  server.use(http.get('*/auth/me', () => HttpResponse.json({ id: 1, nombre: 'a', es_admin: true })));
  setToken('tok');
  renderWithProviders(<AuthProvider><RequireAdmin><div>secreto admin</div></RequireAdmin></AuthProvider>);
  expect(await screen.findByText('secreto admin')).toBeInTheDocument();
});
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd frontend && npx vitest run src/auth/RequireAdmin.test.tsx`
Expected: FAIL — `RequireAdmin` no existe y `esAdmin` no está en el contexto.

- [ ] **Step 3: Extender `AuthContext.tsx`**

Modificar `frontend/src/auth/AuthContext.tsx`:
- Imports: agregar `import { useQuery, useQueryClient } from '@tanstack/react-query';` y asegurarse de que `apiFetch`, `ApiError`, `setToken`, `clearToken`, `getToken` ya se importan de `../api/client`.
- Agregar el tipo `Me` y extender la interfaz del estado:
  ```tsx
  interface Me { id: number; nombre: string; es_admin: boolean }

  interface AuthState {
    isAuthenticated: boolean;
    esAdmin: boolean;
    login: (usuario: string, clave: string) => Promise<void>;
    logout: () => void;
  }
  ```
- En `AuthProvider`, después del `useState` del token, agregar:
  ```tsx
    const qc = useQueryClient();
    const meQuery = useQuery({
      queryKey: ['me'],
      queryFn: () => apiFetch<Me>('/auth/me'),
      enabled: !!token,
    });
    const esAdmin = meQuery.data?.es_admin ?? false;
  ```
- En `logout`, agregar la limpieza de la query (después de limpiar el token):
  ```tsx
    qc.removeQueries({ queryKey: ['me'] });
  ```
- Incluir `esAdmin` en el `value` del provider: `value={{ isAuthenticated: !!token, esAdmin, login, logout }}`.

(El resto de `AuthContext` —`login`, `useAuth`, etc.— no cambia. `token` se llama así o `setTokenState`; respetá los nombres existentes.)

- [ ] **Step 4: Crear `RequireAdmin.tsx`**

```tsx
import { ReactNode } from 'react';
import { Alert } from '@mantine/core';
import { useAuth } from './AuthContext';

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { esAdmin } = useAuth();
  if (!esAdmin) return <Alert color="red">Requiere permisos de administrador.</Alert>;
  return <>{children}</>;
}
```

- [ ] **Step 5: Correr y verificar que pasa**

Run: `cd frontend && npx vitest run src/auth/RequireAdmin.test.tsx`
Expected: PASS (3 tests).

Luego correr la suite completa: `npx vitest run`. Si los tests existentes que autentican (p.ej. `LoginPage.test.tsx`, `RequireAuth.test.tsx`) emiten warnings de "unhandled request" por `GET /auth/me` (ahora que el provider lo dispara cuando hay token), agregar a CADA uno de esos archivos un handler por defecto en su `setupServer`/`server.use`:
```tsx
http.get('*/auth/me', () => HttpResponse.json({ id: 1, nombre: 'a', es_admin: false })),
```
Esto silencia el warning sin cambiar lo que esos tests verifican. (Si no aparece warning ni fallo, no tocarlos.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/auth/AuthContext.tsx frontend/src/auth/RequireAdmin.tsx frontend/src/auth/RequireAdmin.test.tsx
# incluir también los test files que hayas tenido que tocar para el handler de /auth/me
git commit -m "feat(frontend): esAdmin en AuthContext (/auth/me) + RequireAdmin"
```

---

### Task 2: Hooks de agent-tokens

**Files:**
- Modify: `frontend/src/api/hooks.ts`
- Test: `frontend/src/api/hooks.test.tsx`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `frontend/src/api/hooks.test.tsx` (reusa `server`/`wrapper`; extender el import de `./hooks` con `useAgentTokens`, `useCrearAgentToken`):
```tsx
it('useAgentTokens lista los tokens', async () => {
  server.use(http.get('*/api/agent-tokens', () =>
    HttpResponse.json([{ id: 1, label: 'PC-01', created_at: '2026-05-12T09:14:00Z' }])));
  const { result } = renderHook(() => useAgentTokens(), { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.[0].label).toBe('PC-01');
});

it('useCrearAgentToken devuelve el token en claro', async () => {
  server.use(http.post('*/api/agent-tokens', async ({ request }) => {
    const b = (await request.json()) as { label: string };
    return HttpResponse.json({ id: 2, label: b.label, token: 'sxk_secreto' }, { status: 201 });
  }));
  const { result } = renderHook(() => useCrearAgentToken(), { wrapper });
  const creado = await result.current.mutateAsync('Agente nuevo');
  expect(creado?.token).toBe('sxk_secreto');
  expect(creado?.label).toBe('Agente nuevo');
});
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd frontend && npx vitest run src/api/hooks.test.tsx`
Expected: FAIL — hooks no existen.

- [ ] **Step 3: Implementar** (agregar a `frontend/src/api/hooks.ts`; reusa `useQuery`/`useMutation`/`useQueryClient`/`apiFetch`)

```ts
export interface AgentToken {
  id: number;
  label: string;
  created_at: string;
}
export interface AgentTokenCreado {
  id: number;
  label: string;
  token: string;
}

export function useAgentTokens() {
  return useQuery({
    queryKey: ['agent-tokens'],
    queryFn: async () => (await apiFetch<AgentToken[]>('/api/agent-tokens')) ?? [],
  });
}

export function useCrearAgentToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (label: string) =>
      apiFetch<AgentTokenCreado>('/api/agent-tokens', { method: 'POST', body: JSON.stringify({ label }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agent-tokens'] }),
  });
}

export function useRevocarAgentToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/api/agent-tokens/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agent-tokens'] }),
  });
}
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd frontend && npx vitest run src/api/hooks.test.tsx` (luego `npx vitest run` completo)
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/hooks.ts frontend/src/api/hooks.test.tsx
git commit -m "feat(frontend): hooks de agent-tokens (listar/crear/revocar)"
```

---

### Task 3: `AgentTokensPage`

**Files:**
- Create: `frontend/src/pages/AgentTokensPage.tsx`
- Test: `frontend/src/pages/AgentTokensPage.test.tsx`

- [ ] **Step 1: Implementar `AgentTokensPage.tsx`**

```tsx
import { useState } from 'react';
import { Table, Button, TextInput, Stack, Group, Title, Alert, Loader, Text, Code, Modal } from '@mantine/core';
import { useForm } from '@mantine/form';
import dayjs from 'dayjs';
import { useAgentTokens, useCrearAgentToken, useRevocarAgentToken, AgentToken } from '../api/hooks';
import { ApiError } from '../api/client';

export function AgentTokensPage() {
  const { data, isLoading, isError, refetch } = useAgentTokens();
  const crear = useCrearAgentToken();
  const revocar = useRevocarAgentToken();
  const [creadoToken, setCreadoToken] = useState<string | null>(null);
  const [aRevocar, setARevocar] = useState<AgentToken | null>(null);
  const [error, setError] = useState<string | null>(null);
  const form = useForm({ initialValues: { label: '' } });

  async function onSubmit(values: { label: string }) {
    setError(null);
    try {
      const res = await crear.mutateAsync(values.label);
      if (res) setCreadoToken(res.token);
      form.reset();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Error de conexión');
    }
  }

  async function confirmarRevocar() {
    if (!aRevocar) return;
    try {
      await revocar.mutateAsync(aRevocar.id);
    } finally {
      setARevocar(null);
    }
  }

  function copiar() {
    if (creadoToken) navigator.clipboard?.writeText(creadoToken);
  }

  if (isLoading) return <Loader />;
  if (isError)
    return <Alert color="red">Error al cargar <Button size="xs" onClick={() => refetch()}>Reintentar</Button></Alert>;
  const tokens = data ?? [];

  return (
    <Stack>
      <Title order={2}>Tokens de agente</Title>
      <form onSubmit={form.onSubmit(onSubmit)}>
        <Group align="flex-end">
          <TextInput label="Etiqueta" placeholder="Agente oficina PC-01" {...form.getInputProps('label')} />
          <Button type="submit" loading={crear.isPending}>Crear token</Button>
        </Group>
      </form>
      {error && <Alert color="red">{error}</Alert>}
      {creadoToken && (
        <Alert color="teal" title="Token creado — copialo ahora">
          <Text size="sm">No se vuelve a mostrar. Guardalo en la config del agente (token).</Text>
          <Group mt="xs">
            <Code>{creadoToken}</Code>
            <Button size="xs" onClick={copiar}>Copiar</Button>
            <Button size="xs" variant="default" onClick={() => setCreadoToken(null)}>Listo</Button>
          </Group>
        </Alert>
      )}
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Etiqueta</Table.Th>
            <Table.Th>Creado</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {tokens.map((t) => (
            <Table.Tr key={t.id}>
              <Table.Td>{t.label}</Table.Td>
              <Table.Td>{dayjs(t.created_at).format('YYYY-MM-DD HH:mm')}</Table.Td>
              <Table.Td>
                <Button variant="subtle" color="red" size="xs" onClick={() => setARevocar(t)}>Revocar</Button>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      <Modal opened={aRevocar !== null} onClose={() => setARevocar(null)} title="Revocar token">
        <Text>¿Revocar el token "{aRevocar?.label}"? El agente que lo use dejará de funcionar.</Text>
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={() => setARevocar(null)}>Cancelar</Button>
          <Button color="red" loading={revocar.isPending} onClick={confirmarRevocar}>Revocar</Button>
        </Group>
      </Modal>
    </Stack>
  );
}
```

- [ ] **Step 2: Escribir el test** (`frontend/src/pages/AgentTokensPage.test.tsx`)

```tsx
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/utils';
import { AgentTokensPage } from './AgentTokensPage';

const TOKEN = { id: 1, label: 'PC-01', created_at: '2026-05-12T09:14:00Z' };

const server = setupServer(
  http.get('*/api/agent-tokens', () => HttpResponse.json([TOKEN])),
);
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

it('lista los tokens', async () => {
  renderWithProviders(<AgentTokensPage />);
  expect(await screen.findByText('PC-01')).toBeInTheDocument();
});

it('crear muestra el token revelado una vez', async () => {
  server.use(http.post('*/api/agent-tokens', async ({ request }) => {
    const b = (await request.json()) as { label: string };
    return HttpResponse.json({ id: 2, label: b.label, token: 'sxk_secreto_123' }, { status: 201 });
  }));
  renderWithProviders(<AgentTokensPage />);
  await userEvent.type(screen.getByLabelText('Etiqueta'), 'Agente nuevo');
  await userEvent.click(screen.getByRole('button', { name: 'Crear token' }));
  expect(await screen.findByText('sxk_secreto_123')).toBeInTheDocument();
});

it('revoca un token con DELETE al id tras confirmar', async () => {
  let delId = '';
  server.use(http.delete('*/api/agent-tokens/:id', ({ params }) => {
    delId = String(params.id);
    return new HttpResponse(null, { status: 204 });
  }));
  renderWithProviders(<AgentTokensPage />);
  await userEvent.click(await screen.findByRole('button', { name: 'Revocar' }));
  const dialog = await screen.findByRole('dialog');
  await userEvent.click(within(dialog).getByRole('button', { name: 'Revocar' }));
  await waitFor(() => expect(delId).toBe('1'));
});
```

Notas (ajustar SOLO queries del test): `Code` de Mantine renderiza el token como texto, así que `findByText('sxk_secreto_123')` lo encuentra. Usar `within(dialog)` para desambiguar el botón "Revocar" del modal respecto al de la fila. `jsdom` puede no tener `navigator.clipboard`; el test no ejercita Copiar (usa `?.` así que no rompe). `renderWithProviders` ya provee QueryClient + Mantine env=test.

- [ ] **Step 3: Correr y verificar que pasan**

Run: `cd frontend && npx vitest run src/pages/AgentTokensPage.test.tsx` (luego `npx vitest run` completo)
Expected: PASS (3 tests).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AgentTokensPage.tsx frontend/src/pages/AgentTokensPage.test.tsx
git commit -m "feat(frontend): página de tokens de agente (crear/listar/revocar, revelado único)"
```

---

### Task 4: Navegación + gating de ruta

**Files:**
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AppShell.test.tsx`

- [ ] **Step 1: Escribir/actualizar tests de AppShell (TDD)**

En `frontend/src/components/AppShell.test.tsx`:
- Asegurarse de que el `setupServer` tenga un handler de `*/auth/me` (si no lo tiene, agregarlo; default `es_admin:false`), además del de `*/api/clientes`.
- Agregar dos tests (importar `setToken`/`clearToken` de `../api/client`; `afterEach` debe `clearToken()`):
```tsx
it('muestra el link de Tokens de agente a un admin', async () => {
  server.use(http.get('*/auth/me', () => HttpResponse.json({ id: 1, nombre: 'a', es_admin: true })));
  setToken('tok');
  renderWithProviders(
    <AuthProvider><SeleccionProvider><AppShell><div /></AppShell></SeleccionProvider></AuthProvider>
  );
  expect(await screen.findByRole('link', { name: 'Tokens de agente' })).toBeInTheDocument();
});

it('oculta el link de Tokens de agente a un no-admin', async () => {
  server.use(http.get('*/auth/me', () => HttpResponse.json({ id: 1, nombre: 'a', es_admin: false })));
  setToken('tok');
  renderWithProviders(
    <AuthProvider><SeleccionProvider><AppShell><div /></AppShell></SeleccionProvider></AuthProvider>
  );
  // esperar a que cargue algo determinista y verificar ausencia
  await screen.findByText('Clientes');
  expect(screen.queryByRole('link', { name: 'Tokens de agente' })).not.toBeInTheDocument();
});
```
(El AppShell ya se renderiza envuelto en `AuthProvider`+`SeleccionProvider` en este test; mantené ese andamiaje. Importar `AuthProvider` de `../auth/AuthContext` si no está importado.)

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd frontend && npx vitest run src/components/AppShell.test.tsx`
Expected: FAIL — el link de admin no existe aún.

- [ ] **Step 3: Implementar**

En `frontend/src/components/AppShell.tsx`:
- Importar `useAuth`: `import { useAuth } from '../auth/AuthContext';`
- Dentro del componente, obtener `esAdmin` y construir la lista de links con el item admin condicional:
  ```tsx
  const { esAdmin } = useAuth();
  const links = esAdmin
    ? [...LINKS, { to: '/agent-tokens', label: 'Tokens de agente' }]
    : LINKS;
  ```
  Reemplazar el `LINKS.map(...)` del navbar por `links.map(...)` (mismo render de `NavItem`).

En `frontend/src/App.tsx`:
- Importar la página y el guard: `import { AgentTokensPage } from './pages/AgentTokensPage';` y `import { RequireAdmin } from './auth/RequireAdmin';`
- Agregar la ruta dentro del `<Routes>` anidado, antes del catch-all `*`:
  ```tsx
                <Route path="/agent-tokens" element={<RequireAdmin><AgentTokensPage /></RequireAdmin>} />
  ```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd frontend && npx vitest run src/components/AppShell.test.tsx` (luego `npx vitest run` completo, `npx tsc -b`, `npm run build`)
Expected: PASS; tipos limpios; build OK.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AppShell.tsx frontend/src/components/AppShell.test.tsx frontend/src/App.tsx
git commit -m "feat(frontend): link condicional + ruta admin de Tokens de agente"
```

---

### Task 5: Verificación final

- [ ] **Step 1: Suite frontend + tipos + build**

Run: `cd frontend && npx vitest run && npx tsc -b && npm run build`
Expected: todos los tests verdes, `tsc -b` sin errores, build exitoso.

- [ ] **Step 2: Suite backend (sanity, no cambió)**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest -q`
Expected: verde (este slice no toca backend; es un sanity check). Si Postgres está caído, se puede omitir y anotarlo.

- [ ] **Step 3: Commit final si hubo ajustes**

```bash
git add -A
git commit -m "chore: ajustes finales tokens de agente"
```

---

## Self-Review (cobertura del spec)

- `AuthContext` gana `esAdmin` vía query `['me']`; `logout` limpia `['me']` → Task 1. ✔
- `RequireAdmin` (Alert "Requiere permisos de administrador.") → Task 1. ✔
- Hooks `useAgentTokens/useCrearAgentToken/useRevocarAgentToken` + tipos → Task 2. ✔
- `AgentTokensPage` (crear con revelado único + Copiar + Listo; lista con fecha dayjs; revocar con confirmación; 422 inline) → Task 3. ✔
- `AppShell` link solo si `esAdmin`; ruta `/agent-tokens` envuelta en `RequireAdmin` → Task 4. ✔
- Pruebas: esAdmin desde /auth/me, RequireAdmin, link con/sin admin, hooks, página → Tasks 1-4. ✔
- Sin cambios de backend (ya completo); sin dinero. ✔

Riesgos conocidos (notas en el plan): tests existentes que autentican pueden necesitar un handler `*/auth/me` para silenciar warnings (Task 1, Step 5); `navigator.clipboard` puede no existir en jsdom (se usa `?.`, no rompe); desambiguar el botón "Revocar" del modal con `within(dialog)`.
