# Frontend SPA Architecture & UI Specification
## Enterprise Mini SOC Platform

### 1. Technology Stack Selection
- **Core Framework:** React 18+ with Vite compiler & TypeScript strictly configured (`strict: true`).
- **UI Components & Styling:** Tailwind CSS + Shadcn UI (Radix UI primitives), Lucide React icons.
- **Data Fetching & Cache:** TanStack Query v5 for server-state caching, automatic refetching, and optimistic UI updates.
- **Client State:** Zustand for global state (Theme, Auth Session, Notification toast queue).
- **Charts & Visualization:** Apache ECharts / Recharts for real-time threat maps and metrics.

---

### 2. Frontend Directory Blueprint (`frontend/src/`)

```
frontend/src/
├── assets/                 # SVGs, Static Images, Fonts
├── components/             # Reusable UI Component Library
│   ├── ui/                 # Shadcn UI primitives (Button, Dialog, Badge, Card, Table)
│   ├── common/             # Header, Sidebar, StatCard, LoadingSpinner, ErrorBoundary
│   ├── alerts/             # AlertTable, AlertFilter, AlertDetailsModal, ThreatBadge
│   ├── incidents/          # IncidentKanban, SLAClock, TicketDetailsModal
│   ├── soar/               # PlaybookCard, ApprovalGateModal, ExecutionLogViewer
│   └── ai/                 # AISummaryPanel, RiskGaugeChart
│
├── pages/                  # Page Container Views
│   ├── Login.tsx           # Authentication page
│   ├── Dashboard.tsx       # Executive SOC Overview Dashboard
│   ├── LiveAlerts.tsx      # Real-time WebSocket Alert Grid
│   ├── Incidents.tsx       # Incident Ticket Kanban & Management
│   ├── Playbooks.tsx       # SOAR Automation & Approval Center
│   ├── Assets.tsx          # Infrastructure & Agent Inventory
│   └── AuditLogs.tsx       # System Audit Log Search
│
├── hooks/                  # Custom React Hooks
│   ├── useAuth.ts          # Auth login/logout & RBAC checks
│   ├── useWebSocket.ts     # Real-time WebSocket reconnection & event listener
│   ├── useAlerts.ts        # TanStack Query alert hooks
│   └── useIncidents.ts     # TanStack Query incident hooks
│
├── services/               # Axios API Client Modules
│   ├── api.ts              # Axios instance with auth interceptor
│   ├── authService.ts      # Auth REST endpoints
│   ├── alertService.ts     # Alert REST endpoints
│   └── soarService.ts      # Playbook REST endpoints
│
├── stores/                 # Zustand Stores
│   ├── useAuthStore.ts     # Current user & JWT token state
│   ├── useThemeStore.ts    # Dark/Light theme state
│   └── useToastStore.ts    # Toast notification queue
│
├── types/                  # TypeScript Interfaces & DTOs
│   ├── alert.ts            # Alert & ThreatIntel DTOs
│   ├── incident.ts         # Incident & SLA DTOs
│   └── user.ts             # User & Role DTOs
│
└── routes/                 # Protected Router Setup
    ├── AppRoutes.tsx       # React Router v6 route definitions
    └── ProtectedRoute.tsx  # Auth & RBAC Route Guard wrapper
```
