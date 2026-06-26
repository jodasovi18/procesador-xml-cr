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

// ---------------------------------------------------------------------------
// D-150 shape types (shared with D150Page.tsx)
// ---------------------------------------------------------------------------

export interface PorTasaEntry {
  base: string | number;
  iva: string | number;
}

export interface SeccionBase {
  por_tasa: Record<string, PorTasaEntry>;
  exentas: string | number;
  no_sujetas: string | number;
  total_gravadas: string | number;
  total_general: string | number;
}

export interface SeccionVentas extends SeccionBase {
  total_impuesto: string | number;
}

export interface SeccionCompras extends SeccionBase {
  total_credito: string | number;
  no_deducibles?: string | number;
  tiquetes_excluidos_n?: number;
  tiquetes_excluidos_iva?: string | number;
}

export interface Liquidacion {
  debito_fiscal: string | number;
  credito_fiscal: string | number;
  impuesto_neto: string | number;
  estado: string;
}

export interface D150Shape {
  ventas: SeccionVentas;
  compras: SeccionCompras;
  liquidacion: Liquidacion;
}

export interface D150Response {
  preciso: D150Shape;
  ovi: D150Shape;
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
 * Devuelve el `LoteResponse` completo: totales (total/nuevos/actualizados/omitidos/errores)
 * y `.archivos` con el detalle por archivo (ResultadoArchivo[]).
 * Invalida resumen, resumen-clasificacion y d150 al terminar.
 */
export function useIngestaLote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (archivos: File[]) => {
      const fd = new FormData();
      for (const f of archivos) fd.append('archivos', f);
      return (await apiFetch<LoteResponse>('/api/ingesta/lote', { method: 'POST', body: fd }))
        ?? { total: 0, nuevos: 0, actualizados: 0, omitidos: 0, errores: 0, archivos: [] };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['resumen'] });
      qc.invalidateQueries({ queryKey: ['resumen-clasificacion'] });
      qc.invalidateQueries({ queryKey: ['d150'] });
    },
  });
}
