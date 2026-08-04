# Frontend Component & API Integration Guide
## Enterprise Mini SOC Platform

### 1. Standard UI States Guidelines (Mandatory Rules)
Every React UI container and component MUST explicitly handle:
1. **Loading State:** Skeleton screens or `<LoadingSpinner />` while TanStack Query `isLoading` is true.
2. **Error State:** `<ErrorAlert message={error.message} onRetry={refetch} />` when `isError` is true.
3. **Empty State:** `<EmptyState title="No Alerts Found" description="System is clear." />` when data array is empty.

---

### 2. Live Alerts Grid Component Specs (`frontend/src/components/alerts/AlertGrid.tsx`)

```tsx
import { Alert } from '@/types/alert';
import { Badge } from '@/components/ui/badge';

interface AlertGridProps {
  alerts: Alert[];
  onSelectAlert: (alert: Alert) => void;
}

export const AlertGrid = ({ alerts, onSelectAlert }: AlertGridProps) => {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900">
      <table className="w-full text-left text-sm text-slate-300">
        <thead className="bg-slate-950 text-xs uppercase text-slate-400">
          <tr>
            <th className="px-4 py-3">Timestamp</th>
            <th className="px-4 py-3">Severity</th>
            <th className="px-4 py-3">Title</th>
            <th className="px-4 py-3">Source IP</th>
            <th className="px-4 py-3">MITRE Tactic</th>
            <th className="px-4 py-3">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {alerts.map((alert) => (
            <tr key={alert.id} className="hover:bg-slate-800/50 transition-colors">
              <td className="px-4 py-3 font-mono text-xs">{new Date(alert.timestamp).toLocaleString()}</td>
              <td className="px-4 py-3">
                <Badge variant={alert.severity === 'CRITICAL' ? 'destructive' : 'default'}>
                  {alert.severity}
                </Badge>
              </td>
              <td className="px-4 py-3 font-medium text-slate-100">{alert.title}</td>
              <td className="px-4 py-3 font-mono">{alert.source_ip || 'N/A'}</td>
              <td className="px-4 py-3 text-xs text-sky-400">{alert.mitre_tactic}</td>
              <td className="px-4 py-3">
                <button
                  onClick={() => onSelectAlert(alert)}
                  className="rounded bg-sky-600 px-3 py-1 text-xs font-semibold text-white hover:bg-sky-500"
                >
                  Investigate
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
```
