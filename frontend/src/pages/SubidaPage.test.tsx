import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/utils';
import { SubidaPage } from './SubidaPage';

const server = setupServer();
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

it('muestra el reporte por archivo y los totales tras subir', async () => {
  server.use(
    http.post('*/api/ingesta/lote', () =>
      HttpResponse.json({
        total: 2,
        nuevos: 1,
        actualizados: 0,
        omitidos: 0,
        errores: 1,
        archivos: [
          { archivo: 'a.xml', estado: 'nuevo' },
          { archivo: 'b.xml', estado: 'error', motivo: 'XML inválido' },
        ],
      })
    )
  );
  renderWithProviders(<SubidaPage />);

  const input = document.querySelector('input[type="file"]') as HTMLInputElement;

  const files = [
    new File(['<xml/>'], 'a.xml', { type: 'text/xml' }),
    new File(['<xml/>'], 'b.xml', { type: 'text/xml' }),
  ];

  await userEvent.upload(input, files);

  expect(await screen.findByText('a.xml')).toBeInTheDocument();
  expect(await screen.findByText('XML inválido')).toBeInTheDocument();
  expect(await screen.findByText('1 nuevos')).toBeInTheDocument();
});
