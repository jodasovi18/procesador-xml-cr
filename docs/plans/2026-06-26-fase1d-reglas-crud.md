# Reglas CRUD (diferido 1D) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir gestionar (crear/listar/editar/eliminar) las reglas de clasificación por cliente desde el frontend, agregando los endpoints `PUT`/`DELETE` que faltan en el backend.

**Architecture:** Backend FastAPI: dos endpoints nuevos en `routers/reglas.py` que reusan la validación de `ReglaCreate`. Frontend: hooks TanStack nuevos en `api/hooks.ts`, una página `ReglasPage` (tabla + modal crear/editar + modal de confirmación de borrado), y una entrada de navegación en `AppShell`/`App.tsx`. La página usa el `clienteId` del `SeleccionContext` global.

**Tech Stack:** Backend: FastAPI, SQLAlchemy, pytest. Frontend: React, Mantine 7, TanStack Query, Vitest + RTL + MSW.

---

## Convenciones (leer antes de empezar)

- Spec: `docs/plans/2026-06-26-fase1d-reglas-crud-design.md`.
- Worktree: `C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\.claude\worktrees\reverent-lederberg-08f91d`. Rama `claude/fase1d-reglas-crud`.
- **Backend tests (worktree no tiene venv propio):** usar el venv del repo principal apuntando al código del worktree. Desde el worktree, en Bash:
  ```bash
  cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest -q
  ```
  Requiere PostgreSQL local en :5433 (las pruebas crean/borran `sistemaxml_test`). Si el comando de arriba no resuelve, el venv está en `C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\backend\.venv\Scripts\python.exe` y `PYTHONPATH` debe ser el `backend/` del worktree.
- **Frontend (desde `frontend/`):** `npx vitest run`, `npx tsc -b`, `npm run build`. Vitest tiene `globals: true` (no importar describe/it/expect). MSW: handlers con patrón de origen wildcard `*/...`. Tests de componente usan `renderWithProviders` (Mantine env=test + Notifications + QueryClient + MemoryRouter).
- Commits: uno por tarea, en español, prefijo `feat(backend)`/`feat(frontend)`/`test(...)`.
- Dinero: no aplica en esta feature.

## Estructura de archivos

```
backend/app/routers/reglas.py        # + PUT /{id}, DELETE /{id}
backend/tests/test_reglas_endpoint.py # + tests PUT/DELETE
frontend/src/api/hooks.ts            # + Regla, ReglaCreate, useReglas/useCrearRegla/useEditarRegla/useEliminarRegla
frontend/src/api/hooks.test.tsx      # + tests de los hooks de reglas
frontend/src/pages/ReglasPage.tsx    # nueva página
frontend/src/pages/ReglasPage.test.tsx
frontend/src/components/AppShell.tsx # + link "Reglas"
frontend/src/components/AppShell.test.tsx # asserts 5 links
frontend/src/App.tsx                 # + ruta /reglas
```

---

### Task 1: Backend — `PUT /api/reglas/{id}` (editar)

**Files:**
- Modify: `backend/app/routers/reglas.py`
- Test: `backend/tests/test_reglas_endpoint.py`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `backend/tests/test_reglas_endpoint.py` (reusa los helpers `_token`/`_cliente`/`_auth` ya definidos arriba en ese archivo):

```python
def test_editar_regla(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    r = client.post("/api/reglas", json={"cliente_id": cli.id, "cedula": "3101030042", "clasificacion": "Compras"}, headers=_auth(token))
    rid = r.json()["id"]
    upd = {"cliente_id": cli.id, "cabys": "2310100000000", "clasificacion": "No Deducibles", "sub_clasificacion": "Combustibles"}
    r2 = client.put(f"/api/reglas/{rid}", json=upd, headers=_auth(token))
    assert r2.status_code == 200
    body = r2.json()
    assert body["id"] == rid
    assert body["clasificacion"] == "No Deducibles"
    assert body["cabys"] == "2310100000000"
    assert body["sub_clasificacion"] == "Combustibles"
    assert body["cedula"] is None  # se reemplazó por cabys

def test_editar_regla_inexistente_404(client, db_session):
    token = _token(client, db_session); _cliente(db_session)
    upd = {"cliente_id": 1, "cedula": "3101030042", "clasificacion": "Compras"}
    assert client.put("/api/reglas/999999", json=upd, headers=_auth(token)).status_code == 404

def test_editar_regla_clasificacion_invalida_422(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    rid = client.post("/api/reglas", json={"cliente_id": cli.id, "cedula": "3101030042", "clasificacion": "Compras"}, headers=_auth(token)).json()["id"]
    upd = {"cliente_id": cli.id, "cedula": "3101030042", "clasificacion": "Inexistente"}
    assert client.put(f"/api/reglas/{rid}", json=upd, headers=_auth(token)).status_code == 422

def test_editar_regla_sin_ced_ni_cabys_422(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    rid = client.post("/api/reglas", json={"cliente_id": cli.id, "cedula": "3101030042", "clasificacion": "Compras"}, headers=_auth(token)).json()["id"]
    upd = {"cliente_id": cli.id, "clasificacion": "Compras"}
    assert client.put(f"/api/reglas/{rid}", json=upd, headers=_auth(token)).status_code == 422

def test_editar_regla_sin_token_401(client):
    assert client.put("/api/reglas/1", json={"cliente_id": 1, "cedula": "1", "clasificacion": "Compras"}).status_code == 401
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_reglas_endpoint.py -q`
Expected: FAIL — los `PUT` devuelven 405 (método no permitido) en vez de 200/404/422.

- [ ] **Step 3: Implementar el endpoint**

En `backend/app/routers/reglas.py` agregar (después del `listar_reglas` existente):

```python
@router.put("/{regla_id}", response_model=ReglaOut)
def editar_regla(regla_id: int, data: ReglaCreate, db: Session = Depends(get_db),
                 _: Usuario = Depends(get_current_user)):
    regla = db.get(ReglaClasificacion, regla_id)
    if regla is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no existe")
    # cliente_id no se reasigna: la regla queda en su cliente original.
    regla.cedula = data.cedula
    regla.cabys = data.cabys
    regla.rol = data.rol
    regla.clasificacion = data.clasificacion
    regla.sub_clasificacion = data.sub_clasificacion
    db.commit()
    db.refresh(regla)
    return regla
```

(La validación de dominios y "al menos cédula o cabys" la hace `ReglaCreate` antes de entrar al cuerpo, así que un body inválido da 422 automáticamente.)

- [ ] **Step 4: Correr y verificar que pasan**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_reglas_endpoint.py -q`
Expected: PASS (los 5 tests nuevos + los existentes verdes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/reglas.py backend/tests/test_reglas_endpoint.py
git commit -m "feat(backend): PUT /api/reglas/{id} para editar reglas (404/422)"
```

---

### Task 2: Backend — `DELETE /api/reglas/{id}` (eliminar)

**Files:**
- Modify: `backend/app/routers/reglas.py`
- Test: `backend/tests/test_reglas_endpoint.py`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `backend/tests/test_reglas_endpoint.py`:

```python
def test_eliminar_regla(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    rid = client.post("/api/reglas", json={"cliente_id": cli.id, "cedula": "3101030042", "clasificacion": "Compras"}, headers=_auth(token)).json()["id"]
    assert client.delete(f"/api/reglas/{rid}", headers=_auth(token)).status_code == 204
    lst = client.get(f"/api/reglas?cliente_id={cli.id}", headers=_auth(token)).json()
    assert all(r["id"] != rid for r in lst)

def test_eliminar_regla_inexistente_404(client, db_session):
    token = _token(client, db_session); _cliente(db_session)
    assert client.delete("/api/reglas/999999", headers=_auth(token)).status_code == 404

def test_eliminar_regla_sin_token_401(client):
    assert client.delete("/api/reglas/1").status_code == 401
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_reglas_endpoint.py -q`
Expected: FAIL — `DELETE` da 405.

- [ ] **Step 3: Implementar el endpoint**

En `backend/app/routers/reglas.py` agregar:

```python
@router.delete("/{regla_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_regla(regla_id: int, db: Session = Depends(get_db),
                   _: Usuario = Depends(get_current_user)):
    regla = db.get(ReglaClasificacion, regla_id)
    if regla is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no existe")
    db.delete(regla)
    db.commit()
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_reglas_endpoint.py -q`
Expected: PASS (tests nuevos + existentes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/reglas.py backend/tests/test_reglas_endpoint.py
git commit -m "feat(backend): DELETE /api/reglas/{id} (204/404)"
```

---

### Task 3: Frontend — hooks de reglas

**Files:**
- Modify: `frontend/src/api/hooks.ts`
- Test: `frontend/src/api/hooks.test.tsx`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `frontend/src/api/hooks.test.tsx` (mismo archivo; reusa el `wrapper` y el `server` ya definidos allí — si están como constantes locales del archivo, reutilizarlas; si no, replicar el patrón `setupServer()` + beforeAll/afterAll/afterEach + `wrapper` con QueryClient). Imports a agregar: `useReglas`, `useEditarRegla` desde `./hooks`.

```tsx
it('useReglas pasa cliente_id y devuelve la lista', async () => {
  server.use(http.get('*/api/reglas', ({ request }) => {
    const cid = new URL(request.url).searchParams.get('cliente_id');
    return HttpResponse.json([{ id: 1, cliente_id: Number(cid), cedula: '310', cabys: null, rol: null, clasificacion: 'Compras', sub_clasificacion: null }]);
  }));
  const { result } = renderHook(() => useReglas(7), { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.[0].clasificacion).toBe('Compras');
  expect(result.current.data?.[0].cliente_id).toBe(7);
});

it('useReglas no dispara sin cliente', () => {
  const { result } = renderHook(() => useReglas(null), { wrapper });
  expect(result.current.fetchStatus).toBe('idle');
});

it('useEditarRegla hace PUT al id correcto', async () => {
  let metodo = ''; let ruta = '';
  server.use(http.put('*/api/reglas/:id', ({ request, params }) => {
    metodo = request.method; ruta = String(params.id);
    return HttpResponse.json({ id: Number(params.id), cliente_id: 7, cedula: null, cabys: '231', rol: null, clasificacion: 'No Deducibles', sub_clasificacion: null });
  }));
  const { result } = renderHook(() => useEditarRegla(), { wrapper });
  await result.current.mutateAsync({ id: 5, data: { cliente_id: 7, cabys: '231', clasificacion: 'No Deducibles' } });
  expect(metodo).toBe('PUT');
  expect(ruta).toBe('5');
});
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd frontend && npx vitest run src/api/hooks.test.tsx`
Expected: FAIL — `useReglas`/`useEditarRegla` no existen.

- [ ] **Step 3: Implementar los hooks**

En `frontend/src/api/hooks.ts` agregar (el helper `qs` ya existe en el archivo; reutilizarlo):

```ts
export interface Regla {
  id: number;
  cliente_id: number;
  cedula: string | null;
  cabys: string | null;
  rol: string | null;
  clasificacion: string;
  sub_clasificacion: string | null;
}
export interface ReglaCreate {
  cliente_id: number;
  cedula?: string | null;
  cabys?: string | null;
  rol?: string | null;
  clasificacion: string;
  sub_clasificacion?: string | null;
}

export function useReglas(clienteId: number | null) {
  return useQuery({
    queryKey: ['reglas', clienteId],
    enabled: clienteId != null,
    queryFn: async () =>
      (await apiFetch<Regla[]>('/api/reglas' + qs({ cliente_id: clienteId! }))) ?? [],
  });
}

export function useCrearRegla() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ReglaCreate) =>
      apiFetch<Regla>('/api/reglas', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['reglas', vars.cliente_id] }),
  });
}

export function useEditarRegla() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ReglaCreate }) =>
      apiFetch<Regla>(`/api/reglas/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['reglas', vars.data.cliente_id] }),
  });
}

export function useEliminarRegla() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: number; clienteId: number }) =>
      apiFetch<void>(`/api/reglas/${id}`, { method: 'DELETE' }),
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['reglas', vars.clienteId] }),
  });
}
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `cd frontend && npx vitest run src/api/hooks.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/hooks.ts frontend/src/api/hooks.test.tsx
git commit -m "feat(frontend): hooks de reglas (list/crear/editar/eliminar)"
```

---

### Task 4: Frontend — `ReglasPage`

**Files:**
- Create: `frontend/src/pages/ReglasPage.tsx`
- Test: `frontend/src/pages/ReglasPage.test.tsx`

- [ ] **Step 1: Implementar `ReglasPage.tsx`**

```tsx
import { useState } from 'react';
import { Table, Button, Modal, TextInput, Select, Stack, Group, Title, Alert, Loader, Text } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useSeleccion } from '../context/SeleccionContext';
import { useReglas, useCrearRegla, useEditarRegla, useEliminarRegla, Regla, ReglaCreate } from '../api/hooks';
import { ApiError } from '../api/client';

const CLASIFICACIONES = ['Compras', 'Gastos', 'Bienes de Capital', 'No Deducibles', 'Sin Clasificar'];
const ROLES = [
  { value: '', label: '— (cualquiera)' },
  { value: 'compra', label: 'compra' },
  { value: 'venta', label: 'venta' },
];

interface FormValues {
  cedula: string;
  cabys: string;
  rol: string;
  clasificacion: string;
  sub_clasificacion: string;
}

const VACIO: FormValues = { cedula: '', cabys: '', rol: '', clasificacion: 'Compras', sub_clasificacion: '' };

export function ReglasPage() {
  const { clienteId } = useSeleccion();
  const { data: reglas, isLoading, isError, refetch } = useReglas(clienteId);
  const crear = useCrearRegla();
  const editar = useEditarRegla();
  const eliminar = useEliminarRegla();
  // undefined = modal cerrado; null = creando; Regla = editando
  const [editando, setEditando] = useState<Regla | null | undefined>(undefined);
  const [aEliminar, setAEliminar] = useState<Regla | null>(null);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<FormValues>({
    initialValues: VACIO,
    validate: {
      cedula: (v, values) =>
        !v.trim() && !values.cabys.trim() ? 'Indicá al menos cédula o CABYS' : null,
    },
  });

  function abrirNuevo() {
    setError(null);
    form.setValues(VACIO);
    setEditando(null);
  }
  function abrirEditar(r: Regla) {
    setError(null);
    form.setValues({
      cedula: r.cedula ?? '',
      cabys: r.cabys ?? '',
      rol: r.rol ?? '',
      clasificacion: r.clasificacion,
      sub_clasificacion: r.sub_clasificacion ?? '',
    });
    setEditando(r);
  }
  function cerrar() {
    setEditando(undefined);
    setError(null);
    form.reset();
  }

  async function onSubmit(values: FormValues) {
    if (clienteId == null) return;
    setError(null);
    const payload: ReglaCreate = {
      cliente_id: clienteId,
      cedula: values.cedula.trim() || null,
      cabys: values.cabys.trim() || null,
      rol: values.rol || null,
      clasificacion: values.clasificacion,
      sub_clasificacion: values.sub_clasificacion.trim() || null,
    };
    try {
      if (editando) await editar.mutateAsync({ id: editando.id, data: payload });
      else await crear.mutateAsync(payload);
      cerrar();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Error de conexión');
    }
  }

  async function confirmarEliminar() {
    if (!aEliminar || clienteId == null) return;
    try {
      await eliminar.mutateAsync({ id: aEliminar.id, clienteId });
    } finally {
      setAEliminar(null);
    }
  }

  if (clienteId == null) return <Alert color="yellow">Elegí un cliente en la barra superior.</Alert>;
  if (isLoading) return <Loader />;
  if (isError)
    return (
      <Alert color="red">
        Error al cargar las reglas <Button size="xs" onClick={() => refetch()}>Reintentar</Button>
      </Alert>
    );

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Reglas de clasificación</Title>
        <Button onClick={abrirNuevo}>Nueva regla</Button>
      </Group>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Cédula</Table.Th>
            <Table.Th>CABYS</Table.Th>
            <Table.Th>Rol</Table.Th>
            <Table.Th>Clasificación</Table.Th>
            <Table.Th>Sub-clasif.</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {(reglas ?? []).map((r) => (
            <Table.Tr key={r.id}>
              <Table.Td>{r.cedula ?? '—'}</Table.Td>
              <Table.Td>{r.cabys ?? '—'}</Table.Td>
              <Table.Td>{r.rol ?? '—'}</Table.Td>
              <Table.Td>{r.clasificacion}</Table.Td>
              <Table.Td>{r.sub_clasificacion ?? '—'}</Table.Td>
              <Table.Td>
                <Group gap="xs">
                  <Button variant="subtle" size="xs" onClick={() => abrirEditar(r)}>Editar</Button>
                  <Button variant="subtle" color="red" size="xs" onClick={() => setAEliminar(r)}>Eliminar</Button>
                </Group>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      <Modal opened={editando !== undefined} onClose={cerrar} title={editando ? 'Editar regla' : 'Nueva regla'}>
        <form onSubmit={form.onSubmit(onSubmit)}>
          <Stack>
            {error && <Alert color="red">{error}</Alert>}
            <TextInput label="Cédula" {...form.getInputProps('cedula')} />
            <TextInput label="CABYS" {...form.getInputProps('cabys')} />
            <Select label="Rol" data={ROLES} {...form.getInputProps('rol')} />
            <Select label="Clasificación" data={CLASIFICACIONES} {...form.getInputProps('clasificacion')} />
            <TextInput
              label="Sub-clasificación"
              description='"Combustibles" fuerza tratamiento No Sujeto'
              {...form.getInputProps('sub_clasificacion')}
            />
            <Button type="submit" loading={crear.isPending || editar.isPending}>Guardar</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={aEliminar !== null} onClose={() => setAEliminar(null)} title="Eliminar regla">
        <Text>¿Eliminar esta regla de clasificación?</Text>
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={() => setAEliminar(null)}>Cancelar</Button>
          <Button color="red" loading={eliminar.isPending} onClick={confirmarEliminar}>Eliminar</Button>
        </Group>
      </Modal>
    </Stack>
  );
}
```

- [ ] **Step 2: Escribir el test**

`frontend/src/pages/ReglasPage.test.tsx`:

```tsx
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/utils';
import { SeleccionProvider } from '../context/SeleccionContext';
import { ReglasPage } from './ReglasPage';

const REGLA = { id: 5, cliente_id: 1, cedula: '3101030042', cabys: null, rol: 'compra', clasificacion: 'Compras', sub_clasificacion: null };

const server = setupServer(
  http.get('*/api/reglas', () => HttpResponse.json([REGLA])),
);
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

function conCliente(ui: React.ReactNode) {
  return <SeleccionProvider initialClienteId={1}>{ui}</SeleccionProvider>;
}

it('pide elegir cliente cuando no hay selección', () => {
  renderWithProviders(<SeleccionProvider><ReglasPage /></SeleccionProvider>);
  expect(screen.getByText('Elegí un cliente en la barra superior.')).toBeInTheDocument();
});

it('lista las reglas del cliente', async () => {
  renderWithProviders(conCliente(<ReglasPage />));
  expect(await screen.findByText('3101030042')).toBeInTheDocument();
  expect(screen.getByText('Compras')).toBeInTheDocument();
});

it('edita una regla con PUT al id correcto', async () => {
  let putId = '';
  server.use(http.put('*/api/reglas/:id', ({ params }) => {
    putId = String(params.id);
    return HttpResponse.json({ ...REGLA, clasificacion: 'No Deducibles' });
  }));
  renderWithProviders(conCliente(<ReglasPage />));
  await userEvent.click(await screen.findByRole('button', { name: 'Editar' }));
  // El modal abre precargado; cambiar clasificación y guardar.
  await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));
  await waitFor(() => expect(putId).toBe('5'));
});

it('elimina una regla con DELETE al id correcto tras confirmar', async () => {
  let delId = '';
  server.use(http.delete('*/api/reglas/:id', ({ params }) => {
    delId = String(params.id);
    return new HttpResponse(null, { status: 204 });
  }));
  renderWithProviders(conCliente(<ReglasPage />));
  await userEvent.click(await screen.findByRole('button', { name: 'Eliminar' }));
  // Modal de confirmación: hay un segundo botón "Eliminar" (color rojo) dentro del diálogo.
  const dialog = await screen.findByRole('dialog');
  await userEvent.click(within(dialog).getByRole('button', { name: 'Eliminar' }));
  await waitFor(() => expect(delId).toBe('5'));
});

it('muestra 422 inline en el modal', async () => {
  server.use(http.post('*/api/reglas', () =>
    HttpResponse.json({ detail: 'clasificacion inválida' }, { status: 422 })));
  renderWithProviders(conCliente(<ReglasPage />));
  await userEvent.click(await screen.findByRole('button', { name: 'Nueva regla' }));
  // completar cédula para pasar la validación cliente, luego forzar 422 del server
  const dialog = await screen.findByRole('dialog');
  await userEvent.type(within(dialog).getByLabelText('Cédula'), '3101');
  await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }));
  expect(await screen.findByText('clasificacion inválida')).toBeInTheDocument();
});
```

Notas para el implementador:
- Mantine `Modal` renderiza con `role="dialog"`; usar `within(dialog)` para desambiguar el botón "Eliminar"/"Guardar" del modal respecto a los de la tabla.
- Si `getByLabelText('Cédula')` choca con el encabezado de columna "Cédula", restringí con `within(dialog)` (ya hecho arriba) o agregá un `id` al `TextInput` y buscá por id (patrón usado en `ClientesPage.test.tsx`). Ajustá solo la query del test, no el componente, salvo que necesites el `id`.
- Si en el test de editar el `Select` de Clasificación necesita cambiar de valor y eso complica el query, basta con guardar el modal precargado: la aserción clave es que el PUT salió al id 5.

- [ ] **Step 3: Correr y verificar que pasan**

Run: `cd frontend && npx vitest run src/pages/ReglasPage.test.tsx`
Expected: PASS (5 tests). Iterar las queries del test según las notas si algo no matchea, sin cambiar la lógica del componente.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ReglasPage.tsx frontend/src/pages/ReglasPage.test.tsx
git commit -m "feat(frontend): página de reglas (tabla + crear/editar/eliminar, 422 inline)"
```

---

### Task 5: Frontend — navegación (sidebar + ruta)

**Files:**
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AppShell.test.tsx`

- [ ] **Step 1: Actualizar el test de AppShell (TDD)**

En `frontend/src/components/AppShell.test.tsx`, extender la aserción de enlaces para incluir 'Reglas'. Junto a las aserciones existentes (Clientes, Subida XML, Resumen, D-150) agregar:

```tsx
  expect(screen.getByText('Reglas')).toBeInTheDocument();
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd frontend && npx vitest run src/components/AppShell.test.tsx`
Expected: FAIL — no existe el enlace 'Reglas'.

- [ ] **Step 3: Agregar el enlace y la ruta**

En `frontend/src/components/AppShell.tsx`, agregar a la constante `LINKS` la entrada de Reglas (al final):

```tsx
const LINKS = [
  { to: '/clientes', label: 'Clientes' },
  { to: '/subida', label: 'Subida XML' },
  { to: '/resumen', label: 'Resumen' },
  { to: '/d150', label: 'D-150' },
  { to: '/reglas', label: 'Reglas' },
];
```

En `frontend/src/App.tsx`, importar la página y agregar la ruta dentro del `<Routes>` anidado (junto a las otras páginas, antes del catch-all `*`):

```tsx
import { ReglasPage } from './pages/ReglasPage';
// ...
                <Route path="/reglas" element={<ReglasPage />} />
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd frontend && npx vitest run src/components/AppShell.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AppShell.tsx frontend/src/components/AppShell.test.tsx frontend/src/App.tsx
git commit -m "feat(frontend): enlace y ruta de Reglas en el AppShell"
```

---

### Task 6: Verificación final

- [ ] **Step 1: Suite de backend**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest -q`
Expected: toda la suite del backend verde (incluye los nuevos tests de reglas).

- [ ] **Step 2: Suite de frontend + tipos + build**

Run: `cd frontend && npx vitest run && npx tsc -b && npm run build`
Expected: todos los tests verdes, `tsc -b` sin errores, build exitoso.

- [ ] **Step 3: Commit final si hubo ajustes**

```bash
git add -A
git commit -m "chore: ajustes finales reglas CRUD"
```

---

## Self-Review (cobertura del spec)

- Backend `PUT /api/reglas/{id}` (editar, no reasigna cliente, 404, 422) → Task 1. ✔
- Backend `DELETE /api/reglas/{id}` (204, 404) → Task 2. ✔
- Hooks `useReglas/useCrearRegla/useEditarRegla/useEliminarRegla` + tipos → Task 3. ✔
- `ReglasPage` (tabla, modal crear/editar precargado, modal de confirmación de borrado, guard sin cliente, 422 inline) → Task 4. ✔
- Sidebar "Reglas" + ruta `/reglas` → Task 5. ✔
- Pruebas backend (PUT/DELETE ok/404/422/401) → Tasks 1-2. ✔
- Pruebas frontend (listar/crear/editar/eliminar/guard/422) → Tasks 3-4. ✔
- Validación "al menos cédula o CABYS" → cliente (form.validate) + servidor (422), Tasks 4 y 1. ✔
- Sin aritmética de dinero (no aplica). ✔

Riesgos conocidos (marcados como notas en Task 4): desambiguación de queries de RTL entre los botones de la tabla y los de los modales (resuelto con `within(dialog)`), y posible choque de `getByLabelText('Cédula')` con el encabezado de columna (resuelto restringiendo al diálogo).
