// Mensaje del guard de selección: nombra exactamente lo que falta (cliente y/o período),
// para no pedir un cliente que el usuario ya eligió.
export function mensajeSeleccion(
  clienteId: number | null,
  periodo: string | null,
  requierePeriodo: boolean,
): string | null {
  const faltaCliente = clienteId == null;
  const faltaPeriodo = requierePeriodo && periodo == null;
  if (!faltaCliente && !faltaPeriodo) return null;
  if (faltaCliente && faltaPeriodo) return 'Elegí cliente y período en la barra superior.';
  if (faltaCliente) return 'Elegí un cliente en la barra superior.';
  return 'Elegí un período en la barra superior.';
}
