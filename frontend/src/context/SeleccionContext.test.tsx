import { ReactNode } from 'react';
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

it('acepta selección inicial por props', () => {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <SeleccionProvider initialClienteId={7} initialPeriodo="2026-03" initialRol="venta">{children}</SeleccionProvider>
  );
  const { result } = renderHook(() => useSeleccion(), { wrapper });
  expect(result.current.clienteId).toBe(7);
  expect(result.current.periodo).toBe('2026-03');
  expect(result.current.rol).toBe('venta');
});
