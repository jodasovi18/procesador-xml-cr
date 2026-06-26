import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen, fireEvent, waitFor } from '@testing-library/react';
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

  // Try userEvent.upload first; if that doesn't trigger Mantine's onDrop,
  // fall back to fireEvent.change which directly fires the change event.
  const files = [
    new File(['<xml/>'], 'a.xml', { type: 'text/xml' }),
    new File(['<xml/>'], 'b.xml', { type: 'text/xml' }),
  ];

  try {
    await userEvent.upload(input, files);
  } catch {
    // Fallback: fire change event directly
    fireEvent.change(input, { target: { files } });
  }

  expect(await screen.findByText('a.xml')).toBeInTheDocument();
  expect(await screen.findByText('XML inválido')).toBeInTheDocument();
  expect(await screen.findByText('1 nuevos')).toBeInTheDocument();
});
