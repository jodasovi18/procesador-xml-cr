import { ReactNode } from 'react';
import { Alert, Loader } from '@mantine/core';
import { useAuth } from './AuthContext';

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { esAdmin, adminCargando } = useAuth();
  if (adminCargando) return <Loader />;
  if (!esAdmin) return <Alert color="red">Requiere permisos de administrador.</Alert>;
  return <>{children}</>;
}
