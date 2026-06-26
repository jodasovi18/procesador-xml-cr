import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from './client';
import type { Rol } from '../context/SeleccionContext';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Cliente {
  id: number;
  nombre: string;
  cedula: string;
  tipo_cedula: string;
  regimen: string;
}

export interface ClienteCreate {
  nombre: string;
  cedula: string;
  tipo_cedula: string;
  regimen: string;
}

export type Resumen = Record<string, { base: string; iva: string }>;
export type ResumenClasificacion = Record<string, Record<string, { base: string; iva: string }>>;

export interface D150Response {
  preciso: Record<string, unknown>;
  ovi: Record<string, unknown>;
}

/**
 * Forma real devuelta por motor/ingesta_lote.py → _ingest_uno / _resumen.
 * Éxito:   { archivo, estado: 'nuevo'|'actualizado', clave, rol, cliente_id }
 * Omitido: { archivo, estado: 'omitido', motivo }
 * Error:   { archivo, estado: 'error', motivo }
 * El wrapper useIngestaLote devuelve sólo el array `archivos` del resumen.
 */
export interface ResultadoArchivo {
  archivo: string;
  estado: 'nuevo' | 'actualizado' | 'omitido' | 'error';
  motivo?: string;
  clave?: string;
  rol?: string;
  cliente_id?: number;
}

/** Cuerpo completo que devuelve POST /api/ingesta/lote */
export interface LoteResponse {
  total: number;
  nuevos: number;
  actualizados: number;
  omitidos: number;
  errores: number;
  archivos: ResultadoArchivo[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const qs = (params: Record<string, string | number>): string =>
  '?' +
  new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)])
  ).toString();

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/** Lista todos los clientes. */
export function useClientes() {
  return useQuery({
    queryKey: ['clientes'],
    queryFn: async () => (await apiFetch<Cliente[]>('/api/clientes')) ?? [],
  });
}

/** Crea un cliente. Invalida la lista al terminar. */
export function useCrearCliente() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ClienteCreate) =>
      apiFetch<Cliente>('/api/clientes', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['clientes'] }),
  });
}

/** Resumen de compras/ventas por categoría. No ejecuta si faltan parámetros. */
export function useResumen(clienteId: number | null, periodo: string | null, rol: Rol) {
  return useQuery({
    queryKey: ['resumen', clienteId, periodo, rol],
    enabled: clienteId != null && periodo != null,
    queryFn: async () =>
      (await apiFetch<Resumen>(
        '/api/resumen' + qs({ cliente_id: clienteId!, periodo: periodo!, rol })
      )) ?? ({} as Resumen),
  });
}

/** Resumen clasificado (categoría → tasa → {base, iva}). No ejecuta si faltan parámetros. */
export function useResumenClasificacion(clienteId: number | null, periodo: string | null, rol: Rol) {
  return useQuery({
    queryKey: ['resumen-clasificacion', clienteId, periodo, rol],
    enabled: clienteId != null && periodo != null,
    queryFn: async () =>
      (await apiFetch<ResumenClasificacion>(
        '/api/resumen/clasificacion' + qs({ cliente_id: clienteId!, periodo: periodo!, rol })
      )) ?? ({} as ResumenClasificacion),
  });
}

/** D-150 (preciso + ovi). No ejecuta si faltan parámetros. */
export function useD150(clienteId: number | null, periodo: string | null) {
  return useQuery({
    queryKey: ['d150', clienteId, periodo],
    enabled: clienteId != null && periodo != null,
    queryFn: async () =>
      (await apiFetch<D150Response>(
        '/api/d150' + qs({ cliente_id: clienteId!, periodo: periodo! })
      )) ?? ({ preciso: {}, ovi: {} } as D150Response),
  });
}

/**
 * Sube un lote de archivos XML/ZIP.
 * Devuelve el array `archivos` del reporte (ResultadoArchivo[]).
 * Invalida resumen, resumen-clasificacion y d150 al terminar.
 */
export function useIngestaLote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (archivos: File[]): Promise<ResultadoArchivo[]> => {
      const fd = new FormData();
      for (const f of archivos) fd.append('archivos', f);
      const resp = await apiFetch<LoteResponse>('/api/ingesta/lote', {
        method: 'POST',
        body: fd,
      });
      return resp?.archivos ?? [];
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['resumen'] });
      qc.invalidateQueries({ queryKey: ['resumen-clasificacion'] });
      qc.invalidateQueries({ queryKey: ['d150'] });
    },
  });
}
