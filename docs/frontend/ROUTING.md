# Routing, Protected Guards & RBAC UI
## Enterprise Mini SOC Platform

### 1. React Router Setup with Protected Route Guards

```tsx
// ProtectedRoute.tsx Example Blueprint
interface ProtectedRouteProps {
  allowedRoles?: string[];
  children: React.ReactNode;
}

export const ProtectedRoute = ({ allowedRoles, children }: ProtectedRouteProps) => {
  const { user, isAuthenticated } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
};
```
