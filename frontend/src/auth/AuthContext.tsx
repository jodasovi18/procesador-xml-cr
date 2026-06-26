import { createContext, useContext, useState, ReactNode } from 'react';
import { apiFetch, setToken, clearToken, getToken, ApiError } from '../api/client';

interface AuthState {
  isAuthenticated: boolean;
  login: (usuario: string, clave: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

interface TokenResponse { access_token: string }

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTok] = useState<string | null>(() => getToken());

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
    setTok(data.access_token);
  }

  function logout() {
    clearToken();
    setTok(null);
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth fuera de AuthProvider');
  return ctx;
}
