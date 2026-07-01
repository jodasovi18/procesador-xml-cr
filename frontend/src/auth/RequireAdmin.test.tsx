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
