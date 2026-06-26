import { screen } from '@testing-library/react';
import { Routes, Route } from 'react-router-dom';
import { renderWithProviders } from '../test/utils';
import { AuthProvider } from './AuthContext';
import { RequireAuth } from './RequireAuth';
import { clearToken, setToken } from '../api/client';

function Protegido() {
  return (
    <Routes>
      <Route path="/login" element={<div>pantalla de login</div>} />
      <Route path="/secreto" element={<RequireAuth><div>contenido secreto</div></RequireAuth>} />
    </Routes>
  );
}

afterEach(() => clearToken());

it('redirige a /login cuando no hay sesión', () => {
  clearToken();
  renderWithProviders(<AuthProvider><Protegido /></AuthProvider>, { route: '/secreto' });
  expect(screen.getByText('pantalla de login')).toBeInTheDocument();
});

it('muestra el contenido protegido cuando hay token', () => {
  setToken('tok-x');
  renderWithProviders(<AuthProvider><Protegido /></AuthProvider>, { route: '/secreto' });
  expect(screen.getByText('contenido secreto')).toBeInTheDocument();
});
