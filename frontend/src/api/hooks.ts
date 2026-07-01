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

// El backend guarda Comprobante.periodo como "YYYYMM"; el front maneja "YYYY-MM".
export const periodoApi = (p: string) => p.replace(/-/g, '');

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
        '/api/resumen' + qs({ cliente_id: clienteId!, periodo: periodoApi(periodo!), rol })
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
        '/api/resumen/clasificacion' + qs({ cliente_id: clienteId!, periodo: periodoApi(periodo!), rol })
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
        '/api/d150' + qs({ cliente_id: clienteId!, periodo: periodoApi(periodo!) })
      )) ?? ({ preciso: {}, ovi: {} } as D150Response),
  });
}

// ---------------------------------------------------------------------------
// Reglas types
// ---------------------------------------------------------------------------

export interface Regla {
  id: number;
  cliente_id: number;
  cedula: string | null;
  cabys: string | null;
  rol: string | null;
  clasificacion: string;
  sub_clasificacion: string | null;
}

export interface ReglaCreate {
  cliente_id: number;
  cedula?: string | null;
  cabys?: string | null;
  rol?: string | null;
  clasificacion: string;
  sub_clasificacion?: string | null;
}

// ---------------------------------------------------------------------------
// Reglas hooks
// ---------------------------------------------------------------------------

/** Lista las reglas de clasificación de un cliente. No ejecuta si clienteId es null. */
export function useReglas(clienteId: number | null) {
  return useQuery({
    queryKey: ['reglas', clienteId],
    enabled: clienteId != null,
    queryFn: async () =>
      (await apiFetch<Regla[]>('/api/reglas' + qs({ cliente_id: clienteId! }))) ?? [],
  });
}

/** Crea una regla de clasificación. Invalida la lista al terminar. */
export function useCrearRegla() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ReglaCreate) =>
      apiFetch<Regla>('/api/reglas', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['reglas', vars.cliente_id] }),
  });
}

/** Edita una regla existente. Invalida la lista al terminar. */
export function useEditarRegla() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ReglaCreate }) =>
      apiFetch<Regla>(`/api/reglas/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['reglas', vars.data.cliente_id] }),
  });
}

/** Elimina una regla. Invalida la lista al terminar. */
export function useEliminarRegla() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: number; clienteId: number }) =>
      apiFetch<void>(`/api/reglas/${id}`, { method: 'DELETE' }),
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['reglas', vars.clienteId] }),
  });
}

// ---------------------------------------------------------------------------
// Preclasificacion types + hook
// ---------------------------------------------------------------------------

export interface GrupoPreclasificacion {
  clave: string;
  etiqueta: string;
  lineas: number;
  base: string;
}
export type PorPreclasificacion = 'cabys' | 'cedula';

export function usePreclasificacion(
  clienteId: number | null,
  periodo: string | null,
  rol: Rol,
  por: PorPreclasificacion,
) {
  return useQuery({
    queryKey: ['preclasificacion', clienteId, periodo, rol, por],
    enabled: clienteId != null && periodo != null,
    queryFn: async () =>
      (await apiFetch<GrupoPreclasificacion[]>(
        '/api/preclasificacion' + qs({ cliente_id: clienteId!, periodo: periodoApi(periodo!), rol, por }),
      )) ?? [],
  });
}

// ---------------------------------------------------------------------------
// Entradas Manuales types + hooks
// ---------------------------------------------------------------------------

export interface EntradaManual {
  id: number;
  cliente_id: number;
  periodo: string;
  rol: string;
  descripcion: string | null;
  monto: string;
  tarifa: string;
  no_sujeto: boolean;
  deducible: boolean;
  iva: string;
}

export interface EntradaManualCreate {
  cliente_id: number;
  periodo: string;
  rol: string;
  descripcion?: string | null;
  monto: string;
  tarifa: string;
  no_sujeto: boolean;
  deducible: boolean;
}

export interface EntradasManualesResp {
  entradas: EntradaManual[];
  total_monto: string;
  total_iva: string;
}

const RESP_VACIA: EntradasManualesResp = { entradas: [], total_monto: '0', total_iva: '0' };

export function useEntradasManuales(clienteId: number | null, periodo: string | null, rol: Rol) {
  return useQuery({
    queryKey: ['entradas', clienteId, periodo, rol],
    enabled: clienteId != null && periodo != null,
    queryFn: async () =>
      (await apiFetch<EntradasManualesResp>(
        '/api/entradas-manuales' + qs({ cliente_id: clienteId!, periodo: periodoApi(periodo!), rol }),
      )) ?? RESP_VACIA,
  });
}

export function useCrearEntrada() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: EntradaManualCreate) =>
      apiFetch<EntradaManual>('/api/entradas-manuales', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entradas'] });
      qc.invalidateQueries({ queryKey: ['d150'] });
    },
  });
}

export function useEditarEntrada() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: EntradaManualCreate }) =>
      apiFetch<EntradaManual>(`/api/entradas-manuales/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entradas'] });
      qc.invalidateQueries({ queryKey: ['d150'] });
    },
  });
}

export function useEliminarEntrada() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: number }) =>
      apiFetch<void>(`/api/entradas-manuales/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entradas'] });
      qc.invalidateQueries({ queryKey: ['d150'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Agent Tokens types + hooks
// ---------------------------------------------------------------------------

export interface AgentToken {
  id: number;
  label: string;
  created_at: string;
}

export interface AgentTokenCreado {
  id: number;
  label: string;
  token: string;
}

export function useAgentTokens() {
  return useQuery({
    queryKey: ['agent-tokens'],
    queryFn: async () => (await apiFetch<AgentToken[]>('/api/agent-tokens')) ?? [],
  });
}

export function useCrearAgentToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (label: string) =>
      apiFetch<AgentTokenCreado>('/api/agent-tokens', { method: 'POST', body: JSON.stringify({ label }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agent-tokens'] }),
  });
}

export function useRevocarAgentToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/api/agent-tokens/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agent-tokens'] }),
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
