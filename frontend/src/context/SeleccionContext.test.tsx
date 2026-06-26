import { renderHook, act } from '@testing-library/react';
import { SeleccionProvider, useSeleccion } from './SeleccionContext';

it('default rol = compra y permite cambiar la selección', () => {
  const { result } = renderHook(() => useSeleccion(), { wrapper: SeleccionProvider });
  expect(result.current.rol).toBe('compra');
  expect(result.current.clienteId).toBeNull();
  expect(result.current.periodo).toBeNull();
  act(() => {
    result.current.setClienteId(5);
    result.current.setPeriodo('2026-05');
    result.current.setRol('venta');
  });
  expect(result.current.clienteId).toBe(5);
  expect(result.current.periodo).toBe('2026-05');
  expect(result.current.rol).toBe('venta');
});

it('useSeleccion lanza fuera del provider', () => {
  expect(() => renderHook(() => useSeleccion())).toThrow();
});
