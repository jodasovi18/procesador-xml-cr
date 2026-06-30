# Entradas manuales CRUD (diferido 1D) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Página para gestionar (listar/crear/editar/eliminar) las entradas manuales por cliente·período·rol, con IVA y totales calculados en el backend, agregando el `PUT` que falta.

**Architecture:** Backend: `EntradaManualOut` gana un `iva` calculado (espeja `d150.py`), el `GET` devuelve un objeto con totales en Decimal, y un nuevo `PUT`. Frontend: hooks TanStack (con `periodoApi`), `EntradasManualesPage` (tabla + footer de totales + modal crear/editar + confirmación de borrado) y navegación.

**Tech Stack:** Backend FastAPI/SQLAlchemy/pytest. Frontend React/Mantine 7/TanStack Query/Vitest+RTL+MSW.

---

## Convenciones (leer antes de empezar)

- Spec: `docs/plans/2026-06-27-fase1d-entradas-manuales-design.md`.
- Worktree: `C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\.claude\worktrees\reverent-lederberg-08f91d`. Rama `claude/fase1d-entradas-manuales` (desde main).
- **Backend tests:** `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest -q`. Requiere PostgreSQL :5433. Si está caído, BLOCKED.
- **Frontend** (desde `frontend/`): `npx vitest run <file>`, `npx tsc -b`, `npm run build`. Vitest globals on. MSW `*/...` wildcard. `renderWithProviders` (env=test). `SeleccionProvider` acepta initialClienteId/initialPeriodo/initialRol.
- **Período:** el front maneja "YYYY-MM", el backend "YYYYMM". Hay un helper `periodoApi` en `frontend/src/api/hooks.ts` (hoy privado) — esta feature lo **exporta** y lo usa tanto en la query como en el body de crear/editar.
- Dinero como string del backend + `formatColones`; nunca aritmética float en el front (por eso IVA y totales vienen del backend).
- Commits: uno por tarea, español.

## Estructura de archivos

```
backend/app/schemas/entrada_manual.py     # + iva computed, helper iva_entrada, EntradaManualListOut
backend/app/routers/entradas_manuales.py  # GET → objeto con totales; + PUT
backend/tests/test_entradas_manuales.py    # adaptar GET + tests iva/totales/PUT
frontend/src/api/hooks.ts                  # exportar periodoApi; hooks de entradas + tipos
frontend/src/api/hooks.test.tsx            # test del hook
frontend/src/pages/EntradasManualesPage.tsx
frontend/src/pages/EntradasManualesPage.test.tsx
frontend/src/components/AppShell.tsx       # + link
frontend/src/components/AppShell.test.tsx  # asserts 7 links
frontend/src/App.tsx                       # + ruta
```

---

### Task 1: Backend — `iva` calculado + `GET` con totales

**Files:**
- Modify: `backend/app/schemas/entrada_manual.py`
- Modify: `backend/app/routers/entradas_manuales.py`
- Test: `backend/tests/test_entradas_manuales.py`

Contexto: `EntradaManualCreate` y `EntradaManualOut` están en el schema; `EntradaManualOut` usa `ConfigDict(from_attributes=True)` y serializa `monto`/`tarifa` como str con un `field_serializer`. El `GET` actual devuelve `list[EntradaManualOut]`.

- [ ] **Step 1: Adaptar los tests existentes del GET + escribir los nuevos**

En `backend/tests/test_entradas_manuales.py`:
1. En `test_crear_listar_eliminar_entrada`, las dos aserciones del GET hoy hacen `len(lst.json()) == 1` y `len(lst2.json()) == 0`. Cambiarlas a la nueva forma de objeto:
   ```python
   lst = client.get(f"/api/entradas-manuales?cliente_id={cli.id}&periodo=202605", headers=_auth(token))
   assert lst.status_code == 200 and len(lst.json()["entradas"]) == 1
   ```
   y
   ```python
   lst2 = client.get(f"/api/entradas-manuales?cliente_id={cli.id}&periodo=202605", headers=_auth(token))
   assert len(lst2.json()["entradas"]) == 0
   ```
2. Agregar al final estos tests nuevos:
   ```python
   def test_get_incluye_iva_por_fila_y_totales(client, db_session):
       token = _token(client, db_session); cli = _cliente(db_session)
       # gravada: monto 2000, tarifa 13 → iva 260; no sujeta tarifa 0 → iva 0
       client.post("/api/entradas-manuales", json={"cliente_id": cli.id, "periodo": "202605", "rol": "venta",
                   "monto": "2000", "tarifa": "13"}, headers=_auth(token))
       client.post("/api/entradas-manuales", json={"cliente_id": cli.id, "periodo": "202605", "rol": "venta",
                   "monto": "500", "tarifa": "0", "no_sujeto": True}, headers=_auth(token))
       r = client.get(f"/api/entradas-manuales?cliente_id={cli.id}&periodo=202605&rol=venta", headers=_auth(token))
       assert r.status_code == 200
       body = r.json()
       assert len(body["entradas"]) == 2
       ivas = {Decimal(e["iva"]) for e in body["entradas"]}
       assert Decimal("260") in ivas and Decimal("0") in ivas
       assert Decimal(body["total_monto"]) == Decimal("2500")
       assert Decimal(body["total_iva"]) == Decimal("260")
   ```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_entradas_manuales.py -q`
Expected: FAIL — la respuesta del GET es una lista (no tiene `["entradas"]`) y no hay `iva`.

- [ ] **Step 3: Implementar el schema**

En `backend/app/schemas/entrada_manual.py`:
- Agregar el import de `computed_field` (de pydantic) y un helper + constante arriba:
  ```python
  Q5 = Decimal("0.00001")

  def iva_entrada(monto: Decimal, tarifa: Decimal) -> Decimal:
      return (monto * tarifa / Decimal("100")).quantize(Q5)
  ```
  (Asegurate de que `from decimal import Decimal` y `from pydantic import ... computed_field` estén importados.)
- En `EntradaManualOut`, agregar el campo calculado (después de los existentes, junto al `field_serializer`):
  ```python
      @computed_field
      def iva(self) -> str:
          return str(iva_entrada(self.monto, self.tarifa))
  ```
- Agregar el schema de respuesta del listado:
  ```python
  class EntradaManualListOut(BaseModel):
      entradas: list[EntradaManualOut]
      total_monto: str
      total_iva: str
  ```

- [ ] **Step 4: Implementar el router GET**

En `backend/app/routers/entradas_manuales.py`:
- Importar el nuevo schema y el helper: `from app.schemas.entrada_manual import EntradaManualCreate, EntradaManualOut, EntradaManualListOut, iva_entrada` y `from decimal import Decimal`.
- Cambiar el `listar` para devolver el objeto con totales:
  ```python
  @router.get("", response_model=EntradaManualListOut)
  def listar(cliente_id: int, periodo: str, rol: str | None = None,
             db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
      stmt = select(EntradaManual).where(
          EntradaManual.cliente_id == cliente_id, EntradaManual.periodo == periodo)
      if rol is not None:
          stmt = stmt.where(EntradaManual.rol == rol)
      entradas = list(db.scalars(stmt.order_by(EntradaManual.id)))
      total_monto = sum((e.monto for e in entradas), Decimal("0"))
      total_iva = sum((iva_entrada(e.monto, e.tarifa) for e in entradas), Decimal("0"))
      return EntradaManualListOut(entradas=entradas, total_monto=str(total_monto), total_iva=str(total_iva))
  ```
  (Pasar instancias ORM en `entradas=` funciona porque `EntradaManualOut` tiene `from_attributes=True`.)

- [ ] **Step 5: Correr y verificar que pasa**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_entradas_manuales.py -q`
Expected: PASS (los adaptados + el nuevo). Si `total_monto`/`iva` salen con formato Decimal distinto (p.ej. `"2500.00000"`), las aserciones usan `Decimal(...)` así que comparan por valor — OK.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/entrada_manual.py backend/app/routers/entradas_manuales.py backend/tests/test_entradas_manuales.py
git commit -m "feat(backend): entradas manuales con iva calculado y GET con totales"
```

---

### Task 2: Backend — `PUT /api/entradas-manuales/{id}`

**Files:**
- Modify: `backend/app/routers/entradas_manuales.py`
- Test: `backend/tests/test_entradas_manuales.py`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `backend/tests/test_entradas_manuales.py`:
```python
def test_editar_entrada(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    eid = client.post("/api/entradas-manuales", json={"cliente_id": cli.id, "periodo": "202605", "rol": "venta",
                      "descripcion": "Subasta", "monto": "2000", "tarifa": "13"}, headers=_auth(token)).json()["id"]
    upd = {"cliente_id": cli.id, "periodo": "202605", "rol": "venta", "descripcion": "Subasta corregida",
           "monto": "3000", "tarifa": "1", "no_sujeto": False, "deducible": True}
    r = client.put(f"/api/entradas-manuales/{eid}", json=upd, headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == eid
    assert body["descripcion"] == "Subasta corregida"
    assert Decimal(body["monto"]) == Decimal("3000")
    assert Decimal(body["tarifa"]) == Decimal("1")
    assert Decimal(body["iva"]) == Decimal("30")  # 3000 * 1 / 100

def test_editar_entrada_inexistente_404(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    upd = {"cliente_id": cli.id, "periodo": "202605", "rol": "venta", "monto": "1", "tarifa": "13"}
    assert client.put("/api/entradas-manuales/999999", json=upd, headers=_auth(token)).status_code == 404

def test_editar_entrada_monto_negativo_422(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    eid = client.post("/api/entradas-manuales", json={"cliente_id": cli.id, "periodo": "202605", "rol": "venta",
                      "monto": "2000", "tarifa": "13"}, headers=_auth(token)).json()["id"]
    upd = {"cliente_id": cli.id, "periodo": "202605", "rol": "venta", "monto": "-5", "tarifa": "13"}
    assert client.put(f"/api/entradas-manuales/{eid}", json=upd, headers=_auth(token)).status_code == 422

def test_editar_entrada_sin_token_401(client):
    assert client.put("/api/entradas-manuales/1", json={"cliente_id": 1, "periodo": "202605", "rol": "venta", "monto": "1", "tarifa": "13"}).status_code == 401
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_entradas_manuales.py -q`
Expected: FAIL — `PUT` da 405.

- [ ] **Step 3: Implementar el endpoint**

En `backend/app/routers/entradas_manuales.py` agregar:
```python
@router.put("/{entrada_id}", response_model=EntradaManualOut)
def editar(entrada_id: int, data: EntradaManualCreate, db: Session = Depends(get_db),
           _: Usuario = Depends(get_current_user)):
    e = db.get(EntradaManual, entrada_id)
    if e is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no existe")
    # cliente_id no se reasigna.
    e.periodo = data.periodo
    e.rol = data.rol
    e.descripcion = data.descripcion
    e.monto = data.monto
    e.tarifa = data.tarifa
    e.no_sujeto = data.no_sujeto
    e.deducible = data.deducible
    db.commit()
    db.refresh(e)
    return e
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_entradas_manuales.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/entradas_manuales.py backend/tests/test_entradas_manuales.py
git commit -m "feat(backend): PUT /api/entradas-manuales/{id} (404/422)"
```

---

### Task 3: Frontend — hooks de entradas (+ exportar `periodoApi`)

**Files:**
- Modify: `frontend/src/api/hooks.ts`
- Test: `frontend/src/api/hooks.test.tsx`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `frontend/src/api/hooks.test.tsx` (reusa `server`/`wrapper`; extender el import desde `./hooks` con `useEntradasManuales`):
```tsx
it('useEntradasManuales manda periodo=YYYYMM y devuelve entradas+totales', async () => {
  let url = '';
  server.use(http.get('*/api/entradas-manuales', ({ request }) => {
    url = new URL(request.url).search;
    return HttpResponse.json({ entradas: [{ id: 1, cliente_id: 7, periodo: '202605', rol: 'venta', descripcion: 'Subasta', monto: '2000', tarifa: '13', no_sujeto: false, deducible: true, iva: '260' }], total_monto: '2000', total_iva: '260' });
  }));
  const { result } = renderHook(() => useEntradasManuales(7, '2026-05', 'venta'), { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.entradas[0].iva).toBe('260');
  expect(result.current.data?.total_iva).toBe('260');
  expect(url).toContain('periodo=202605');  // periodoApi normaliza YYYY-MM → YYYYMM
});
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd frontend && npx vitest run src/api/hooks.test.tsx`
Expected: FAIL — `useEntradasManuales` no existe.

- [ ] **Step 3: Implementar**

En `frontend/src/api/hooks.ts`:
- **Exportar** el helper `periodoApi` (hoy es `const periodoApi = ...`): cambiar a `export const periodoApi = (p: string) => p.replace(/-/g, '');` (mantener el comentario que tenga).
- Agregar tipos y hooks:
```ts
export interface EntradaManual {
  id: number;
  cliente_id: number;
  periodo: string;
  rol: string;
  descripcion: string | null;
  monto: string;
  tarifa: string;
  no_sujeto: boolean;
  deducible: boolean;
  iva: string;
}
export interface EntradaManualCreate {
  cliente_id: number;
  periodo: string;
  rol: string;
  descripcion?: string | null;
  monto: string;
  tarifa: string;
  no_sujeto: boolean;
  deducible: boolean;
}
export interface EntradasManualesResp {
  entradas: EntradaManual[];
  total_monto: string;
  total_iva: string;
}

const RESP_VACIA: EntradasManualesResp = { entradas: [], total_monto: '0', total_iva: '0' };

export function useEntradasManuales(clienteId: number | null, periodo: string | null, rol: Rol) {
  return useQuery({
    queryKey: ['entradas', clienteId, periodo, rol],
    enabled: clienteId != null && periodo != null,
    queryFn: async () =>
      (await apiFetch<EntradasManualesResp>(
        '/api/entradas-manuales' + qs({ cliente_id: clienteId!, periodo: periodoApi(periodo!), rol }),
      )) ?? RESP_VACIA,
  });
}

export function useCrearEntrada() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: EntradaManualCreate) =>
      apiFetch<EntradaManual>('/api/entradas-manuales', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entradas'] });
      qc.invalidateQueries({ queryKey: ['d150'] });
    },
  });
}

export function useEditarEntrada() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: EntradaManualCreate }) =>
      apiFetch<EntradaManual>(`/api/entradas-manuales/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entradas'] });
      qc.invalidateQueries({ queryKey: ['d150'] });
    },
  });
}

export function useEliminarEntrada() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: number }) =>
      apiFetch<void>(`/api/entradas-manuales/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entradas'] });
      qc.invalidateQueries({ queryKey: ['d150'] });
    },
  });
}
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd frontend && npx vitest run src/api/hooks.test.tsx` (luego full `npx vitest run`)
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/hooks.ts frontend/src/api/hooks.test.tsx
git commit -m "feat(frontend): hooks de entradas manuales (+ exportar periodoApi)"
```

---

### Task 4: Frontend — `EntradasManualesPage`

**Files:**
- Create: `frontend/src/pages/EntradasManualesPage.tsx`
- Test: `frontend/src/pages/EntradasManualesPage.test.tsx`

- [ ] **Step 1: Implementar `EntradasManualesPage.tsx`**

```tsx
import { useState } from 'react';
import { Table, Button, Modal, TextInput, NumberInput, Checkbox, Stack, Group, Title, Alert, Loader, Text } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useSeleccion } from '../context/SeleccionContext';
import {
  useEntradasManuales, useCrearEntrada, useEditarEntrada, useEliminarEntrada,
  EntradaManual, EntradaManualCreate, periodoApi,
} from '../api/hooks';
import { ApiError } from '../api/client';
import { formatColones } from '../lib/money';

interface FormValues {
  descripcion: string;
  monto: number | string;
  tarifa: number | string;
  no_sujeto: boolean;
  deducible: boolean;
}
const VACIO: FormValues = { descripcion: '', monto: 0, tarifa: 0, no_sujeto: false, deducible: true };

export function EntradasManualesPage() {
  const { clienteId, periodo, rol } = useSeleccion();
  const { data, isLoading, isError, refetch } = useEntradasManuales(clienteId, periodo, rol);
  const crear = useCrearEntrada();
  const editar = useEditarEntrada();
  const eliminar = useEliminarEntrada();
  const [editando, setEditando] = useState<EntradaManual | null | undefined>(undefined); // undefined=cerrado, null=nuevo, Entrada=editar
  const [aEliminar, setAEliminar] = useState<EntradaManual | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorEliminar, setErrorEliminar] = useState<string | null>(null);
  const form = useForm<FormValues>({ initialValues: VACIO });

  function abrirNuevo() {
    setError(null);
    form.setValues(VACIO);
    setEditando(null);
  }
  function abrirEditar(e: EntradaManual) {
    setError(null);
    form.setValues({ descripcion: e.descripcion ?? '', monto: e.monto, tarifa: e.tarifa, no_sujeto: e.no_sujeto, deducible: e.deducible });
    setEditando(e);
  }
  function cerrar() {
    setEditando(undefined);
    setError(null);
    form.reset();
  }

  async function onSubmit(values: FormValues) {
    if (clienteId == null || periodo == null) return;
    setError(null);
    const payload: EntradaManualCreate = {
      cliente_id: clienteId,
      periodo: periodoApi(periodo), // YYYY-MM → YYYYMM para el backend
      rol,
      descripcion: values.descripcion.trim() || null,
      monto: String(values.monto),
      tarifa: String(values.tarifa),
      no_sujeto: values.no_sujeto,
      deducible: values.deducible,
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
    if (!aEliminar) return;
    setErrorEliminar(null);
    try {
      await eliminar.mutateAsync({ id: aEliminar.id });
      setAEliminar(null);
    } catch (e) {
      setErrorEliminar(e instanceof ApiError ? e.detail : 'Error al eliminar');
    }
  }

  if (clienteId == null || periodo == null)
    return <Alert color="yellow">Elegí cliente y período en la barra superior.</Alert>;
  if (isLoading) return <Loader />;
  if (isError)
    return <Alert color="red">Error al cargar <Button size="xs" onClick={() => refetch()}>Reintentar</Button></Alert>;

  const resp = data ?? { entradas: [], total_monto: '0', total_iva: '0' };

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Entradas manuales</Title>
        <Button onClick={abrirNuevo}>Nueva entrada</Button>
      </Group>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Descripción</Table.Th>
            <Table.Th>Monto</Table.Th>
            <Table.Th>Tarifa</Table.Th>
            <Table.Th>No sujeto</Table.Th>
            <Table.Th>Deducible</Table.Th>
            <Table.Th>IVA</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {resp.entradas.map((e) => (
            <Table.Tr key={e.id}>
              <Table.Td>{e.descripcion ?? '—'}</Table.Td>
              <Table.Td>{formatColones(e.monto)}</Table.Td>
              <Table.Td>{e.tarifa}%</Table.Td>
              <Table.Td>{e.no_sujeto ? '✓' : '—'}</Table.Td>
              <Table.Td>{e.deducible ? '✓' : '—'}</Table.Td>
              <Table.Td>{formatColones(e.iva)}</Table.Td>
              <Table.Td>
                <Group gap="xs">
                  <Button variant="subtle" size="xs" onClick={() => abrirEditar(e)}>Editar</Button>
                  <Button variant="subtle" color="red" size="xs" onClick={() => { setErrorEliminar(null); setAEliminar(e); }}>Eliminar</Button>
                </Group>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
        <Table.Tfoot>
          <Table.Tr>
            <Table.Th>Total ({resp.entradas.length})</Table.Th>
            <Table.Th>{formatColones(resp.total_monto)}</Table.Th>
            <Table.Th />
            <Table.Th />
            <Table.Th />
            <Table.Th>{formatColones(resp.total_iva)}</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Tfoot>
      </Table>

      <Modal opened={editando !== undefined} onClose={cerrar} title={editando ? 'Editar entrada' : 'Nueva entrada'}>
        <form onSubmit={form.onSubmit(onSubmit)}>
          <Stack>
            {error && <Alert color="red">{error}</Alert>}
            <TextInput label="Descripción" {...form.getInputProps('descripcion')} />
            <Group grow>
              <NumberInput label="Monto (₡)" min={0} decimalScale={5} {...form.getInputProps('monto')} />
              <NumberInput label="Tarifa (%)" min={0} decimalScale={4} {...form.getInputProps('tarifa')} />
            </Group>
            <Group>
              <Checkbox label="No sujeto" {...form.getInputProps('no_sujeto', { type: 'checkbox' })} />
              <Checkbox label="Deducible" {...form.getInputProps('deducible', { type: 'checkbox' })} />
            </Group>
            <Button type="submit" loading={crear.isPending || editar.isPending}>Guardar</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={aEliminar !== null} onClose={() => { setAEliminar(null); setErrorEliminar(null); }} title="Eliminar entrada">
        <Text>¿Eliminar esta entrada manual?</Text>
        {errorEliminar && <Alert color="red">{errorEliminar}</Alert>}
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={() => setAEliminar(null)}>Cancelar</Button>
          <Button color="red" loading={eliminar.isPending} onClick={confirmarEliminar}>Eliminar</Button>
        </Group>
      </Modal>
    </Stack>
  );
}
```

- [ ] **Step 2: Escribir el test** (`frontend/src/pages/EntradasManualesPage.test.tsx`)

```tsx
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/utils';
import { SeleccionProvider } from '../context/SeleccionContext';
import { EntradasManualesPage } from './EntradasManualesPage';

const ENTRADA = { id: 7, cliente_id: 1, periodo: '202605', rol: 'venta', descripcion: 'Subasta ganado', monto: '2450000', tarifa: '1', no_sujeto: false, deducible: true, iva: '24500' };
const RESP = { entradas: [ENTRADA], total_monto: '2450000', total_iva: '24500' };

const server = setupServer(
  http.get('*/api/entradas-manuales', () => HttpResponse.json(RESP)),
);
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

function conSeleccion(ui: React.ReactNode) {
  return <SeleccionProvider initialClienteId={1} initialPeriodo="2026-05" initialRol="venta">{ui}</SeleccionProvider>;
}

it('pide cliente/período cuando no hay selección', () => {
  renderWithProviders(<SeleccionProvider><EntradasManualesPage /></SeleccionProvider>);
  expect(screen.getByText('Elegí cliente y período en la barra superior.')).toBeInTheDocument();
});

it('lista entradas y muestra los totales en el footer', async () => {
  renderWithProviders(conSeleccion(<EntradasManualesPage />));
  expect(await screen.findByText('Subasta ganado')).toBeInTheDocument();
  // monto e IVA formateados
  expect(screen.getByText('₡2.450.000,00')).toBeInTheDocument();
  expect(screen.getByText('₡24.500,00')).toBeInTheDocument();
});

it('edita una entrada con PUT al id correcto y período YYYYMM', async () => {
  let putId = '';
  let body: Record<string, unknown> | null = null;
  server.use(http.put('*/api/entradas-manuales/:id', async ({ request, params }) => {
    putId = String(params.id);
    body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ ...ENTRADA, descripcion: 'corregida' });
  }));
  renderWithProviders(conSeleccion(<EntradasManualesPage />));
  await userEvent.click(await screen.findByRole('button', { name: 'Editar' }));
  await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));
  await waitFor(() => expect(putId).toBe('7'));
  expect(body).toMatchObject({ periodo: '202605', rol: 'venta' });
});

it('elimina una entrada tras confirmar', async () => {
  let delId = '';
  server.use(http.delete('*/api/entradas-manuales/:id', ({ params }) => {
    delId = String(params.id);
    return new HttpResponse(null, { status: 204 });
  }));
  renderWithProviders(conSeleccion(<EntradasManualesPage />));
  await userEvent.click(await screen.findByRole('button', { name: 'Eliminar' }));
  const dialog = await screen.findByRole('dialog');
  await userEvent.click(within(dialog).getByRole('button', { name: 'Eliminar' }));
  await waitFor(() => expect(delId).toBe('7'));
});
```

Notas (ajustar SOLO queries del test, no la lógica): usar `within(dialog)` para desambiguar el botón "Eliminar" del modal respecto al de la fila. El test de editar abre el modal precargado y guarda sin cambiar campos (la aserción clave es el PUT al id 7 con `periodo: '202605'`, que prueba el `periodoApi` en el body). Mantine `Modal` rinde con `role="dialog"`.

- [ ] **Step 3: Correr y verificar que pasan**

Run: `cd frontend && npx vitest run src/pages/EntradasManualesPage.test.tsx` (luego full `npx vitest run`)
Expected: PASS (4 tests).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/EntradasManualesPage.tsx frontend/src/pages/EntradasManualesPage.test.tsx
git commit -m "feat(frontend): página de entradas manuales (tabla + totales + crear/editar/eliminar)"
```

---

### Task 5: Frontend — navegación

**Files:**
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AppShell.test.tsx`

- [ ] **Step 1: Actualizar el test de AppShell (TDD)**

En `frontend/src/components/AppShell.test.tsx`, junto a las aserciones existentes:
```tsx
  expect(screen.getByRole('link', { name: 'Entradas manuales' })).toBeInTheDocument();
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd frontend && npx vitest run src/components/AppShell.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Agregar el enlace y la ruta**

En `frontend/src/components/AppShell.tsx`, agregar a `LINKS` (al final):
```tsx
  { to: '/entradas-manuales', label: 'Entradas manuales' },
```

En `frontend/src/App.tsx`, importar la página y agregar la ruta dentro del `<Routes>` anidado (antes del catch-all `*`):
```tsx
import { EntradasManualesPage } from './pages/EntradasManualesPage';
// ...
                <Route path="/entradas-manuales" element={<EntradasManualesPage />} />
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd frontend && npx vitest run src/components/AppShell.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AppShell.tsx frontend/src/components/AppShell.test.tsx frontend/src/App.tsx
git commit -m "feat(frontend): enlace y ruta de Entradas manuales en el AppShell"
```

---

### Task 6: Verificación final

- [ ] **Step 1: Suite backend**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest -q`
Expected: toda la suite verde.

- [ ] **Step 2: Suite frontend + tipos + build**

Run: `cd frontend && npx vitest run && npx tsc -b && npm run build`
Expected: tests verdes, `tsc -b` sin errores, build exitoso.

- [ ] **Step 3: Commit final si hubo ajustes**

```bash
git add -A
git commit -m "chore: ajustes finales entradas manuales"
```

---

## Self-Review (cobertura del spec)

- `EntradaManualOut.iva` calculado (espeja d150) + helper `iva_entrada` → Task 1. ✔
- `GET` devuelve `{entradas, total_monto, total_iva}` (totales Decimal) + adaptar tests viejos → Task 1. ✔
- `PUT /api/entradas-manuales/{id}` (404/422, no reasigna cliente) → Task 2. ✔
- Hooks `useEntradasManuales/useCrearEntrada/useEditarEntrada/useEliminarEntrada` + exportar `periodoApi` + invalidar d150 → Task 3. ✔
- `EntradasManualesPage` (tabla + footer totales + modal crear/editar + confirmación borrado + guard) → Task 4. ✔
- Período en el body como YYYYMM (`periodoApi`) → Task 4 (payload) + Task 3 (query). ✔
- Dinero como string + `formatColones`; IVA/totales del backend → Tasks 1 y 4. ✔
- Sidebar + ruta → Task 5. ✔
- Pruebas backend (iva/totales/PUT) y frontend (hook + página, incl. período YYYYMM en el body) → Tasks 1-4. ✔

Riesgos conocidos (notas en el plan): formato exacto de los strings Decimal en los tests del backend (se comparan con `Decimal(...)`); queries RTL del modal (usar `within(dialog)`); display de `tarifa` como `{e.tarifa}%` (puede mostrar decimales del Numeric, cosmético).
