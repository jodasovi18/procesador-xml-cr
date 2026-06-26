import { formatColones } from './money';

describe('formatColones', () => {
  it('formatea con separador de miles y dos decimales', () => {
    expect(formatColones('34749173.64')).toBe('₡34.749.173,64');
  });
  it('agrega dos decimales a un entero', () => {
    expect(formatColones('1824800')).toBe('₡1.824.800,00');
  });
  it('formatea cero', () => {
    expect(formatColones('0')).toBe('₡0,00');
  });
  it('devuelve guion para valores vacíos o no numéricos', () => {
    expect(formatColones('')).toBe('—');
    expect(formatColones('abc')).toBe('—');
  });
  it('formatea montos negativos (notas de crédito)', () => {
    // es-ES NO agrupa números de 4 dígitos (minimumGroupingDigits), ni positivos ni negativos.
    expect(formatColones('-1234.56')).toBe('₡-1234,56');
  });
  it('agrupa los miles también en negativos grandes', () => {
    expect(formatColones('-1234567.89')).toBe('₡-1.234.567,89');
  });
  it('devuelve guion para null/undefined', () => {
    expect(formatColones(null)).toBe('—');
    expect(formatColones(undefined)).toBe('—');
  });
});
