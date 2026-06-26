# Fase 1D — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el primer frontend web del Sistema XML CR (Login → Clientes → Subida XML → Resumen → D-150) sobre la API existente, con marca teal.

**Architecture:** App Vite/React/TS con Mantine. Un wrapper `fetch` tipado es el único punto que conoce la API; hooks de TanStack Query envuelven cada endpoint; las páginas consumen hooks + un `SeleccionContext` global (cliente/período/rol) que vive en una barra superior junto a un sidebar de navegación. Auth por JWT en `localStorage`.

**Tech Stack:** Vite, React 18, TypeScript, Mantine 7 (`core`, `hooks`, `form`, `dropzone`, `notifications`, `dates`), React Router 6, TanStack Query 5. Pruebas: Vitest + React Testing Library + MSW 2 + jsdom.

---

## Convenciones del repo (leer antes de empezar)

- Spec de referencia: `docs/plans/2026-06-25-fase1d-frontend-design.md`.
- Todo el trabajo ocurre en el directorio nuevo `frontend/` (hermano de `backend/`).
- **Dinero como string:** la API serializa `Decimal`→`str`. El front formatea para mostrar; **nunca** hace aritmética en float con montos.
- Comandos de front se corren desde `frontend/`: `npm test` (Vitest, `run` no watch), `npm run dev`.
- Commits: un commit por tarea (al final), mensaje en español, prefijo `feat(frontend):` / `chore(frontend):` / `test(frontend):`.
- Node disponible: v22, npm 11.

## Estructura de archivos

```
frontend/
  package.json
  tsconfig.json
  tsconfig.node.json
  vite.config.ts            # plugin react + proxy /api y /auth → :8000 + config vitest
  index.html
  src/
    main.tsx                # MantineProvider(teal) + QueryClientProvider + Router
    theme.ts                # createTheme({ primaryColor: 'teal' })
    App.tsx                 # rutas + RequireAuth + AppShell
    test/
      setup.ts              # jest-dom + cleanup
      server.ts             # MSW server + handlers base
      utils.tsx             # renderWithProviders
    lib/
      money.ts              # formatColones (puro)
    api/
      client.ts             # apiFetch, ApiError, token storage
      hooks.ts              # hooks TanStack por endpoint
    auth/
      AuthContext.tsx       # token + login + logout
      LoginPage.tsx
      RequireAuth.tsx
    context/
      SeleccionContext.tsx  # cliente/período/rol global
    components/
      AppShell.tsx          # sidebar + barra de contexto
    pages/
      ClientesPage.tsx
      SubidaPage.tsx
      ResumenPage.tsx
      D150Page.tsx
```

Cada archivo tiene una responsabilidad: el wrapper conoce HTTP, los hooks conocen endpoints, las páginas conocen presentación. Se prueban aislados con MSW.

---

### Task 0: Scaffold del proyecto (Vite + Mantine + Vitest)

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/vite.config.ts`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/theme.ts`, `frontend/src/App.tsx`, `frontend/src/test/setup.ts`, `frontend/src/test/utils.tsx`, `frontend/.gitignore`

- [ ] **Step 1: Crear `frontend/package.json`**

```json
{
  "name": "sistema-xml-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@mantine/core": "^7.13.0",
    "@mantine/dates": "^7.13.0",
    "@mantine/dropzone": "^7.13.0",
    "@mantine/form": "^7.13.0",
    "@mantine/hooks": "^7.13.0",
    "@mantine/notifications": "^7.13.0",
    "@tanstack/react-query": "^5.59.0",
    "dayjs": "^1.11.13",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.27.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.2",
    "jsdom": "^25.0.1",
    "msw": "^2.4.9",
    "typescript": "^5.6.2",
    "vite": "^5.4.8",
    "vitest": "^2.1.2"
  }
}
```

- [ ] **Step 2: Crear `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 3: Crear `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Crear `frontend/vite.config.ts`** (proxy + config de Vitest)

```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
  },
});
```

- [ ] **Step 5: Crear `frontend/index.html`**

```html
<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Sistema XML</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Crear `frontend/src/theme.ts`**

```ts
import { createTheme } from '@mantine/core';

export const theme = createTheme({
  primaryColor: 'teal',
});
```

- [ ] **Step 7: Crear `frontend/src/App.tsx`** (placeholder, se completa en Task 6)

```tsx
export function App() {
  return <div>Sistema XML</div>;
}
```

- [ ] **Step 8: Crear `frontend/src/main.tsx`**

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import '@mantine/core/styles.css';
import '@mantine/dropzone/styles.css';
import '@mantine/notifications/styles.css';
import '@mantine/dates/styles.css';
import { theme } from './theme';
import { App } from './App';

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MantineProvider theme={theme}>
      <Notifications />
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </MantineProvider>
  </React.StrictMode>
);
```

- [ ] **Step 9: Crear `frontend/src/test/setup.ts`**

```ts
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(() => {
  cleanup();
});

// jsdom no implementa estas APIs que Mantine usa.
window.matchMedia ||= ((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {},
  removeListener: () => {},
  dispatchEvent: () => false,
})) as unknown as typeof window.matchMedia;

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver ||= ResizeObserverStub as unknown as typeof ResizeObserver;
```

- [ ] **Step 10: Crear `frontend/src/test/utils.tsx`** (render con providers)

```tsx
import { ReactElement, ReactNode } from 'react';
import { render } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { theme } from '../theme';

export function renderWithProviders(ui: ReactElement, { route = '/' } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MantineProvider theme={theme}>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
        </QueryClientProvider>
      </MantineProvider>
    );
  }
  return render(ui, { wrapper: Wrapper });
}
```

- [ ] **Step 11: Crear `frontend/.gitignore`**

```
node_modules
dist
*.local
```

- [ ] **Step 12: Instalar dependencias**

Run (desde `frontend/`): `npm install --no-audit --no-fund`
Expected: termina sin errores, crea `node_modules` y `package-lock.json`.

- [ ] **Step 13: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts frontend/index.html frontend/.gitignore frontend/src/main.tsx frontend/src/theme.ts frontend/src/App.tsx frontend/src/test/setup.ts frontend/src/test/utils.tsx
git commit -m "chore(frontend): scaffold Vite + React + Mantine + Vitest (teal)"
```

---

### Task 1: Formateo de dinero (`lib/money.ts`)

Función pura, primer ciclo TDD. Formatea un string decimal de la API a colones legibles (estilo CR: punto de miles, coma decimal).

**Files:**
- Create: `frontend/src/lib/money.ts`
- Test: `frontend/src/lib/money.test.ts`

- [ ] **Step 1: Escribir el test que falla**

```ts
import { describe, it, expect } from 'vitest';
import { formatColones } from './money';

describe('formatColones', () => {
  it('formatea con separador de miles y dos decimales', () => {
    expect(formatColones('34749173.64')).toBe('₡34.749.173,64');
  });
  it('agrega dos decimales a un entero', () => {
    expect(formatColones('1824800')).toBe('₡1.824.800,00');
  });
  it('formatea cero', () => {
    expect(formatColones('0')).toBe('₡0,00');
  });
  it('devuelve guion para valores vacíos o no numéricos', () => {
    expect(formatColones('')).toBe('—');
    expect(formatColones('abc')).toBe('—');
  });
});
```

- [ ] **Step 2: Correr y verificar que falla**

Run (desde `frontend/`): `npm test -- money`
Expected: FAIL — `formatColones` no existe / módulo no encontrado.

- [ ] **Step 3: Implementación mínima**

```ts
// Formatea un string decimal (proveniente de la API, donde el dinero es Decimal→str)
// a colones legibles. SOLO para mostrar: nunca usar el número para aritmética.
const fmt = new Intl.NumberFormat('es-CR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatColones(value: string): string {
  if (value === undefined || value === null || value.trim() === '') return '—';
  const n = Number(value);
  if (Number.isNaN(n)) return '—';
  return `₡${fmt.format(n)}`;
}
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `npm test -- money`
Expected: PASS (4 tests).

> Nota: `Intl` con locale `es-CR` produce `1.234,56`. Si el entorno de CI no trae ese locale, el test fallaría; Node 22 incluye ICU completo, así que pasa. Si fallara, fijar el separador a mano.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/money.ts frontend/src/lib/money.test.ts
git commit -m "feat(frontend): formato de colones (string Decimal → CR, display-only)"
```

---

### Task 2: Wrapper de API (`api/client.ts`)

Único módulo que conoce HTTP. Adjunta el token, parsea JSON, lanza `ApiError` tipado en ≥400. Maneja `FormData` (multipart) y form-urlencoded (login).

**Files:**
- Create: `frontend/src/api/client.ts`
- Test: `frontend/src/api/client.test.ts`

- [ ] **Step 1: Escribir el test que falla**

```ts
import { describe, it, expect, beforeEach, afterAll, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { apiFetch, ApiError, setToken, getToken, clearToken } from './client';

const server = setupServer();
beforeEach(() => { clearToken(); server.resetHandlers(); });
server.listen ? null : null; // (placeholder; real listen abajo)

describe('apiFetch', () => {
  it('parsea JSON en 200', async () => {
    server.use(http.get('/api/cosa', () => HttpResponse.json({ ok: true })));
    server.listen();
    const data = await apiFetch<{ ok: boolean }>('/api/cosa');
    expect(data).toEqual({ ok: true });
    server.close();
  });

  it('adjunta el Authorization Bearer cuando hay token', async () => {
    let recibido = '';
    server.use(http.get('/api/cosa', ({ request }) => {
      recibido = request.headers.get('Authorization') ?? '';
      return HttpResponse.json({});
    }));
    server.listen();
    setToken('abc123');
    await apiFetch('/api/cosa');
    expect(recibido).toBe('Bearer abc123');
    server.close();
  });

  it('lanza ApiError con status y detalle en 422', async () => {
    server.use(http.post('/api/x', () =>
      HttpResponse.json({ detail: 'XML inválido' }, { status: 422 })));
    server.listen();
    await expect(apiFetch('/api/x', { method: 'POST' }))
      .rejects.toMatchObject({ status: 422, detail: 'XML inválido' });
    server.close();
  });
});
```

> Nota para el implementador: el patrón canónico es `setupServer()` + `beforeAll(server.listen)` / `afterAll(server.close)` / `afterEach(server.resetHandlers)`. Reescribir el andamiaje del test a ese patrón si resulta más limpio; lo que importa son las tres aserciones (parseo, header, ApiError).

- [ ] **Step 2: Correr y verificar que falla**

Run: `npm test -- client`
Expected: FAIL — `./client` no existe.

- [ ] **Step 3: Implementación**

```ts
const TOKEN_KEY = 'sxml_token';

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  // No fijar Content-Type para FormData (el browser pone el boundary).
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body && typeof body.detail === 'string') detail = body.detail;
    } catch {
      // respuesta sin cuerpo JSON
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `npm test -- client`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/client.test.ts
git commit -m "feat(frontend): wrapper fetch tipado con ApiError y token (api/client)"
```

---

### Task 3: Auth (`auth/AuthContext`, `LoginPage`, `RequireAuth`)

**Files:**
- Create: `frontend/src/auth/AuthContext.tsx`, `frontend/src/auth/LoginPage.tsx`, `frontend/src/auth/RequireAuth.tsx`
- Test: `frontend/src/auth/LoginPage.test.tsx`

- [ ] **Step 1: Crear `AuthContext.tsx`**

```tsx
import { createContext, useContext, useState, ReactNode } from 'react';
import { apiFetch, setToken, clearToken, getToken } from '../api/client';

interface AuthState {
  isAuthenticated: boolean;
  login: (usuario: string, clave: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

interface TokenResponse { access_token: string }

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTok] = useState<string | null>(() => getToken());

  async function login(usuario: string, clave: string) {
    const body = new URLSearchParams({ username: usuario, password: clave });
    // OAuth2 password flow: form-urlencoded, sin Bearer.
    const data = await apiFetch<TokenResponse>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    setToken(data.access_token);
    setTok(data.access_token);
  }

  function logout() {
    clearToken();
    setTok(null);
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth fuera de AuthProvider');
  return ctx;
}
```

- [ ] **Step 2: Crear `RequireAuth.tsx`**

```tsx
import { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './AuthContext';

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
```

- [ ] **Step 3: Crear `LoginPage.tsx`**

```tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextInput, PasswordInput, Button, Paper, Title, Stack, Alert } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useAuth } from './AuthContext';
import { ApiError } from '../api/client';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const form = useForm({ initialValues: { usuario: '', clave: '' } });

  async function onSubmit(values: { usuario: string; clave: string }) {
    setError(null);
    try {
      await login(values.usuario, values.clave);
      navigate('/clientes');
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Error de conexión');
    }
  }

  return (
    <Paper maw={360} mx="auto" mt={120} p="xl" withBorder>
      <Title order={2} mb="md">Sistema XML</Title>
      <form onSubmit={form.onSubmit(onSubmit)}>
        <Stack>
          {error && <Alert color="red">{error}</Alert>}
          <TextInput label="Usuario" {...form.getInputProps('usuario')} />
          <PasswordInput label="Contraseña" {...form.getInputProps('clave')} />
          <Button type="submit">Ingresar</Button>
        </Stack>
      </form>
    </Paper>
  );
}
```

- [ ] **Step 4: Escribir el test que falla** (`LoginPage.test.tsx`)

```tsx
import { describe, it, expect, beforeAll, afterAll, afterEach, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/utils';
import { AuthProvider } from './AuthContext';
import { LoginPage } from './LoginPage';
import { getToken, clearToken } from '../api/client';

const server = setupServer();
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());
beforeEach(() => clearToken());

it('guarda el token tras un login exitoso', async () => {
  server.use(http.post('/auth/login', () =>
    HttpResponse.json({ access_token: 'tok-1', token_type: 'bearer' })));
  renderWithProviders(<AuthProvider><LoginPage /></AuthProvider>);
  await userEvent.type(screen.getByLabelText('Usuario'), 'admin');
  await userEvent.type(screen.getByLabelText('Contraseña'), 'secreto');
  await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }));
  await waitFor(() => expect(getToken()).toBe('tok-1'));
});

it('muestra el detalle de error en 401', async () => {
  server.use(http.post('/auth/login', () =>
    HttpResponse.json({ detail: 'Usuario o contraseña incorrectos' }, { status: 401 })));
  renderWithProviders(<AuthProvider><LoginPage /></AuthProvider>);
  await userEvent.type(screen.getByLabelText('Usuario'), 'x');
  await userEvent.type(screen.getByLabelText('Contraseña'), 'y');
  await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }));
  expect(await screen.findByText('Usuario o contraseña incorrectos')).toBeInTheDocument();
});
```

- [ ] **Step 5: Correr y verificar que falla, luego pasa**

Run: `npm test -- LoginPage`
Expected: primero FALLA si algún import no existe; tras crear los tres archivos, PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/auth/
git commit -m "feat(frontend): auth JWT (AuthContext + LoginPage + RequireAuth)"
```

---

### Task 4: Contexto de selección (`context/SeleccionContext.tsx`)

Estado global cliente/período/rol que consumen Subida, Resumen y D-150.

**Files:**
- Create: `frontend/src/context/SeleccionContext.tsx`
- Test: `frontend/src/context/SeleccionContext.test.tsx`

- [ ] **Step 1: Escribir el test que falla**

```tsx
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { SeleccionProvider, useSeleccion } from './SeleccionContext';

it('default rol = compra y permite cambiar la selección', () => {
  const { result } = renderHook(() => useSeleccion(), { wrapper: SeleccionProvider });
  expect(result.current.rol).toBe('compra');
  expect(result.current.clienteId).toBeNull();
  act(() => {
    result.current.setClienteId(5);
    result.current.setPeriodo('2026-05');
    result.current.setRol('venta');
  });
  expect(result.current.clienteId).toBe(5);
  expect(result.current.periodo).toBe('2026-05');
  expect(result.current.rol).toBe('venta');
});
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `npm test -- SeleccionContext`
Expected: FAIL — módulo no existe.

- [ ] **Step 3: Implementación**

```tsx
import { createContext, useContext, useState, ReactNode } from 'react';

export type Rol = 'compra' | 'venta';

interface SeleccionState {
  clienteId: number | null;
  periodo: string | null; // "YYYY-MM"
  rol: Rol;
  setClienteId: (id: number | null) => void;
  setPeriodo: (p: string | null) => void;
  setRol: (r: Rol) => void;
}

const SeleccionContext = createContext<SeleccionState | null>(null);

export function SeleccionProvider({ children }: { children: ReactNode }) {
  const [clienteId, setClienteId] = useState<number | null>(null);
  const [periodo, setPeriodo] = useState<string | null>(null);
  const [rol, setRol] = useState<Rol>('compra');
  return (
    <SeleccionContext.Provider
      value={{ clienteId, periodo, rol, setClienteId, setPeriodo, setRol }}
    >
      {children}
    </SeleccionContext.Provider>
  );
}

export function useSeleccion(): SeleccionState {
  const ctx = useContext(SeleccionContext);
  if (!ctx) throw new Error('useSeleccion fuera de SeleccionProvider');
  return ctx;
}
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `npm test -- SeleccionContext`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/context/
git commit -m "feat(frontend): SeleccionContext (cliente/período/rol global)"
```

---

### Task 5: Hooks de API (`api/hooks.ts`)

Hooks TanStack por endpoint. Tipos compartidos con las páginas.

**Files:**
- Create: `frontend/src/api/hooks.ts`
- Test: `frontend/src/api/hooks.test.tsx`

- [ ] **Step 1: Escribir el test que falla**

```tsx
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { renderHook, waitFor } from '@testing-library/react';
import { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useClientes, useResumen } from './hooks';

const server = setupServer();
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

it('useClientes devuelve la lista', async () => {
  server.use(http.get('/api/clientes', () =>
    HttpResponse.json([{ id: 1, nombre: 'Agrofinca', cedula: '3101', tipo_cedula: 'juridica', regimen: 'tradicional' }])));
  const { result } = renderHook(() => useClientes(), { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.[0].nombre).toBe('Agrofinca');
});

it('useResumen pasa cliente/periodo/rol como query params', async () => {
  let url = '';
  server.use(http.get('/api/resumen', ({ request }) => {
    url = new URL(request.url).search;
    return HttpResponse.json({ Bienes: { base: '100', iva: '13' } });
  }));
  const { result } = renderHook(() => useResumen(1, '2026-05', 'compra'), { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(url).toContain('cliente_id=1');
  expect(url).toContain('periodo=2026-05');
  expect(url).toContain('rol=compra');
});
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `npm test -- hooks`
Expected: FAIL — `./hooks` no existe.

- [ ] **Step 3: Implementación**

```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from './client';
import type { Rol } from '../context/SeleccionContext';

export interface Cliente {
  id: number;
  nombre: string;
  cedula: string;
  tipo_cedula: string;
  regimen: string;
}
export interface ClienteCreate {
  nombre: string;
  cedula: string;
  tipo_cedula: string;
  regimen: string;
}

// resumen por categoría: { categoria: { base, iva } }
export type Resumen = Record<string, { base: string; iva: string }>;
// por clasificación: { clasificacion: { tasa: { base, iva } } }
export type ResumenClasificacion = Record<string, Record<string, { base: string; iva: string }>>;

export interface D150Response {
  preciso: Record<string, unknown>;
  ovi: Record<string, unknown>;
}

export interface ResultadoArchivo {
  archivo: string;
  estado: 'nuevo' | 'actualizado' | 'omitido' | 'error';
  detalle?: string;
}

const qs = (params: Record<string, string | number>) =>
  '?' + new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)])
  ).toString();

export function useClientes() {
  return useQuery({
    queryKey: ['clientes'],
    queryFn: () => apiFetch<Cliente[]>('/api/clientes'),
  });
}

export function useCrearCliente() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ClienteCreate) =>
      apiFetch<Cliente>('/api/clientes', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['clientes'] }),
  });
}

export function useResumen(clienteId: number | null, periodo: string | null, rol: Rol) {
  return useQuery({
    queryKey: ['resumen', clienteId, periodo, rol],
    enabled: clienteId != null && periodo != null,
    queryFn: () =>
      apiFetch<Resumen>('/api/resumen' + qs({ cliente_id: clienteId!, periodo: periodo!, rol })),
  });
}

export function useResumenClasificacion(clienteId: number | null, periodo: string | null, rol: Rol) {
  return useQuery({
    queryKey: ['resumen-clasificacion', clienteId, periodo, rol],
    enabled: clienteId != null && periodo != null,
    queryFn: () =>
      apiFetch<ResumenClasificacion>(
        '/api/resumen/clasificacion' + qs({ cliente_id: clienteId!, periodo: periodo!, rol })),
  });
}

export function useD150(clienteId: number | null, periodo: string | null) {
  return useQuery({
    queryKey: ['d150', clienteId, periodo],
    enabled: clienteId != null && periodo != null,
    queryFn: () =>
      apiFetch<D150Response>('/api/d150' + qs({ cliente_id: clienteId!, periodo: periodo! })),
  });
}

export function useIngestaLote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (archivos: File[]) => {
      const fd = new FormData();
      for (const f of archivos) fd.append('archivos', f);
      return apiFetch<ResultadoArchivo[]>('/api/ingesta/lote', { method: 'POST', body: fd });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['resumen'] });
      qc.invalidateQueries({ queryKey: ['resumen-clasificacion'] });
      qc.invalidateQueries({ queryKey: ['d150'] });
    },
  });
}
```

> Nota: confirmar contra el backend la forma exacta de la respuesta de `/api/ingesta/lote` (`motor/ingesta_lote.py`) y ajustar `ResultadoArchivo` si difiere. La página de Subida (Task 8) renderiza estos campos.

- [ ] **Step 4: Correr y verificar que pasa**

Run: `npm test -- hooks`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/hooks.ts frontend/src/api/hooks.test.tsx
git commit -m "feat(frontend): hooks TanStack por endpoint (api/hooks)"
```

---

### Task 6: AppShell + ruteo (`components/AppShell.tsx`, `App.tsx`)

Sidebar + barra de contexto global, y cableado de rutas con `RequireAuth`.

**Files:**
- Create: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/App.tsx` (reemplaza el placeholder de Task 0)
- Modify: `frontend/src/main.tsx` (envolver con `AuthProvider` + `SeleccionProvider`)
- Test: `frontend/src/components/AppShell.test.tsx`

- [ ] **Step 1: Crear `components/AppShell.tsx`**

```tsx
import { ReactNode } from 'react';
import { AppShell as MantineAppShell, NavLink, Group, Select, SegmentedControl, Text, Button } from '@mantine/core';
import { MonthPickerInput } from '@mantine/dates';
import { NavLink as RouterNavLink, useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import { useSeleccion, Rol } from '../context/SeleccionContext';
import { useClientes } from '../api/hooks';
import { useAuth } from '../auth/AuthContext';

const LINKS = [
  { to: '/clientes', label: 'Clientes' },
  { to: '/subida', label: 'Subida XML' },
  { to: '/resumen', label: 'Resumen' },
  { to: '/d150', label: 'D-150' },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { clienteId, periodo, rol, setClienteId, setPeriodo, setRol } = useSeleccion();
  const { data: clientes } = useClientes();
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <MantineAppShell header={{ height: 60 }} navbar={{ width: 200, breakpoint: 'sm' }} padding="md">
      <MantineAppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Text fw={700} c="teal">Sistema XML</Text>
          <Group>
            <Select
              placeholder="Cliente"
              data={(clientes ?? []).map((c) => ({ value: String(c.id), label: c.nombre }))}
              value={clienteId != null ? String(clienteId) : null}
              onChange={(v) => setClienteId(v ? Number(v) : null)}
              w={200}
            />
            <MonthPickerInput
              placeholder="Período"
              value={periodo ? dayjs(periodo + '-01').toDate() : null}
              onChange={(d) => setPeriodo(d ? dayjs(d).format('YYYY-MM') : null)}
              w={140}
            />
            <SegmentedControl
              value={rol}
              onChange={(v) => setRol(v as Rol)}
              data={[{ value: 'compra', label: 'Compra' }, { value: 'venta', label: 'Venta' }]}
            />
            <Button variant="subtle" onClick={() => { logout(); navigate('/login'); }}>Salir</Button>
          </Group>
        </Group>
      </MantineAppShell.Header>
      <MantineAppShell.Navbar p="xs">
        {LINKS.map((l) => (
          <NavLink key={l.to} component={RouterNavLink} to={l.to} label={l.label} />
        ))}
      </MantineAppShell.Navbar>
      <MantineAppShell.Main>{children}</MantineAppShell.Main>
    </MantineAppShell>
  );
}
```

- [ ] **Step 2: Reemplazar `App.tsx`**

```tsx
import { Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from './auth/LoginPage';
import { RequireAuth } from './auth/RequireAuth';
import { AppShell } from './components/AppShell';
import { ClientesPage } from './pages/ClientesPage';
import { SubidaPage } from './pages/SubidaPage';
import { ResumenPage } from './pages/ResumenPage';
import { D150Page } from './pages/D150Page';

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <AppShell>
              <Routes>
                <Route path="/clientes" element={<ClientesPage />} />
                <Route path="/subida" element={<SubidaPage />} />
                <Route path="/resumen" element={<ResumenPage />} />
                <Route path="/d150" element={<D150Page />} />
                <Route path="*" element={<Navigate to="/clientes" replace />} />
              </Routes>
            </AppShell>
          </RequireAuth>
        }
      />
    </Routes>
  );
}
```

> Nota: las páginas `ClientesPage`/`SubidaPage`/`ResumenPage`/`D150Page` se crean en Tasks 7-10. Para que `App.tsx` compile en esta tarea, crear primero stubs mínimos de cada una (`export function XPage() { return <div/>; }`) y completarlas en sus tasks. Alternativa: implementar Task 6 después de 7-10. El orden recomendado para subagentes es 7→10 y luego 6; si se hace 6 antes, dejar los stubs.

- [ ] **Step 3: Actualizar `main.tsx`** — envolver `<App/>` con los providers de auth y selección.

Reemplazar el bloque `<BrowserRouter><App /></BrowserRouter>` por:

```tsx
import { AuthProvider } from './auth/AuthContext';
import { SeleccionProvider } from './context/SeleccionContext';
// ...
        <BrowserRouter>
          <AuthProvider>
            <SeleccionProvider>
              <App />
            </SeleccionProvider>
          </AuthProvider>
        </BrowserRouter>
```

- [ ] **Step 4: Escribir el test** (`AppShell.test.tsx`)

```tsx
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../test/utils';
import { AuthProvider } from '../auth/AuthContext';
import { SeleccionProvider } from '../context/SeleccionContext';
import { AppShell } from './AppShell';

const server = setupServer(
  http.get('/api/clientes', () =>
    HttpResponse.json([{ id: 1, nombre: 'Agrofinca', cedula: '3101', tipo_cedula: 'juridica', regimen: 'tradicional' }]))
);
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

it('muestra los enlaces de navegación y el cliente en el selector', async () => {
  renderWithProviders(
    <AuthProvider><SeleccionProvider><AppShell><div>contenido</div></AppShell></SeleccionProvider></AuthProvider>
  );
  expect(screen.getByText('Clientes')).toBeInTheDocument();
  expect(screen.getByText('D-150')).toBeInTheDocument();
  expect(screen.getByText('contenido')).toBeInTheDocument();
  await waitFor(() => expect(screen.getByPlaceholderText('Cliente')).toBeInTheDocument());
});
```

- [ ] **Step 5: Correr y verificar que pasa**

Run: `npm test -- AppShell`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ frontend/src/App.tsx frontend/src/main.tsx
git commit -m "feat(frontend): AppShell (sidebar + barra de contexto) y ruteo con RequireAuth"
```

---

### Task 7: Página de Clientes (`pages/ClientesPage.tsx`)

Tabla de clientes + modal de alta. Maneja 409 (cédula duplicada) inline.

**Files:**
- Create: `frontend/src/pages/ClientesPage.tsx`
- Test: `frontend/src/pages/ClientesPage.test.tsx`

- [ ] **Step 1: Implementar `ClientesPage.tsx`**

```tsx
import { useState } from 'react';
import { Table, Button, Modal, TextInput, Select, Stack, Group, Title, Alert, Loader } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useClientes, useCrearCliente, ClienteCreate } from '../api/hooks';
import { ApiError } from '../api/client';

export function ClientesPage() {
  const { data: clientes, isLoading, isError, refetch } = useClientes();
  const crear = useCrearCliente();
  const [abierto, setAbierto] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<ClienteCreate>({
    initialValues: { nombre: '', cedula: '', tipo_cedula: 'juridica', regimen: 'tradicional' },
  });

  async function onSubmit(values: ClienteCreate) {
    setError(null);
    try {
      await crear.mutateAsync(values);
      setAbierto(false);
      form.reset();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Error de conexión');
    }
  }

  if (isLoading) return <Loader />;
  if (isError) return <Alert color="red">Error al cargar clientes <Button onClick={() => refetch()}>Reintentar</Button></Alert>;

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Clientes</Title>
        <Button onClick={() => setAbierto(true)}>Nuevo cliente</Button>
      </Group>
      <Table striped>
        <Table.Thead>
          <Table.Tr><Table.Th>Nombre</Table.Th><Table.Th>Cédula</Table.Th><Table.Th>Régimen</Table.Th></Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {(clientes ?? []).map((c) => (
            <Table.Tr key={c.id}>
              <Table.Td>{c.nombre}</Table.Td><Table.Td>{c.cedula}</Table.Td><Table.Td>{c.regimen}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Modal opened={abierto} onClose={() => setAbierto(false)} title="Nuevo cliente">
        <form onSubmit={form.onSubmit(onSubmit)}>
          <Stack>
            {error && <Alert color="red">{error}</Alert>}
            <TextInput label="Nombre" required {...form.getInputProps('nombre')} />
            <TextInput label="Cédula" required {...form.getInputProps('cedula')} />
            <Select label="Tipo de cédula" data={['fisica', 'juridica']} {...form.getInputProps('tipo_cedula')} />
            <Select label="Régimen" data={['tradicional', 'simplificado']} {...form.getInputProps('regimen')} />
            <Button type="submit" loading={crear.isPending}>Guardar</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
```

> Nota: confirmar los valores válidos de `tipo_cedula` y `regimen` contra `backend/app/schemas/cliente.py` y ajustar los `data` de los `Select`. (CLAUDE.md marca como pendiente validar estos dominios en el backend.)

- [ ] **Step 2: Escribir el test** (`ClientesPage.test.tsx`)

```tsx
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/utils';
import { ClientesPage } from './ClientesPage';

const server = setupServer();
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

it('lista clientes y muestra 409 inline al duplicar cédula', async () => {
  server.use(
    http.get('/api/clientes', () =>
      HttpResponse.json([{ id: 1, nombre: 'Agrofinca', cedula: '3101', tipo_cedula: 'juridica', regimen: 'tradicional' }])),
    http.post('/api/clientes', () =>
      HttpResponse.json({ detail: 'Ya existe un cliente con esa cédula' }, { status: 409 }))
  );
  renderWithProviders(<ClientesPage />);
  expect(await screen.findByText('Agrofinca')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Nuevo cliente' }));
  await userEvent.type(screen.getByLabelText('Nombre'), 'Otro');
  await userEvent.type(screen.getByLabelText('Cédula'), '3101');
  await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));
  expect(await screen.findByText('Ya existe un cliente con esa cédula')).toBeInTheDocument();
});
```

- [ ] **Step 3: Correr y verificar que falla, luego pasa**

Run: `npm test -- ClientesPage`
Expected: tras implementar, PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ClientesPage.tsx frontend/src/pages/ClientesPage.test.tsx
git commit -m "feat(frontend): página de clientes (tabla + alta, 409 inline)"
```

---

### Task 8: Página de Subida (`pages/SubidaPage.tsx`)

Dropzone XML/ZIP → `/api/ingesta/lote`; tabla de reporte por archivo.

**Files:**
- Create: `frontend/src/pages/SubidaPage.tsx`
- Test: `frontend/src/pages/SubidaPage.test.tsx`

- [ ] **Step 1: Implementar `SubidaPage.tsx`**

```tsx
import { useState } from 'react';
import { Stack, Title, Text, Table, Alert, Badge } from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import { notifications } from '@mantine/notifications';
import { useIngestaLote, ResultadoArchivo } from '../api/hooks';
import { ApiError } from '../api/client';

const COLOR: Record<ResultadoArchivo['estado'], string> = {
  nuevo: 'teal', actualizado: 'blue', omitido: 'gray', error: 'red',
};

export function SubidaPage() {
  const ingesta = useIngestaLote();
  const [resultados, setResultados] = useState<ResultadoArchivo[]>([]);

  async function onDrop(files: File[]) {
    try {
      const res = await ingesta.mutateAsync(files);
      setResultados(res);
      notifications.show({ message: `Procesados ${res.length} archivo(s)`, color: 'teal' });
    } catch (e) {
      notifications.show({
        color: 'red',
        message: e instanceof ApiError ? e.detail : 'Error al subir',
      });
    }
  }

  return (
    <Stack>
      <Title order={2}>Subir comprobantes</Title>
      <Dropzone onDrop={onDrop} loading={ingesta.isPending} accept={['text/xml', 'application/xml', 'application/zip']}>
        <Text ta="center" p="xl">Arrastrá archivos XML o ZIP, o hacé clic para elegir</Text>
      </Dropzone>
      {resultados.length > 0 && (
        <Table striped>
          <Table.Thead><Table.Tr><Table.Th>Archivo</Table.Th><Table.Th>Estado</Table.Th><Table.Th>Detalle</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {resultados.map((r) => (
              <Table.Tr key={r.archivo}>
                <Table.Td>{r.archivo}</Table.Td>
                <Table.Td><Badge color={COLOR[r.estado]}>{r.estado}</Badge></Table.Td>
                <Table.Td>{r.detalle ?? ''}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
```

> Nota crítica: la forma de `ResultadoArchivo` (campos `archivo`/`estado`/`detalle`) DEBE coincidir con lo que devuelve `motor/ingesta_lote.py`. Antes de implementar, leer ese módulo y ajustar el tipo en `api/hooks.ts` y este render. El test mockea la forma asumida; corregir ambos si el backend difiere.

- [ ] **Step 2: Escribir el test** (`SubidaPage.test.tsx`) — dispara `onDrop` directamente

```tsx
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../test/utils';
import { SubidaPage } from './SubidaPage';

const server = setupServer();
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

it('muestra el reporte por archivo tras subir', async () => {
  server.use(http.post('/api/ingesta/lote', () =>
    HttpResponse.json([
      { archivo: 'a.xml', estado: 'nuevo' },
      { archivo: 'b.xml', estado: 'error', detalle: 'XML inválido' },
    ])));
  renderWithProviders(<SubidaPage />);
  // Mantine Dropzone expone un input file oculto; subir vía ese input.
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const { default: userEvent } = await import('@testing-library/user-event');
  await userEvent.upload(input, [new File(['<xml/>'], 'a.xml', { type: 'text/xml' })]);
  expect(await screen.findByText('a.xml')).toBeInTheDocument();
  expect(await screen.findByText('XML inválido')).toBeInTheDocument();
});
```

> Nota: si `userEvent.upload` sobre el input del Dropzone no dispara `onDrop` de forma fiable en jsdom, refactorizar extrayendo la lógica a un componente que reciba `onDrop` y testear esa función directamente (`onDrop([file])`), que es lo que importa. No pelear con la simulación de drag.

- [ ] **Step 3: Correr y verificar que pasa**

Run: `npm test -- SubidaPage`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SubidaPage.tsx frontend/src/pages/SubidaPage.test.tsx
git commit -m "feat(frontend): página de subida (dropzone XML/ZIP + reporte por archivo)"
```

---

### Task 9: Página de Resumen (`pages/ResumenPage.tsx`)

Tabs Categoría / Clasificación, leyendo la selección global. Montos con `formatColones`.

**Files:**
- Create: `frontend/src/pages/ResumenPage.tsx`
- Test: `frontend/src/pages/ResumenPage.test.tsx`

- [ ] **Step 1: Implementar `ResumenPage.tsx`**

```tsx
import { Stack, Title, Tabs, Table, Alert, Loader, Text } from '@mantine/core';
import { useSeleccion } from '../context/SeleccionContext';
import { useResumen, useResumenClasificacion } from '../api/hooks';
import { formatColones } from '../lib/money';

function TablaCategoria({ clienteId, periodo, rol }: { clienteId: number | null; periodo: string | null; rol: 'compra' | 'venta' }) {
  const { data, isLoading, isError, refetch } = useResumen(clienteId, periodo, rol);
  if (isLoading) return <Loader />;
  if (isError) return <Alert color="red">Error <Text component="button" onClick={() => refetch()}>reintentar</Text></Alert>;
  return (
    <Table striped>
      <Table.Thead><Table.Tr><Table.Th>Categoría</Table.Th><Table.Th>Base</Table.Th><Table.Th>IVA</Table.Th></Table.Tr></Table.Thead>
      <Table.Tbody>
        {Object.entries(data ?? {}).map(([cat, v]) => (
          <Table.Tr key={cat}>
            <Table.Td>{cat}</Table.Td><Table.Td>{formatColones(v.base)}</Table.Td><Table.Td>{formatColones(v.iva)}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function TablaClasificacion({ clienteId, periodo, rol }: { clienteId: number | null; periodo: string | null; rol: 'compra' | 'venta' }) {
  const { data, isLoading } = useResumenClasificacion(clienteId, periodo, rol);
  if (isLoading) return <Loader />;
  return (
    <Table striped>
      <Table.Thead><Table.Tr><Table.Th>Clasificación</Table.Th><Table.Th>Tasa</Table.Th><Table.Th>Base</Table.Th><Table.Th>IVA</Table.Th></Table.Tr></Table.Thead>
      <Table.Tbody>
        {Object.entries(data ?? {}).flatMap(([clas, tasas]) =>
          Object.entries(tasas).map(([tasa, v]) => (
            <Table.Tr key={clas + tasa}>
              <Table.Td>{clas}</Table.Td><Table.Td>{tasa}</Table.Td>
              <Table.Td>{formatColones(v.base)}</Table.Td><Table.Td>{formatColones(v.iva)}</Table.Td>
            </Table.Tr>
          )))}
      </Table.Tbody>
    </Table>
  );
}

export function ResumenPage() {
  const { clienteId, periodo, rol } = useSeleccion();
  if (clienteId == null || periodo == null)
    return <Alert color="yellow">Elegí cliente y período en la barra superior.</Alert>;
  return (
    <Stack>
      <Title order={2}>Resumen</Title>
      <Tabs defaultValue="categoria">
        <Tabs.List>
          <Tabs.Tab value="categoria">Categoría</Tabs.Tab>
          <Tabs.Tab value="clasificacion">Clasificación</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="categoria" pt="md"><TablaCategoria clienteId={clienteId} periodo={periodo} rol={rol} /></Tabs.Panel>
        <Tabs.Panel value="clasificacion" pt="md"><TablaClasificacion clienteId={clienteId} periodo={periodo} rol={rol} /></Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
```

- [ ] **Step 2: Escribir el test** — provider de selección con valores fijos

```tsx
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen, act } from '@testing-library/react';
import { renderWithProviders } from '../test/utils';
import { SeleccionProvider, useSeleccion } from '../context/SeleccionContext';
import { ResumenPage } from './ResumenPage';

const server = setupServer(
  http.get('/api/resumen', () => HttpResponse.json({ Bienes: { base: '34749173.64', iva: '347491.74' } }))
);
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

function Fijar() {
  const s = useSeleccion();
  if (s.clienteId == null) { s.setClienteId(1); s.setPeriodo('2026-05'); }
  return null;
}

it('muestra montos formateados en colones', async () => {
  renderWithProviders(<SeleccionProvider><Fijar /><ResumenPage /></SeleccionProvider>);
  expect(await screen.findByText('₡34.749.173,64')).toBeInTheDocument();
});
```

> Nota: si fijar el contexto vía un componente hijo causa warnings de render, alternativa: exponer un `initial` opcional en `SeleccionProvider` (`{ clienteId, periodo }`) usado solo en tests, o envolver `setClienteId` en `useEffect`. Elegir lo más limpio; la aserción (monto formateado) es lo que importa.

- [ ] **Step 3: Correr y verificar que pasa**

Run: `npm test -- ResumenPage`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ResumenPage.tsx frontend/src/pages/ResumenPage.test.tsx
git commit -m "feat(frontend): página de resumen (tabs categoría/clasificación, colones)"
```

---

### Task 10: Página D-150 (`pages/D150Page.tsx`)

Muestra el D-150 con toggle preciso ↔ OVI (entero). La forma exacta de `preciso`/`ovi` sale de `motor/d150.py` (`jsonify_preciso` / `d150_ovi`).

**Files:**
- Create: `frontend/src/pages/D150Page.tsx`
- Test: `frontend/src/pages/D150Page.test.tsx`

- [ ] **Step 0: Leer el backend para fijar la forma**

Leer `backend/app/motor/d150.py` (funciones `build_d150`, `jsonify_preciso`, `d150_ovi`) para conocer las claves exactas del objeto `preciso` y `ovi`. El render abajo asume un diccionario plano `clave → valor string`. Ajustar si la estructura es anidada.

- [ ] **Step 1: Implementar `D150Page.tsx`**

```tsx
import { useState } from 'react';
import { Stack, Title, Table, SegmentedControl, Alert, Loader } from '@mantine/core';
import { useSeleccion } from '../context/SeleccionContext';
import { useD150 } from '../api/hooks';
import { formatColones } from '../lib/money';

export function D150Page() {
  const { clienteId, periodo } = useSeleccion();
  const { data, isLoading, isError, refetch } = useD150(clienteId, periodo);
  const [vista, setVista] = useState<'preciso' | 'ovi'>('preciso');

  if (clienteId == null || periodo == null)
    return <Alert color="yellow">Elegí cliente y período en la barra superior.</Alert>;
  if (isLoading) return <Loader />;
  if (isError) return <Alert color="red">Error al cargar el D-150 <button onClick={() => refetch()}>reintentar</button></Alert>;

  const obj = (vista === 'preciso' ? data?.preciso : data?.ovi) ?? {};
  return (
    <Stack>
      <Title order={2}>D-150</Title>
      <SegmentedControl
        value={vista}
        onChange={(v) => setVista(v as 'preciso' | 'ovi')}
        data={[{ value: 'preciso', label: 'Preciso' }, { value: 'ovi', label: 'OVI (entero)' }]}
      />
      <Table striped>
        <Table.Thead><Table.Tr><Table.Th>Renglón</Table.Th><Table.Th>Monto</Table.Th></Table.Tr></Table.Thead>
        <Table.Tbody>
          {Object.entries(obj).map(([k, v]) => (
            <Table.Tr key={k}>
              <Table.Td>{k}</Table.Td>
              <Table.Td>{vista === 'preciso' ? formatColones(String(v)) : String(v)}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}
```

> Nota: en la vista OVI los valores son enteros (string o number) y se muestran tal cual (sin `formatColones`, que agrega decimales). En la vista preciso son strings Decimal y se formatean. Si `jsonify_preciso` devuelve una estructura anidada, aplanar antes de renderizar.

- [ ] **Step 2: Escribir el test**

```tsx
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../test/utils';
import { SeleccionProvider, useSeleccion } from '../context/SeleccionContext';
import { D150Page } from './D150Page';

const server = setupServer(
  http.get('/api/d150', () => HttpResponse.json({
    preciso: { debito: '584715.74', credito: '0.00', liquidacion: '584715.74' },
    ovi: { debito: '584716', credito: '0', liquidacion: '584716' },
  }))
);
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

function Fijar() {
  const s = useSeleccion();
  if (s.clienteId == null) { s.setClienteId(1); s.setPeriodo('2026-05'); }
  return null;
}

it('muestra el D-150 preciso formateado en colones', async () => {
  renderWithProviders(<SeleccionProvider><Fijar /><D150Page /></SeleccionProvider>);
  expect(await screen.findByText('₡584.715,74')).toBeInTheDocument();
});
```

- [ ] **Step 3: Correr y verificar que pasa**

Run: `npm test -- D150Page`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/D150Page.tsx frontend/src/pages/D150Page.test.tsx
git commit -m "feat(frontend): página D-150 (toggle preciso/OVI, colones)"
```

---

### Task 11: Verificación final

- [ ] **Step 1: Correr toda la suite**

Run (desde `frontend/`): `npm test`
Expected: todos los archivos de test en verde.

- [ ] **Step 2: Type-check / build**

Run: `npm run build`
Expected: `tsc -b` sin errores y build de Vite exitoso. Corregir cualquier error de tipos (imports no usados fallan por `noUnusedLocals`).

- [ ] **Step 3: Humo manual (opcional, requiere backend corriendo)**

Con el backend en `:8000` (`uvicorn app.main:app --reload`), correr `npm run dev`, entrar a `http://localhost:5173`, hacer login, listar clientes, subir un XML de prueba y ver resumen/D-150. Validación visual con mockups según preferencia del usuario.

- [ ] **Step 4: Commit final si quedaron ajustes**

```bash
git add -A
git commit -m "chore(frontend): ajustes finales de tipos y verificación de la suite"
```

---

## Self-Review (cobertura del spec)

- Login (`/auth/login` form OAuth2) → Task 3. ✔
- Clientes (GET/POST, 409 inline) → Task 7. ✔
- Subida lote (multipart, reporte por archivo) → Tasks 5 + 8. ✔
- Resumen categoría + clasificación → Tasks 5 + 9. ✔
- D-150 (preciso + OVI) → Tasks 5 + 10. ✔
- Sidebar + barra de contexto global (cliente/período/rol) → Tasks 4 + 6. ✔
- Wrapper `fetch` tipado con ApiError + token → Task 2. ✔
- Dinero como string formateado (nunca float) → Task 1, usado en 9 y 10. ✔
- Manejo de errores 401/422/409/red → 2 (ApiError), 3 (401 login), 7 (409), 8 (422/notif), 9/10 (reintentar). ✔
- Teal en un solo lugar → Task 0 (`theme.ts`). ✔
- Vitest + RTL + MSW → Task 0 (setup) + tests por tarea. ✔
- Proxy Vite `/api` y `/auth` → Task 0 (`vite.config.ts`). ✔
- Diferidos (reglas/CABYS/entradas-manuales/tokens/reportes) → fuera del plan, por diseño. ✔

**Riesgos conocidos marcados como notas en el plan:** forma exacta de la respuesta de `ingesta_lote` (Tasks 5/8) y estructura de `jsonify_preciso`/`d150_ovi` (Task 10) deben confirmarse leyendo el backend antes de implementar esas tareas; dominios de `tipo_cedula`/`regimen` en Task 7.
