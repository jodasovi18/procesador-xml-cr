import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/utils';
import { SeleccionProvider } from '../context/SeleccionContext';
import { ResumenPage } from './ResumenPage';

const server = setupServer(
  http.get('*/api/resumen', () => HttpResponse.json({ Bienes: { base: '34749173.64', iva: '347491.74' } })),
  http.get('*/api/resumen/clasificacion', () => HttpResponse.json({
    Combustibles: { '13%': { base: '1000000', iva: '0' } },
  }))
);
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

it('muestra montos formateados en colones', async () => {
  renderWithProviders(
    <SeleccionProvider initialClienteId={1} initialPeriodo="2026-05"><ResumenPage /></SeleccionProvider>
  );
  expect(await screen.findByText('₡34.749.173,64')).toBeInTheDocument();
});

it('pide elegir cliente/período cuando no hay selección', () => {
  renderWithProviders(<SeleccionProvider><ResumenPage /></SeleccionProvider>);
  expect(screen.getByText('Elegí cliente y período en la barra superior.')).toBeInTheDocument();
});

it('muestra la clasificación formateada al cambiar de tab', async () => {
  renderWithProviders(
    <SeleccionProvider initialClienteId={1} initialPeriodo="2026-05"><ResumenPage /></SeleccionProvider>
  );
  await userEvent.click(await screen.findByRole('tab', { name: 'Clasificación' }));
  expect(await screen.findByText('Combustibles')).toBeInTheDocument();
  expect(await screen.findByText('₡1.000.000,00')).toBeInTheDocument();
});
