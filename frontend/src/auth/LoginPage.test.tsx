import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/utils';
import { AuthProvider } from './AuthContext';
import { LoginPage } from './LoginPage';
import { getToken, clearToken } from '../api/client';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterAll(() => server.close());
afterEach(() => { server.resetHandlers(); clearToken(); });

it('guarda el token tras un login exitoso', async () => {
  server.use(http.post('*/auth/login', () =>
    HttpResponse.json({ access_token: 'tok-1', token_type: 'bearer' })));
  renderWithProviders(<AuthProvider><LoginPage /></AuthProvider>);
  await userEvent.type(screen.getByLabelText('Usuario'), 'admin');
  await userEvent.type(screen.getByLabelText(/contraseña/i), 'secreto');
  await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }));
  await waitFor(() => expect(getToken()).toBe('tok-1'));
});

it('muestra el detalle de error en 401', async () => {
  server.use(http.post('*/auth/login', () =>
    HttpResponse.json({ detail: 'Usuario o contraseña incorrectos' }, { status: 401 })));
  renderWithProviders(<AuthProvider><LoginPage /></AuthProvider>);
  await userEvent.type(screen.getByLabelText('Usuario'), 'x');
  await userEvent.type(screen.getByLabelText(/contraseña/i), 'y');
  await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }));
  expect(await screen.findByText('Usuario o contraseña incorrectos')).toBeInTheDocument();
});
