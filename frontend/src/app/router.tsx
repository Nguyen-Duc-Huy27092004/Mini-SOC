import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuthStore, selectIsAuthenticated, selectUser } from '../features/auth/store';
import { LoginPage } from '../features/auth/pages/LoginPage';
import { ChangePasswordPage } from '../features/auth/pages/ChangePasswordPage';
import { ExecutiveDashboard } from '../features/dashboard/pages/ExecutiveDashboard';
import { AnalystDashboard } from '../features/analyst/pages/AnalystDashboard';
import { OperationsDashboard } from '../features/operations/pages/OperationsDashboard';
import { AlertsPage } from '../features/alerts/pages/AlertsPage';
import { MainLayout } from '../widgets/layout/MainLayout';

// Zabbix Pages
import { InfrastructureDashboard } from '../features/zabbix/pages/InfrastructureDashboard';
import { AssetManagement } from '../features/zabbix/pages/AssetManagement';
import { MaintenanceCenter } from '../features/zabbix/pages/MaintenanceCenter';
import { TaskCenter } from '../features/zabbix/pages/TaskCenter';
import { NotificationSettings } from '../features/zabbix/pages/NotificationSettings';

// SOAR Pages
import { SoarDashboard } from '../features/soar/pages/SoarDashboard';
import { PlaybooksPage } from '../features/soar/pages/PlaybooksPage';
import { RulesPage } from '../features/soar/pages/RulesPage';
import { ApprovalsPage } from '../features/soar/pages/ApprovalsPage';

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
        
        {/* Zabbix Routes */}
        <Route path="infrastructure" element={<InfrastructureDashboard />} />
        <Route path="infrastructure/assets" element={<AssetManagement />} />
        <Route path="infrastructure/maintenance" element={<MaintenanceCenter />} />
        <Route path="infrastructure/tasks" element={<TaskCenter />} />
        <Route path="infrastructure/notifications" element={<NotificationSettings />} />

        {/* SOAR Routes */}
        <Route path="soar" element={<SoarDashboard />} />
        <Route path="soar/playbooks" element={<PlaybooksPage />} />
        <Route path="soar/rules" element={<RulesPage />} />
        <Route path="soar/approvals" element={<ApprovalsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
