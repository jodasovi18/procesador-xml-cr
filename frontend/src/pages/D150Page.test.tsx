import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/utils';
import { SeleccionProvider } from '../context/SeleccionContext';
import { D150Page } from './D150Page';

// Real shape: nested { ventas, compras, liquidacion }
// preciso values are Decimal strings; ovi values are integers (estado is string)
const MOCK_PRECISO = {
  ventas: {
    por_tasa: {
      '1%': { base: '34749173.64', iva: '347491.74' },
      '13%': { base: '1824800.00', iva: '237224.00' },
    },
    exentas: '0.00',
    no_sujetas: '699750.00',
    total_gravadas: '36573973.64',
    total_impuesto: '584715.74',
    total_general: '37273723.64',
  },
  compras: {
    por_tasa: {
      '13%': { base: '30000000.00', iva: '3900000.00' },
    },
    exentas: '0.00',
    no_sujetas: '0.00',
    total_gravadas: '30000000.00',
    total_credito: '3900000.00',
    total_general: '30000000.00',
    no_deducibles: '500000.00',
    tiquetes_excluidos_n: 2,
    tiquetes_excluidos_iva: '50000.00',
  },
  liquidacion: {
    debito_fiscal: '584715.74',
    credito_fiscal: '3900000.00',
    impuesto_neto: '-3315284.26',
    estado: 'saldo_favor',
  },
};

const MOCK_OVI = {
  ventas: {
    por_tasa: {
      '1%': { base: 34749174, iva: 347492 },
      '13%': { base: 1824800, iva: 237224 },
    },
    exentas: 0,
    no_sujetas: 699750,
    total_gravadas: 36573974,
    total_impuesto: 584716,
    total_general: 37273724,
  },
  compras: {
    por_tasa: {
      '13%': { base: 30000000, iva: 3900000 },
    },
    exentas: 0,
    no_sujetas: 0,
    total_gravadas: 30000000,
    total_credito: 3900000,
    total_general: 30000000,
    no_deducibles: 500000,
    tiquetes_excluidos_n: 2,
    tiquetes_excluidos_iva: 50000,
  },
  liquidacion: {
    debito_fiscal: 584716,
    credito_fiscal: 3900000,
    impuesto_neto: -3315284,
    estado: 'saldo_favor',
  },
};

const server = setupServer(
  http.get('*/api/d150', () =>
    HttpResponse.json({ preciso: MOCK_PRECISO, ovi: MOCK_OVI })
  )
);

beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

it('muestra alerta cuando no hay cliente/período seleccionado', () => {
  renderWithProviders(
    <SeleccionProvider>
      <D150Page />
    </SeleccionProvider>
  );
  expect(
    screen.getByText('Elegí cliente y período en la barra superior.')
  ).toBeInTheDocument();
});

it('muestra el D-150 preciso con valores en colones formateados', async () => {
  renderWithProviders(
    <SeleccionProvider initialClienteId={1} initialPeriodo="2026-05">
      <D150Page />
    </SeleccionProvider>
  );
  // Liquidación → débito fiscal formateado con ₡ y separadores (aparece varias veces)
  const debitoElems = await screen.findAllByText('₡584.715,74');
  expect(debitoElems.length).toBeGreaterThanOrEqual(1);
  // Crédito fiscal formateado
  expect(screen.getAllByText('₡3.900.000,00').length).toBeGreaterThanOrEqual(1);
  // Estado no pasa por formatColones
  expect(screen.getByText('saldo_favor')).toBeInTheDocument();
});

it('cambia a vista OVI y muestra enteros sin decimales', async () => {
  renderWithProviders(
    <SeleccionProvider initialClienteId={1} initialPeriodo="2026-05">
      <D150Page />
    </SeleccionProvider>
  );
  // Esperar carga (múltiples elementos con el mismo valor)
  await screen.findAllByText('₡584.715,74');

  // Cambiar a OVI
  await userEvent.click(screen.getByText('OVI (entero)'));

  // En OVI los valores son enteros sin símbolo de moneda (puede haber duplicados)
  expect((await screen.findAllByText('584716')).length).toBeGreaterThanOrEqual(1);
  expect(screen.getAllByText('3900000').length).toBeGreaterThanOrEqual(1);
  // Estado sigue igual
  expect(screen.getByText('saldo_favor')).toBeInTheDocument();
  // Ya no hay formatos con ₡
  expect(screen.queryByText('₡584.715,74')).not.toBeInTheDocument();
});

it('muestra error cuando la API falla y permite reintentar', async () => {
  server.use(
    http.get('*/api/d150', () => HttpResponse.error())
  );
  renderWithProviders(
    <SeleccionProvider initialClienteId={1} initialPeriodo="2026-05">
      <D150Page />
    </SeleccionProvider>
  );
  expect(await screen.findByText(/Error al cargar el D-150/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
});
