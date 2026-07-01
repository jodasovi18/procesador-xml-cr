import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../test/utils';
import { AuthProvider } from '../auth/AuthContext';
import { SeleccionProvider } from '../context/SeleccionContext';
import { AppShell } from './AppShell';
import { setToken, clearToken } from '../api/client';

const server = setupServer(
  http.get('*/api/clientes', () =>
    HttpResponse.json([{ id: 1, nombre: 'Agrofinca', cedula: '3101', tipo_cedula: 'juridica', regimen: 'tradicional' }]))
);
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => { server.resetHandlers(); clearToken(); });

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
  await screen.findByText('Clientes');
  expect(screen.queryByRole('link', { name: 'Tokens de agente' })).not.toBeInTheDocument();
});

it('muestra los enlaces de navegación, el contenido y el selector de cliente', async () => {
  renderWithProviders(
    <AuthProvider><SeleccionProvider><AppShell><div>contenido</div></AppShell></SeleccionProvider></AuthProvider>
  );
  expect(screen.getByRole('link', { name: 'Clientes' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Subida XML' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Resumen' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'D-150' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Reglas' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Preclasificar' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Entradas manuales' })).toBeInTheDocument();
  expect(screen.getByText('contenido')).toBeInTheDocument();
  await waitFor(() => expect(screen.getByPlaceholderText('Cliente')).toBeInTheDocument());
});
