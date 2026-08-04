# Backend Authentication & Authorization Framework
## Enterprise Mini SOC Platform

### 1. OAuth2 / JWT Implementation Blueprint

```python
# JWT Payload Structure
{
  "sub": "usr-uuid-102938",
  "username": "soc_analyst_01",
  "role": "SOC_Analyst_T2",
  "permissions": ["alerts:read", "incidents:write", "soar:request"],
  "exp": 1722765000,
  "iat": 1722764100
}
```

---

### 2. FastAPI Role Dependency (`deps.py`)

```python
def require_roles(allowed_roles: List[str]):
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{current_user.role}' lacks permission."
            )
        return current_user
    return role_checker
```
