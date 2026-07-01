import { ReactNode } from 'react';
import { Alert } from '@mantine/core';
import { useAuth } from './AuthContext';

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { esAdmin } = useAuth();
  if (!esAdmin) return <Alert color="red">Requiere permisos de administrador.</Alert>;
  return <>{children}</>;
}
