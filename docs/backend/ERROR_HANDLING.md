# Standardized Error Handling & Exceptions
## Enterprise Mini SOC Platform

### 1. Exception Hierarchy (`backend/app/core/exceptions.py`)

```python
class SOCBaseException(Exception):
    def __init__(self, message: str, error_code: str, status_code: int = 400):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code

class ResourceNotFoundException(SOCBaseException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} with ID '{identifier}' not found.",
            error_code="RESOURCE_NOT_FOUND",
            status_code=404
        )

class UnauthorizedActionException(SOCBaseException):
    def __init__(self, reason: str):
        super().__init__(
            message=reason,
            error_code="UNAUTHORIZED_ACTION",
            status_code=403
        )
```

---

### 2. Global Exception Middleware

```python
@app.exception_handler(SOCBaseException)
async def soc_exception_handler(request: Request, exc: SOCBaseException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": request.url.path
        }
    )
```
