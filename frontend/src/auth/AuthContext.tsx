import { createContext, useContext, useState, ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, setToken, clearToken, getToken, ApiError } from '../api/client';

interface Me { id: number; nombre: string; es_admin: boolean }

interface AuthState {
  isAuthenticated: boolean;
  esAdmin: boolean;
  login: (usuario: string, clave: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

interface TokenResponse { access_token: string }

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const qc = useQueryClient();
  const meQuery = useQuery({
    queryKey: ['me'],
    queryFn: () => apiFetch<Me>('/auth/me'),
    enabled: !!token,
  });
  const esAdmin = meQuery.data?.es_admin ?? false;

  async function login(usuario: string, clave: string) {
    // OAuth2 password flow: form-urlencoded, sin Bearer.
    // Usar string en vez de URLSearchParams para evitar el mismatch de clase entre realms
    // (jsdom vs MSW) que causa "Expected init.body to be an instance of URLSearchParams".
    const body = new URLSearchParams({ username: usuario, password: clave }).toString();
    const data = await apiFetch<TokenResponse>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    if (!data) throw new ApiError(500, 'respuesta vacía del login');
    setToken(data.access_token);
    setTokenState(data.access_token);
  }

  function logout() {
    clearToken();
    setTokenState(null);
    qc.removeQueries({ queryKey: ['me'] });
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!token, esAdmin, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth fuera de AuthProvider');
  return ctx;
}
