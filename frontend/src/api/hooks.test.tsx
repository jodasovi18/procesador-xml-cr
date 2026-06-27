import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { renderHook, waitFor } from '@testing-library/react';
import { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useClientes, useResumen, useResumenClasificacion, useD150, useCrearCliente, useIngestaLote, useReglas, useEditarRegla, usePreclasificacion } from './hooks';

const server = setupServer();
beforeAll(() => server.listen());
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

it('useClientes devuelve la lista', async () => {
  server.use(
    http.get('*/api/clientes', () =>
      HttpResponse.json([
        { id: 1, nombre: 'Agrofinca', cedula: '3101', tipo_cedula: 'juridica', regimen: 'tradicional' },
      ])
    )
  );
  const { result } = renderHook(() => useClientes(), { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.[0].nombre).toBe('Agrofinca');
  expect(result.current.data?.[0].id).toBe(1);
});

it('useResumen pasa cliente/periodo/rol como query params', async () => {
  let url = '';
  server.use(
    http.get('*/api/resumen', ({ request }) => {
      url = new URL(request.url).search;
      return HttpResponse.json({ Bienes: { base: '100', iva: '13' } });
    })
  );
  const { result } = renderHook(() => useResumen(1, '2026-05', 'compra'), { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(url).toContain('cliente_id=1');
  expect(url).toContain('periodo=2026-05');
  expect(url).toContain('rol=compra');
  expect(result.current.data?.['Bienes']?.base).toBe('100');
});

it('useResumen no ejecuta si faltan cliente/periodo', () => {
  const { result } = renderHook(() => useResumen(null, null, 'compra'), { wrapper });
  expect(result.current.status).toBe('pending');
  expect(result.current.fetchStatus).toBe('idle');
});

it('useResumenClasificacion pasa params correctos', async () => {
  let url = '';
  server.use(
    http.get('*/api/resumen/clasificacion', ({ request }) => {
      url = new URL(request.url).search;
      return HttpResponse.json({ Combustibles: { '13%': { base: '50', iva: '0' } } });
    })
  );
  const { result } = renderHook(() => useResumenClasificacion(2, '2026-05', 'venta'), { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(url).toContain('cliente_id=2');
  expect(url).toContain('rol=venta');
  expect(result.current.data?.['Combustibles']?.['13%']?.base).toBe('50');
});

it('useD150 devuelve preciso y ovi', async () => {
  server.use(
    http.get('*/api/d150', () =>
      HttpResponse.json({ preciso: { debito: '100' }, ovi: { debito: 100 } })
    )
  );
  const { result } = renderHook(() => useD150(1, '2026-05'), { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect((result.current.data?.preciso as unknown as Record<string, unknown>)?.['debito']).toBe('100');
  expect((result.current.data?.ovi as unknown as Record<string, unknown>)?.['debito']).toBe(100);
});

it('useCrearCliente llama POST y devuelve el cliente creado', async () => {
  server.use(
    http.post('*/api/clientes', async ({ request }) => {
      const body = await request.json() as Record<string, unknown>;
      return HttpResponse.json(
        { id: 99, nombre: body['nombre'], cedula: body['cedula'], tipo_cedula: body['tipo_cedula'], regimen: body['regimen'] },
        { status: 201 }
      );
    })
  );
  const { result } = renderHook(() => useCrearCliente(), { wrapper });
  result.current.mutate({ nombre: 'Test SA', cedula: '3102', tipo_cedula: 'juridica', regimen: 'tradicional' });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.id).toBe(99);
  expect(result.current.data?.nombre).toBe('Test SA');
});

it('useIngestaLote devuelve el LoteResponse completo (totales + archivos)', async () => {
  server.use(
    http.post('*/api/ingesta/lote', () =>
      HttpResponse.json({
        total: 1,
        nuevos: 1,
        actualizados: 0,
        omitidos: 0,
        errores: 0,
        archivos: [{ archivo: 'a.xml', estado: 'nuevo' }],
      })
    )
  );
  const { result } = renderHook(() => useIngestaLote(), { wrapper });
  const file = new File(['<xml/>'], 'a.xml', { type: 'text/xml' });
  result.current.mutate([file]);
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.total).toBe(1);
  expect(result.current.data?.archivos[0].archivo).toBe('a.xml');
  expect(result.current.data?.archivos[0].estado).toBe('nuevo');
});

it('useReglas pasa cliente_id y devuelve la lista', async () => {
  server.use(http.get('*/api/reglas', ({ request }) => {
    const cid = new URL(request.url).searchParams.get('cliente_id');
    return HttpResponse.json([{ id: 1, cliente_id: Number(cid), cedula: '310', cabys: null, rol: null, clasificacion: 'Compras', sub_clasificacion: null }]);
  }));
  const { result } = renderHook(() => useReglas(7), { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.[0].clasificacion).toBe('Compras');
  expect(result.current.data?.[0].cliente_id).toBe(7);
});

it('useReglas no dispara sin cliente', () => {
  const { result } = renderHook(() => useReglas(null), { wrapper });
  expect(result.current.fetchStatus).toBe('idle');
});

it('useEditarRegla hace PUT al id correcto', async () => {
  let metodo = ''; let ruta = '';
  server.use(http.put('*/api/reglas/:id', ({ request, params }) => {
    metodo = request.method; ruta = String(params.id);
    return HttpResponse.json({ id: Number(params.id), cliente_id: 7, cedula: null, cabys: '231', rol: null, clasificacion: 'No Deducibles', sub_clasificacion: null });
  }));
  const { result } = renderHook(() => useEditarRegla(), { wrapper });
  await result.current.mutateAsync({ id: 5, data: { cliente_id: 7, cabys: '231', clasificacion: 'No Deducibles' } });
  expect(metodo).toBe('PUT');
  expect(ruta).toBe('5');
});

it('usePreclasificacion pasa cliente_id/periodo/rol/por', async () => {
  let url = '';
  server.use(http.get('*/api/preclasificacion', ({ request }) => {
    url = new URL(request.url).search;
    return HttpResponse.json([{ clave: '2310100', etiqueta: 'Fertilizante', lineas: 2, base: '150' }]);
  }));
  const { result } = renderHook(() => usePreclasificacion(7, '2026-05', 'compra', 'cabys'), { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.[0].clave).toBe('2310100');
  expect(url).toContain('cliente_id=7');
  expect(url).toContain('periodo=2026-05');
  expect(url).toContain('rol=compra');
  expect(url).toContain('por=cabys');
});

it('usePreclasificacion no dispara sin cliente o período', () => {
  const { result } = renderHook(() => usePreclasificacion(null, '2026-05', 'compra', 'cabys'), { wrapper });
  expect(result.current.fetchStatus).toBe('idle');
});
