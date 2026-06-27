# Preclasificación por CABYS/cédula (diferido 1D) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Asistente que surface las líneas "Sin Clasificar" de un cliente·período·rol agrupadas por CABYS o por cédula del proveedor, y permite asignarles clasificación en lote creando reglas.

**Architecture:** Backend: un motor puro (`motor/preclasificacion.py`) que agrupa las líneas no clasificadas (reusando el engine de clasificación), expuesto por `GET /api/preclasificacion`. Frontend: hook `usePreclasificacion`, `PreclasificarPage` con dos pestañas que reusan `POST /api/reglas` para guardar, y una entrada de navegación.

**Tech Stack:** Backend FastAPI/SQLAlchemy/pytest. Frontend React/Mantine 7/TanStack Query/Vitest+RTL+MSW.

---

## Convenciones (leer antes de empezar)

- Spec: `docs/plans/2026-06-26-fase1d-preclasificacion-cabys-design.md`.
- Worktree: `C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\.claude\worktrees\reverent-lederberg-08f91d`. Rama `claude/fase1d-preclasificacion` (desde main, con el slice de reglas ya integrado).
- **Backend tests** (worktree sin venv propio), desde el worktree en Bash:
  ```bash
  cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest -q
  ```
  Requiere PostgreSQL local :5433 (crea/borra `sistemaxml_test`). Si Postgres está caído, reportar BLOCKED.
- **Frontend** (desde `frontend/`): `npx vitest run <file>`, `npx tsc -b`, `npm run build`. Vitest globals on. MSW `*/...` wildcard. `renderWithProviders` (Mantine env=test + Notifications + QueryClient + MemoryRouter). `SeleccionProvider` acepta `initialClienteId`/`initialPeriodo`/`initialRol`.
- Commits: uno por tarea, español, prefijo `feat(backend)`/`feat(frontend)`/`test(...)`.
- Dinero: la base se muestra con `formatColones`; nunca aritmética float.

## Estructura de archivos

```
backend/app/motor/preclasificacion.py        # grupos_sin_clasificar (motor puro)
backend/tests/test_preclasificacion.py        # tests del motor
backend/app/routers/preclasificacion.py       # GET /api/preclasificacion
backend/app/main.py                            # registrar el router
backend/tests/test_preclasificacion_endpoint.py
frontend/src/api/hooks.ts                      # usePreclasificacion + tipos
frontend/src/api/hooks.test.tsx                # test del hook
frontend/src/pages/PreclasificarPage.tsx
frontend/src/pages/PreclasificarPage.test.tsx
frontend/src/components/AppShell.tsx           # + link "Preclasificar"
frontend/src/components/AppShell.test.tsx      # asserts 6 links
frontend/src/App.tsx                           # + ruta /preclasificar
```

---

### Task 1: Backend — motor `grupos_sin_clasificar`

**Files:**
- Create: `backend/app/motor/preclasificacion.py`
- Test: `backend/tests/test_preclasificacion.py`

Contexto: `motor/clasificacion.py` expone `build_lookup(reglas)` y `clasificar(cedula, cabys, rol, lookup) -> (clas, sub)`; devuelve `("Sin Clasificar", "")` si nada matchea. `motor/resumen.py` muestra el patrón de iterar `LineaComprobante` join `Comprobante` y derivar la cédula de la contraparte (`emisor_cedula` en compra, `receptor_cedula` en venta). Modelos: `LineaComprobante(cabys, detalle, base_imponible, ...)`, `Comprobante(cliente_id, periodo, rol, emisor_cedula, emisor_nombre, receptor_cedula, receptor_nombre, ...)`.

- [ ] **Step 1: Escribir el test que falla** (`backend/tests/test_preclasificacion.py`)

```python
from decimal import Decimal
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante, LineaComprobante
from app.models.regla_clasificacion import ReglaClasificacion
from app.motor.preclasificacion import grupos_sin_clasificar


def _cliente(db):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db.add(c); db.commit(); db.refresh(c)
    return c


def _comp_con_lineas(db, cliente_id, emisor_ced, emisor_nom, lineas):
    """lineas: list of (cabys, detalle, base)."""
    comp = Comprobante(cliente_id=cliente_id, clave=f"k{emisor_ced}{len(lineas)}{db.query(Comprobante).count()}",
                       tipo_doc="FacturaElectronica", consecutivo="1",
                       fecha=__import__("datetime").datetime(2026, 5, 1), periodo="202605", rol="compra",
                       emisor_cedula=emisor_ced, emisor_nombre=emisor_nom,
                       receptor_cedula="3102858282", receptor_nombre="Agrofinca", xml_raw="<x/>")
    db.add(comp); db.flush()
    for i, (cabys, detalle, base) in enumerate(lineas, 1):
        db.add(LineaComprobante(comprobante_id=comp.id, numero=i, cabys=cabys, detalle=detalle,
                                base_imponible=Decimal(base), tarifa_label="13%", tipo="Bienes",
                                iva_monto=Decimal("0")))
    db.commit()
    return comp


def test_agrupa_por_cabys(db_session):
    cli = _cliente(db_session)
    _comp_con_lineas(db_session, cli.id, "3101030042", "Insumos", [
        ("2310100000000", "Fertilizante", "100"),
        ("2310100000000", "Fertilizante NPK", "50"),
        ("3420100000000", "Diésel", "200"),
    ])
    grupos = grupos_sin_clasificar(db_session, cli.id, "202605", "compra", "cabys")
    # ordenado por base desc: diésel 200, fertilizante 150
    assert [g.clave for g in grupos] == ["3420100000000", "2310100000000"]
    fert = next(g for g in grupos if g.clave == "2310100000000")
    assert fert.lineas == 2
    assert fert.base == Decimal("150")
    assert fert.etiqueta  # alguna muestra de detalle no vacía


def test_agrupa_por_cedula(db_session):
    cli = _cliente(db_session)
    _comp_con_lineas(db_session, cli.id, "3101030042", "Insumos del Valle", [
        ("2310100000000", "Fertilizante", "100"),
    ])
    _comp_con_lineas(db_session, cli.id, "3102888777", "Transportes Sur", [
        ("8511000000000", "Flete", "300"),
    ])
    grupos = grupos_sin_clasificar(db_session, cli.id, "202605", "compra", "cedula")
    assert [g.clave for g in grupos] == ["3102888777", "3101030042"]
    ins = next(g for g in grupos if g.clave == "3101030042")
    assert ins.etiqueta == "Insumos del Valle"
    assert ins.base == Decimal("100")


def test_excluye_lo_ya_cubierto_por_regla(db_session):
    cli = _cliente(db_session)
    _comp_con_lineas(db_session, cli.id, "3101030042", "Insumos", [
        ("2310100000000", "Fertilizante", "100"),
        ("3420100000000", "Diésel", "200"),
    ])
    # Regla por CABYS para fertilizante → ya no es "Sin Clasificar"
    db_session.add(ReglaClasificacion(cliente_id=cli.id, cabys="2310100000000", clasificacion="Compras"))
    db_session.commit()
    grupos = grupos_sin_clasificar(db_session, cli.id, "202605", "compra", "cabys")
    assert [g.clave for g in grupos] == ["3420100000000"]


def test_omite_clave_vacia(db_session):
    cli = _cliente(db_session)
    _comp_con_lineas(db_session, cli.id, "3101030042", "Insumos", [("", "Sin cabys", "100")])
    assert grupos_sin_clasificar(db_session, cli.id, "202605", "compra", "cabys") == []


def test_por_invalido(db_session):
    cli = _cliente(db_session)
    import pytest
    with pytest.raises(ValueError):
        grupos_sin_clasificar(db_session, cli.id, "202605", "compra", "otro")
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_preclasificacion.py -q`
Expected: FAIL — `app.motor.preclasificacion` no existe.

- [ ] **Step 3: Implementar** (`backend/app/motor/preclasificacion.py`)

```python
"""Asistente de preclasificación: agrupa las líneas que quedan 'Sin Clasificar'
(según el engine de reglas) por CABYS o por cédula de la contraparte, para asignarlas
en lote. No escribe nada; solo agrega para mostrar."""
from dataclasses import dataclass
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.comprobante import Comprobante, LineaComprobante
from app.models.regla_clasificacion import ReglaClasificacion
from app.motor.clasificacion import build_lookup, clasificar


@dataclass
class Grupo:
    clave: str
    etiqueta: str
    lineas: int
    base: Decimal


def grupos_sin_clasificar(db: Session, cliente_id: int, periodo: str, rol: str,
                          por: str = "cabys") -> list[Grupo]:
    if por not in ("cabys", "cedula"):
        raise ValueError("por debe ser 'cabys' o 'cedula'")
    reglas = db.scalars(select(ReglaClasificacion).where(
        ReglaClasificacion.cliente_id == cliente_id))
    lookup = build_lookup(reglas)
    stmt = (
        select(LineaComprobante, Comprobante)
        .join(Comprobante, LineaComprobante.comprobante_id == Comprobante.id)
        .where(
            Comprobante.cliente_id == cliente_id,
            Comprobante.periodo == periodo,
            Comprobante.rol == rol,
        )
    )
    acc: dict[str, dict] = {}
    for ln, comp in db.execute(stmt):
        cedula = comp.emisor_cedula if rol == "compra" else comp.receptor_cedula
        clas, _ = clasificar(cedula, ln.cabys, rol, lookup)
        if clas != "Sin Clasificar":
            continue
        if por == "cabys":
            clave = (ln.cabys or "").strip()
            etiqueta = (ln.detalle or "").strip()
        else:
            clave = (cedula or "").strip()
            etiqueta = (comp.emisor_nombre if rol == "compra" else comp.receptor_nombre) or ""
        if not clave:
            continue
        g = acc.get(clave)
        if g is None:
            acc[clave] = {"etiqueta": etiqueta, "lineas": 1, "base": ln.base_imponible}
        else:
            g["lineas"] += 1
            g["base"] += ln.base_imponible
            if not g["etiqueta"] and etiqueta:
                g["etiqueta"] = etiqueta
    grupos = [Grupo(clave=k, etiqueta=v["etiqueta"], lineas=v["lineas"], base=v["base"])
              for k, v in acc.items()]
    grupos.sort(key=lambda g: g.base, reverse=True)
    return grupos
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_preclasificacion.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/motor/preclasificacion.py backend/tests/test_preclasificacion.py
git commit -m "feat(backend): motor de preclasificacion (agrupa lineas Sin Clasificar por CABYS/cedula)"
```

---

### Task 2: Backend — endpoint `GET /api/preclasificacion`

**Files:**
- Create: `backend/app/routers/preclasificacion.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_preclasificacion_endpoint.py`

- [ ] **Step 1: Escribir el test que falla** (`backend/tests/test_preclasificacion_endpoint.py`)

```python
from datetime import datetime
from decimal import Decimal
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante, LineaComprobante
from app.auth.security import hash_password


def _token(client, db):
    db.add(Usuario(nombre="pre", password_hash=hash_password("clave12345"), es_admin=True))
    db.commit()
    return client.post("/auth/login", data={"username": "pre", "password": "clave12345"}).json()["access_token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _cliente(db):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db.add(c); db.commit(); db.refresh(c)
    return c


def _comp(db, cliente_id, cabys, detalle, base):
    comp = Comprobante(cliente_id=cliente_id, clave=f"k{cabys}{db.query(Comprobante).count()}",
                       tipo_doc="FacturaElectronica", consecutivo="1", fecha=datetime(2026, 5, 1),
                       periodo="202605", rol="compra", emisor_cedula="3101030042", emisor_nombre="Insumos",
                       receptor_cedula="3102858282", receptor_nombre="Agrofinca", xml_raw="<x/>")
    db.add(comp); db.flush()
    db.add(LineaComprobante(comprobante_id=comp.id, numero=1, cabys=cabys, detalle=detalle,
                            base_imponible=Decimal(base), tarifa_label="13%", tipo="Bienes", iva_monto=Decimal("0")))
    db.commit()


def test_preclasificacion_ok(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    _comp(db_session, cli.id, "2310100000000", "Fertilizante", "100")
    r = client.get(f"/api/preclasificacion?cliente_id={cli.id}&periodo=202605&rol=compra&por=cabys", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["clave"] == "2310100000000"
    assert body[0]["lineas"] == 1
    assert body[0]["base"] == "100.00000"  # Decimal Numeric(18,5) → str

def test_preclasificacion_por_invalido_422(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    r = client.get(f"/api/preclasificacion?cliente_id={cli.id}&periodo=202605&rol=compra&por=otro", headers=_auth(token))
    assert r.status_code == 422

def test_preclasificacion_rol_invalido_422(client, db_session):
    token = _token(client, db_session); cli = _cliente(db_session)
    r = client.get(f"/api/preclasificacion?cliente_id={cli.id}&periodo=202605&rol=otro&por=cabys", headers=_auth(token))
    assert r.status_code == 422

def test_preclasificacion_sin_token_401(client):
    assert client.get("/api/preclasificacion?cliente_id=1&periodo=202605&rol=compra").status_code == 401
```

Nota: el valor exacto de `base` serializado depende de la precisión `Numeric(18,5)` → probablemente `"100.00000"`. Si el string real difiere, ajustar la aserción al valor real (NO cambiar la implementación). Lo esencial es que sea el string del Decimal.

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_preclasificacion_endpoint.py -q`
Expected: FAIL — 404 (ruta inexistente).

- [ ] **Step 3: Implementar el router** (`backend/app/routers/preclasificacion.py`)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.motor.preclasificacion import grupos_sin_clasificar

router = APIRouter(prefix="/api/preclasificacion", tags=["preclasificacion"])


@router.get("")
def preclasificacion(cliente_id: int, periodo: str, rol: str, por: str = "cabys",
                     db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    if rol not in ("compra", "venta"):
        raise HTTPException(status_code=422, detail="rol debe ser 'compra' o 'venta'")
    if por not in ("cabys", "cedula"):
        raise HTTPException(status_code=422, detail="por debe ser 'cabys' o 'cedula'")
    grupos = grupos_sin_clasificar(db, cliente_id, periodo, rol, por)
    return [{"clave": g.clave, "etiqueta": g.etiqueta, "lineas": g.lineas, "base": str(g.base)}
            for g in grupos]
```

Registrar en `backend/app/main.py`: agregar el import junto a los otros routers y el `include_router`:
```python
from app.routers.preclasificacion import router as preclasificacion_router
# ...
app.include_router(preclasificacion_router)
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_preclasificacion_endpoint.py -q`
Expected: PASS (4 tests). Si la aserción de `base` falla por el formato, ajustarla al string real.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/preclasificacion.py backend/app/main.py backend/tests/test_preclasificacion_endpoint.py
git commit -m "feat(backend): GET /api/preclasificacion (grupos sin clasificar por CABYS/cedula)"
```

---

### Task 3: Frontend — hook `usePreclasificacion`

**Files:**
- Modify: `frontend/src/api/hooks.ts`
- Test: `frontend/src/api/hooks.test.tsx`

- [ ] **Step 1: Escribir el test que falla** (agregar a `frontend/src/api/hooks.test.tsx`; reusa el `server`/`wrapper` ya definidos; extender el import desde `./hooks` con `usePreclasificacion`)

```tsx
it('usePreclasificacion pasa cliente_id/periodo/rol/por', async () => {
  let url = '';
  server.use(http.get('*/api/preclasificacion', ({ request }) => {
    url = new URL(request.url).search;
    return HttpResponse.json([{ clave: '2310100', etiqueta: 'Fertilizante', lineas: 2, base: '150' }]);
  }));
  const { result } = renderHook(() => usePreclasificacion(7, '2026-05', 'compra', 'cabys'), { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.[0].clave).toBe('2310100');
  expect(url).toContain('cliente_id=7');
  expect(url).toContain('periodo=2026-05');
  expect(url).toContain('rol=compra');
  expect(url).toContain('por=cabys');
});

it('usePreclasificacion no dispara sin cliente o período', () => {
  const { result } = renderHook(() => usePreclasificacion(null, '2026-05', 'compra', 'cabys'), { wrapper });
  expect(result.current.fetchStatus).toBe('idle');
});
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd frontend && npx vitest run src/api/hooks.test.tsx`
Expected: FAIL — `usePreclasificacion` no existe.

- [ ] **Step 3: Implementar** (agregar a `frontend/src/api/hooks.ts`; reusa `qs`, `Rol`)

```ts
export interface GrupoPreclasificacion {
  clave: string;
  etiqueta: string;
  lineas: number;
  base: string;
}
export type PorPreclasificacion = 'cabys' | 'cedula';

export function usePreclasificacion(
  clienteId: number | null,
  periodo: string | null,
  rol: Rol,
  por: PorPreclasificacion,
) {
  return useQuery({
    queryKey: ['preclasificacion', clienteId, periodo, rol, por],
    enabled: clienteId != null && periodo != null,
    queryFn: async () =>
      (await apiFetch<GrupoPreclasificacion[]>(
        '/api/preclasificacion' + qs({ cliente_id: clienteId!, periodo: periodo!, rol, por }),
      )) ?? [],
  });
}
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd frontend && npx vitest run src/api/hooks.test.tsx`
Expected: PASS. Luego `npx vitest run` completo.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/hooks.ts frontend/src/api/hooks.test.tsx
git commit -m "feat(frontend): hook usePreclasificacion"
```

---

### Task 4: Frontend — `PreclasificarPage`

**Files:**
- Create: `frontend/src/pages/PreclasificarPage.tsx`
- Test: `frontend/src/pages/PreclasificarPage.test.tsx`

- [ ] **Step 1: Implementar `PreclasificarPage.tsx`**

```tsx
import { useState } from 'react';
import { Stack, Title, Tabs, Table, Select, TextInput, Button, Group, Alert, Loader, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useSeleccion, Rol } from '../context/SeleccionContext';
import { usePreclasificacion, useCrearRegla, PorPreclasificacion, ReglaCreate } from '../api/hooks';
import { formatColones } from '../lib/money';
import { useQueryClient } from '@tanstack/react-query';

const CLASIFICACIONES = ['Compras', 'Gastos', 'Bienes de Capital', 'No Deducibles', 'Sin Clasificar'];

interface Asignacion {
  clasificacion: string;
  sub: string;
}

function Panel({ por, clienteId, periodo, rol }: { por: PorPreclasificacion; clienteId: number; periodo: string; rol: Rol }) {
  const { data, isLoading, isError, refetch } = usePreclasificacion(clienteId, periodo, rol, por);
  const crear = useCrearRegla();
  const qc = useQueryClient();
  const [asig, setAsig] = useState<Record<string, Asignacion>>({});

  function setClas(clave: string, clasificacion: string) {
    setAsig((a) => ({ ...a, [clave]: { clasificacion, sub: a[clave]?.sub ?? '' } }));
  }
  function setSub(clave: string, sub: string) {
    setAsig((a) => ({ ...a, [clave]: { clasificacion: a[clave]?.clasificacion ?? '', sub } }));
  }

  async function guardar() {
    const elegidas = Object.entries(asig).filter(([, v]) => v.clasificacion);
    if (elegidas.length === 0) return;
    const results = await Promise.allSettled(
      elegidas.map(([clave, v]) => {
        const payload: ReglaCreate =
          por === 'cabys'
            ? { cliente_id: clienteId, cabys: clave, clasificacion: v.clasificacion, sub_clasificacion: v.sub.trim() || null, rol: null }
            : { cliente_id: clienteId, cedula: clave, clasificacion: v.clasificacion, rol };
        return crear.mutateAsync(payload);
      }),
    );
    const ok = results.filter((r) => r.status === 'fulfilled').length;
    const fail = results.length - ok;
    notifications.show({
      color: fail ? 'orange' : 'teal',
      message: `${ok} regla(s) creada(s)${fail ? `, ${fail} con error` : ''}`,
    });
    setAsig({});
    qc.invalidateQueries({ queryKey: ['preclasificacion'] });
    qc.invalidateQueries({ queryKey: ['resumen'] });
    qc.invalidateQueries({ queryKey: ['resumen-clasificacion'] });
    refetch();
  }

  if (isLoading) return <Loader />;
  if (isError)
    return <Alert color="red">Error al cargar <Button size="xs" onClick={() => refetch()}>Reintentar</Button></Alert>;
  const grupos = data ?? [];
  if (grupos.length === 0)
    return <Text c="dimmed">No hay líneas sin clasificar para este período/rol.</Text>;

  const hayAsignadas = Object.values(asig).some((v) => v.clasificacion);

  return (
    <Stack>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{por === 'cabys' ? 'CABYS' : 'Cédula'}</Table.Th>
            <Table.Th>{por === 'cabys' ? 'Detalle' : 'Proveedor'}</Table.Th>
            <Table.Th>Líneas</Table.Th>
            <Table.Th>Base</Table.Th>
            <Table.Th>Clasificación</Table.Th>
            {por === 'cabys' && <Table.Th>Sub-clasif.</Table.Th>}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {grupos.map((g) => (
            <Table.Tr key={g.clave}>
              <Table.Td>{g.clave}</Table.Td>
              <Table.Td>{g.etiqueta || '—'}</Table.Td>
              <Table.Td>{g.lineas}</Table.Td>
              <Table.Td>{formatColones(g.base)}</Table.Td>
              <Table.Td>
                <Select
                  data={CLASIFICACIONES}
                  placeholder="— elegir —"
                  value={asig[g.clave]?.clasificacion || null}
                  onChange={(v) => setClas(g.clave, v ?? '')}
                  aria-label={`Clasificación ${g.clave}`}
                  w={170}
                />
              </Table.Td>
              {por === 'cabys' && (
                <Table.Td>
                  <TextInput
                    placeholder="—"
                    value={asig[g.clave]?.sub ?? ''}
                    onChange={(e) => setSub(g.clave, e.currentTarget.value)}
                    aria-label={`Sub ${g.clave}`}
                    w={130}
                  />
                </Table.Td>
              )}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Group justify="flex-end">
        <Button onClick={guardar} loading={crear.isPending} disabled={!hayAsignadas}>
          Guardar asignaciones
        </Button>
      </Group>
    </Stack>
  );
}

export function PreclasificarPage() {
  const { clienteId, periodo, rol } = useSeleccion();
  if (clienteId == null || periodo == null)
    return <Alert color="yellow">Elegí cliente y período en la barra superior.</Alert>;
  return (
    <Stack>
      <Title order={2}>Preclasificar</Title>
      <Tabs defaultValue="cabys" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="cabys">Por CABYS</Tabs.Tab>
          <Tabs.Tab value="cedula">Por proveedor</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="cabys" pt="md">
          <Panel por="cabys" clienteId={clienteId} periodo={periodo} rol={rol} />
        </Tabs.Panel>
        <Tabs.Panel value="cedula" pt="md">
          <Panel por="cedula" clienteId={clienteId} periodo={periodo} rol={rol} />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
```

Nota: `keepMounted={false}` hace que solo la pestaña activa esté montada (una sola query a la vez y un solo botón "Guardar" en el DOM — más simple de testear y evita disparar ambas queries).

- [ ] **Step 2: Escribir el test** (`frontend/src/pages/PreclasificarPage.test.tsx`)

```tsx
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/utils';
import { SeleccionProvider } from '../context/SeleccionContext';
import { PreclasificarPage } from './PreclasificarPage';

function gruposPor(request: Request) {
  const por = new URL(request.url).searchParams.get('por');
  if (por === 'cabys') return [{ clave: '3420100', etiqueta: 'Diésel', lineas: 12, base: '1240000' }];
  return [{ clave: '3101030042', etiqueta: 'Insumos del Valle', lineas: 14, base: '1690500' }];
}

const server = setupServer(
  http.get('*/api/preclasificacion', ({ request }) => HttpResponse.json(gruposPor(request))),
);
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

function conSeleccion(ui: React.ReactNode) {
  return <SeleccionProvider initialClienteId={1} initialPeriodo="2026-05">{ui}</SeleccionProvider>;
}

it('pide cliente/período cuando no hay selección', () => {
  renderWithProviders(<SeleccionProvider><PreclasificarPage /></SeleccionProvider>);
  expect(screen.getByText('Elegí cliente y período en la barra superior.')).toBeInTheDocument();
});

it('asigna por CABYS y guarda creando regla con rol null', async () => {
  let body: Record<string, unknown> | null = null;
  server.use(http.post('*/api/reglas', async ({ request }) => {
    body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: 1, ...body }, { status: 201 });
  }));
  renderWithProviders(conSeleccion(<PreclasificarPage />));
  expect(await screen.findByText('3420100')).toBeInTheDocument();
  expect(screen.getByText('₡1.240.000,00')).toBeInTheDocument();
  // Abrir el Select de clasificación de esa fila y elegir 'Compras'
  await userEvent.click(screen.getByLabelText('Clasificación 3420100'));
  await userEvent.click(await screen.findByRole('option', { name: 'Compras' }));
  await userEvent.click(screen.getByRole('button', { name: 'Guardar asignaciones' }));
  await waitFor(() => expect(body).toMatchObject({ cabys: '3420100', clasificacion: 'Compras', rol: null }));
});

it('por proveedor crea regla por cédula con el rol del contexto', async () => {
  let body: Record<string, unknown> | null = null;
  server.use(http.post('*/api/reglas', async ({ request }) => {
    body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: 1, ...body }, { status: 201 });
  }));
  renderWithProviders(conSeleccion(<PreclasificarPage />));
  await userEvent.click(screen.getByRole('tab', { name: 'Por proveedor' }));
  expect(await screen.findByText('3101030042')).toBeInTheDocument();
  await userEvent.click(screen.getByLabelText('Clasificación 3101030042'));
  await userEvent.click(await screen.findByRole('option', { name: 'Compras' }));
  await userEvent.click(screen.getByRole('button', { name: 'Guardar asignaciones' }));
  await waitFor(() => expect(body).toMatchObject({ cedula: '3101030042', clasificacion: 'Compras', rol: 'compra' }));
});
```

Notas para el implementador (ajustar SOLO queries del test, no la lógica):
- El Select de Mantine 7: el input accesible se obtiene por `getByLabelText('Clasificación 3420100')`. Al hacer click se abre el dropdown y las opciones tienen `role="option"`. Si `getByLabelText` no matchea el input (Mantine puede exponerlo como combobox), probá `screen.getByRole('textbox', { name: 'Clasificación 3420100' })` o `getByRole('combobox', { name: ... })`. Lo esencial es: elegir 'Compras' en esa fila y verificar el body del POST.
- Con `keepMounted={false}` solo la pestaña activa está montada, así que no hay ambigüedad de doble "Guardar" ni doble Select. Tras click en el tab "Por proveedor", esperá `findByText('3101030042')` antes de interactuar.
- El default de `rol` en `SeleccionProvider` es `'compra'`, por eso la regla por cédula sale con `rol: 'compra'`.

- [ ] **Step 3: Correr y verificar que pasa**

Run: `cd frontend && npx vitest run src/pages/PreclasificarPage.test.tsx`
Expected: PASS (3 tests). Iterar queries del Select según las notas si hace falta.

- [ ] **Step 4: Correr suite completa**

Run: `cd frontend && npx vitest run`
Expected: todo verde.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/PreclasificarPage.tsx frontend/src/pages/PreclasificarPage.test.tsx
git commit -m "feat(frontend): página de preclasificación (tabs CABYS/proveedor, asignación en lote)"
```

---

### Task 5: Frontend — navegación (sidebar + ruta)

**Files:**
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AppShell.test.tsx`

- [ ] **Step 1: Actualizar el test de AppShell (TDD)**

En `frontend/src/components/AppShell.test.tsx`, junto a las aserciones de enlaces existentes, agregar (usando el mismo estilo `getByRole('link', { name })` que los otros):

```tsx
  expect(screen.getByRole('link', { name: 'Preclasificar' })).toBeInTheDocument();
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd frontend && npx vitest run src/components/AppShell.test.tsx`
Expected: FAIL — no existe el enlace.

- [ ] **Step 3: Agregar el enlace y la ruta**

En `frontend/src/components/AppShell.tsx`, agregar a `LINKS` (al final):
```tsx
  { to: '/preclasificar', label: 'Preclasificar' },
```

En `frontend/src/App.tsx`, importar la página y agregar la ruta dentro del `<Routes>` anidado (antes del catch-all `*`):
```tsx
import { PreclasificarPage } from './pages/PreclasificarPage';
// ...
                <Route path="/preclasificar" element={<PreclasificarPage />} />
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd frontend && npx vitest run src/components/AppShell.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AppShell.tsx frontend/src/components/AppShell.test.tsx frontend/src/App.tsx
git commit -m "feat(frontend): enlace y ruta de Preclasificar en el AppShell"
```

---

### Task 6: Verificación final

- [ ] **Step 1: Suite backend**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest -q`
Expected: toda la suite verde (incluye motor + endpoint de preclasificación).

- [ ] **Step 2: Suite frontend + tipos + build**

Run: `cd frontend && npx vitest run && npx tsc -b && npm run build`
Expected: tests verdes, `tsc -b` sin errores, build exitoso.

- [ ] **Step 3: Commit final si hubo ajustes**

```bash
git add -A
git commit -m "chore: ajustes finales preclasificacion"
```

---

## Self-Review (cobertura del spec)

- Motor `grupos_sin_clasificar` (agrupa por CABYS/cédula, excluye lo cubierto por regla, suma base, omite clave vacía, ordena) → Task 1. ✔
- Endpoint `GET /api/preclasificacion` (`por`/`rol` validados, base str, 401) → Task 2. ✔
- Hook `usePreclasificacion` (params, enabled, queryKey) → Task 3. ✔
- `PreclasificarPage` (tabs CABYS/proveedor, tabla con Select + sub en CABYS, guardar en lote reusando POST /api/reglas con rol null/contexto, empty-state, guard) → Task 4. ✔
- Guardado reusa `POST /api/reglas` con `Promise.allSettled` + notificación + invalidación de preclasificacion/reglas/resumen → Task 4. ✔
- Sidebar "Preclasificar" + ruta → Task 5. ✔
- Pruebas backend (motor + endpoint) y frontend (hook + página) → Tasks 1-4. ✔
- Dinero con `formatColones` (string) → Task 4. ✔

Riesgos conocidos (notas en el plan): el formato exacto del string de `base` en el test del endpoint (`Numeric(18,5)` → ajustar al valor real); las queries RTL del `Select` de Mantine (ajustar role/label sin tocar la lógica). `keepMounted={false}` elegido para simplificar el testeo de pestañas y evitar doble query.
