import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { apiFetch, ApiError, setToken, clearToken } from './client';

const server = setupServer();
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => { server.resetHandlers(); clearToken(); });

describe('apiFetch', () => {
  it('parsea JSON en 200', async () => {
    server.use(http.get('/api/cosa', () => HttpResponse.json({ ok: true })));
    await expect(apiFetch('/api/cosa')).resolves.toEqual({ ok: true });
  });

  it('adjunta Authorization Bearer cuando hay token', async () => {
    let recibido = '';
    server.use(http.get('/api/cosa', ({ request }) => {
      recibido = request.headers.get('Authorization') ?? '';
      return HttpResponse.json({});
    }));
    setToken('abc123');
    await apiFetch('/api/cosa');
    expect(recibido).toBe('Bearer abc123');
  });

  it('no adjunta Authorization cuando no hay token', async () => {
    let recibido: string | null = 'x';
    server.use(http.get('/api/cosa', ({ request }) => {
      recibido = request.headers.get('Authorization');
      return HttpResponse.json({});
    }));
    await apiFetch('/api/cosa');
    expect(recibido).toBeNull();
  });

  it('lanza ApiError con status y detalle en 422', async () => {
    server.use(http.post('/api/x', () =>
      HttpResponse.json({ detail: 'XML inválido' }, { status: 422 })));
    await expect(apiFetch('/api/x', { method: 'POST' }))
      .rejects.toMatchObject({ status: 422, detail: 'XML inválido' });
  });

  it('no fija Content-Type para FormData', async () => {
    let ct: string | null = 'unset';
    server.use(http.post('/api/up', async ({ request }) => {
      ct = request.headers.get('Content-Type');
      return HttpResponse.json({});
    }));
    const fd = new FormData();
    fd.append('archivos', new File(['x'], 'a.xml'));
    await apiFetch('/api/up', { method: 'POST', body: fd });
    // El browser/undici fija multipart/form-data con boundary; nunca application/json.
    expect(ct).not.toContain('application/json');
  });
});
