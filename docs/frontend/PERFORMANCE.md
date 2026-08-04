# Frontend Performance Optimization Baseline
## Enterprise Mini SOC Platform

### 1. Performance Guidelines
- **Virtualization for High-Volume Grids:** Use TanStack Virtual (`@tanstack/react-virtual`) for alert logs exceeding 100 items to guarantee smooth 60 FPS scrolling.
- **Code Splitting & Lazy Loading:** Lazy load modal dialogs and secondary page routes via `React.lazy()` and `<Suspense>`.
- **WebSocket Throttling:** Buffer inbound WebSocket alerts into 250ms batch window to minimize component re-renders.
