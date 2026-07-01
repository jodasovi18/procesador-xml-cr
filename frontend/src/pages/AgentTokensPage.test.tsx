import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/utils';
import { AgentTokensPage } from './AgentTokensPage';

const TOKEN = { id: 1, label: 'PC-01', created_at: '2026-05-12T09:14:00Z' };

const server = setupServer(
  http.get('*/api/agent-tokens', () => HttpResponse.json([TOKEN])),
);
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

it('lista los tokens', async () => {
  renderWithProviders(<AgentTokensPage />);
  expect(await screen.findByText('PC-01')).toBeInTheDocument();
});

it('crear muestra el token revelado una vez', async () => {
  server.use(http.post('*/api/agent-tokens', async ({ request }) => {
    const b = (await request.json()) as { label: string };
    return HttpResponse.json({ id: 2, label: b.label, token: 'sxk_secreto_123' }, { status: 201 });
  }));
  renderWithProviders(<AgentTokensPage />);
  await userEvent.type(await screen.findByLabelText('Etiqueta'), 'Agente nuevo');
  await userEvent.click(screen.getByRole('button', { name: 'Crear token' }));
  expect(await screen.findByText('sxk_secreto_123')).toBeInTheDocument();
});

it('revoca un token con DELETE al id tras confirmar', async () => {
  let delId = '';
  server.use(http.delete('*/api/agent-tokens/:id', ({ params }) => {
    delId = String(params.id);
    return new HttpResponse(null, { status: 204 });
  }));
  renderWithProviders(<AgentTokensPage />);
  await userEvent.click(await screen.findByRole('button', { name: 'Revocar' }));
  const dialog = await screen.findByRole('dialog');
  await userEvent.click(within(dialog).getByRole('button', { name: 'Revocar' }));
  await waitFor(() => expect(delId).toBe('1'));
});
