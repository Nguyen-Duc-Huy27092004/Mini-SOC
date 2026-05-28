import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuthStore, selectIsAuthenticated, selectUser } from '../features/auth/store';
import { LoginPage } from '../features/auth/pages/LoginPage';
import { ChangePasswordPage } from '../features/auth/pages/ChangePasswordPage';
import { ExecutiveDashboard } from '../features/dashboard/pages/ExecutiveDashboard';
import { AnalystDashboard } from '../features/analyst/pages/AnalystDashboard';
import { OperationsDashboard } from '../features/operations/pages/OperationsDashboard';
import { AlertsPage } from '../features/alerts/pages/AlertsPage';
import { MainLayout } from '../widgets/layout/MainLayout';

function Protected({ children }: { children: React.ReactNode }) {
  const ok = useAuthStore(selectIsAuthenticated);
  return ok ? <>{children}</> : <Navigate to="/login" replace />;
}

function HomeByRole() {
  const user = useAuthStore(selectUser);
  const roles = user?.roles || [];
  if (roles.includes('SOC Analyst')) return <AnalystDashboard />;
  if (roles.includes('IT Admin')) return <OperationsDashboard />;
  return <ExecutiveDashboard />;
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/change-password" element={
        <Protected>
          <ChangePasswordPage />
        </Protected>
      } />
      <Route
        element={
          <Protected>
            <MainLayout />
          </Protected>
        }
      >
        <Route index element={<HomeByRole />} />
        <Route path="executive" element={<ExecutiveDashboard />} />
        <Route path="analyst" element={<AnalystDashboard />} />
        <Route path="operations" element={<OperationsDashboard />} />
        <Route path="alerts" element={<AlertsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
