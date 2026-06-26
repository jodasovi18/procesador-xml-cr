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
    http.get('*/api/clientes', () =>
      HttpResponse.json([{ id: 1, nombre: 'Agrofinca', cedula: '3101', tipo_cedula: 'juridica', regimen: 'tradicional' }])),
    http.post('*/api/clientes', () =>
      HttpResponse.json({ detail: 'Ya existe un cliente con esa cédula' }, { status: 409 }))
  );
  renderWithProviders(<ClientesPage />);
  expect(await screen.findByText('Agrofinca')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Nuevo cliente' }));
  // Wait for modal inputs to appear (Mantine portal + env=test renders synchronously after state update)
  const nombreInput = await waitFor(() => {
    const el = document.getElementById('cliente-nombre') as HTMLInputElement;
    if (!el) throw new Error('cliente-nombre input not found');
    return el;
  });
  const cedulaInput = document.getElementById('cliente-cedula') as HTMLInputElement | null;
  if (!cedulaInput) throw new Error('cliente-cedula input no encontrado');
  await userEvent.type(nombreInput, 'Otro');
  await userEvent.type(cedulaInput, '3101');
  await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));
  expect(await screen.findByText('Ya existe un cliente con esa cédula')).toBeInTheDocument();
});
