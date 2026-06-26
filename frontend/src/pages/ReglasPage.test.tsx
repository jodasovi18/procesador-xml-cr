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
  const dialog = await screen.findByRole('dialog');
  await userEvent.click(within(dialog).getByRole('button', { name: 'Eliminar' }));
  await waitFor(() => expect(delId).toBe('5'));
});

it('muestra 422 inline en el modal', async () => {
  server.use(http.post('*/api/reglas', () =>
    HttpResponse.json({ detail: 'clasificacion inválida' }, { status: 422 })));
  renderWithProviders(conCliente(<ReglasPage />));
  await userEvent.click(await screen.findByRole('button', { name: 'Nueva regla' }));
  const dialog = await screen.findByRole('dialog');
  const cedulaInput = within(dialog).getByLabelText('Cédula');
  await userEvent.type(cedulaInput, '3101');
  await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }));
  expect(await screen.findByText('clasificacion inválida')).toBeInTheDocument();
});
