# State Management Architecture (Zustand + TanStack Query)
## Enterprise Mini SOC Platform

### 1. Client State (Zustand)
- `useAuthStore`: Manages authenticated User object, accessToken in memory (HTTP-only refresh token in cookie), and logout routine.
- `useThemeStore`: Manages dark/light theme switching with system preference detection.

### 2. Server State (TanStack Query)
- Query caching with `staleTime: 10000` (10s) for live alert data.
- Automatic query invalidation on mutation (e.g. updating incident status invalidates `["incidents"]` query).
