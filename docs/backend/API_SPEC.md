# Backend OpenAPI Route Definitions
## Enterprise Mini SOC Platform

### 1. OpenAPI Route Map

```python
# Auth Routes
POST /api/v1/auth/login            # Authenticate user & issue JWT
POST /api/v1/auth/refresh          # Refresh JWT access token
GET  /api/v1/auth/me               # Fetch current authenticated user profile

# Alert Routes
GET  /api/v1/alerts                # Paginated list of security alerts
GET  /api/v1/alerts/{id}           # Detailed alert view
WS   /api/v1/alerts/ws             # Live alert WebSocket stream

# Incident Routes
GET  /api/v1/incidents             # List incident tickets
POST /api/v1/incidents             # Create new incident ticket
GET  /api/v1/incidents/{id}        # Incident details
PATCH /api/v1/incidents/{id}       # Update incident status/assignee

# SOAR Routes
POST /api/v1/soar/playbooks/execute # Initiate playbook
GET  /api/v1/soar/approvals        # List pending approval gates
POST /api/v1/soar/approvals/{id}/decision # Approve or reject playbook action
```
