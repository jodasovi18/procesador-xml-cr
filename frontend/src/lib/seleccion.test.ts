import { mensajeSeleccion } from './seleccion';

describe('mensajeSeleccion', () => {
  it('faltan ambos (requiere período)', () => {
    expect(mensajeSeleccion(null, null, true)).toBe('Elegí cliente y período en la barra superior.');
  });
  it('hay cliente, falta período → NO pide cliente', () => {
    expect(mensajeSeleccion(1, null, true)).toBe('Elegí un período en la barra superior.');
  });
  it('falta cliente, hay período', () => {
    expect(mensajeSeleccion(null, '2026-05', true)).toBe('Elegí un cliente en la barra superior.');
  });
  it('ambos presentes → sin aviso', () => {
    expect(mensajeSeleccion(1, '2026-05', true)).toBeNull();
  });
  it('no requiere período: solo mira el cliente', () => {
    expect(mensajeSeleccion(null, null, false)).toBe('Elegí un cliente en la barra superior.');
    expect(mensajeSeleccion(5, null, false)).toBeNull();
  });
});
