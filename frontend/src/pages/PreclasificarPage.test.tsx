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
  await userEvent.click(screen.getAllByLabelText('Clasificación 3420100')[0]);
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
  await userEvent.click(screen.getAllByLabelText('Clasificación 3101030042')[0]);
  await userEvent.click(await screen.findByRole('option', { name: 'Compras' }));
  await userEvent.click(screen.getByRole('button', { name: 'Guardar asignaciones' }));
  await waitFor(() => expect(body).toMatchObject({ cedula: '3101030042', clasificacion: 'Compras', rol: 'compra' }));
});

it('conserva la fila que falló al guardar (fallo parcial)', async () => {
  server.use(
    http.get('*/api/preclasificacion', ({ request }) => {
      const por = new URL(request.url).searchParams.get('por');
      if (por === 'cabys')
        return HttpResponse.json([
          { clave: '3420100', etiqueta: 'Diésel', lineas: 12, base: '1240000' },
          { clave: '2310100', etiqueta: 'Fertilizante', lineas: 9, base: '880500' },
        ]);
      return HttpResponse.json([]);
    }),
    http.post('*/api/reglas', async ({ request }) => {
      const b = (await request.json()) as Record<string, unknown>;
      if (b.cabys === '2310100') return HttpResponse.json({ detail: 'duplicada' }, { status: 422 });
      return HttpResponse.json({ id: 1, ...b }, { status: 201 });
    }),
  );
  renderWithProviders(conSeleccion(<PreclasificarPage />));
  // asignar ambas
  await userEvent.click((await screen.findAllByLabelText('Clasificación 3420100'))[0]);
  await userEvent.click(await screen.findByRole('option', { name: 'Compras' }));
  await userEvent.click(screen.getAllByLabelText('Clasificación 2310100')[0]);
  await userEvent.click(await screen.findByRole('option', { name: 'Gastos' }));
  await userEvent.click(screen.getByRole('button', { name: 'Guardar asignaciones' }));
  // la fila que falló (2310100) conserva su valor 'Gastos'; la que pasó (3420100) se limpia
  await waitFor(() => expect(screen.getAllByLabelText('Clasificación 2310100')[0]).toHaveValue('Gastos'));
  expect(screen.getAllByLabelText('Clasificación 3420100')[0]).toHaveValue('');
});
