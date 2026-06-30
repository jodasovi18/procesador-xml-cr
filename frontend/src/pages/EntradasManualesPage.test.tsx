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
  // monto aparece tanto en la fila como en el footer (tfoot); getAllByText confirma ambas presencias
  expect(screen.getAllByText('₡2.450.000,00')).toHaveLength(2);
  expect(screen.getAllByText('₡24.500,00')).toHaveLength(2);
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
