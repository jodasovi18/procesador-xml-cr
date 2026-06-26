import { createContext, useContext, useState, ReactNode } from 'react';

export type Rol = 'compra' | 'venta';

interface SeleccionState {
  clienteId: number | null;
  periodo: string | null; // "YYYY-MM"
  rol: Rol;
  setClienteId: (id: number | null) => void;
  setPeriodo: (p: string | null) => void;
  setRol: (r: Rol) => void;
}

const SeleccionContext = createContext<SeleccionState | null>(null);

export function SeleccionProvider({ children }: { children: ReactNode }) {
  const [clienteId, setClienteId] = useState<number | null>(null);
  const [periodo, setPeriodo] = useState<string | null>(null);
  const [rol, setRol] = useState<Rol>('compra');
  return (
    <SeleccionContext.Provider
      value={{ clienteId, periodo, rol, setClienteId, setPeriodo, setRol }}
    >
      {children}
    </SeleccionContext.Provider>
  );
}

export function useSeleccion(): SeleccionState {
  const ctx = useContext(SeleccionContext);
  if (!ctx) throw new Error('useSeleccion fuera de SeleccionProvider');
  return ctx;
}
