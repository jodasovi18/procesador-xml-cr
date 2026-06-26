import { Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from './auth/LoginPage';
import { RequireAuth } from './auth/RequireAuth';
import { AppShell } from './components/AppShell';
import { ClientesPage } from './pages/ClientesPage';
import { SubidaPage } from './pages/SubidaPage';
import { ResumenPage } from './pages/ResumenPage';
import { D150Page } from './pages/D150Page';

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <AppShell>
              <Routes>
                <Route path="/clientes" element={<ClientesPage />} />
                <Route path="/subida" element={<SubidaPage />} />
                <Route path="/resumen" element={<ResumenPage />} />
                <Route path="/d150" element={<D150Page />} />
                <Route path="*" element={<Navigate to="/clientes" replace />} />
              </Routes>
            </AppShell>
          </RequireAuth>
        }
      />
    </Routes>
  );
}
