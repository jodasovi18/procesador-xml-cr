// Formatea un string decimal (proveniente de la API, donde el dinero es Decimal→str)
// a colones legibles. SOLO para mostrar: nunca usar el número para aritmética.
// Locale es-ES: punto de miles, coma decimal (es-CR usa espacio fino en este runtime).
const fmt = new Intl.NumberFormat('es-ES', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatColones(value: string): string {
  if (value === undefined || value === null || value.trim() === '') return '—';
  const n = Number(value);
  if (Number.isNaN(n)) return '—';
  return `₡${fmt.format(n)}`;
}
