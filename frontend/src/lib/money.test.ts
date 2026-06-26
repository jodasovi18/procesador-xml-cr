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
});
