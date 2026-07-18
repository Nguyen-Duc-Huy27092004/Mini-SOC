# security/ package shadows security.py — re-export everything from the real module.
# This ensures `from app.core.security import X` works regardless of which takes priority.
from app.core.security_module import (  # noqa: F401
    Role,
    bearer_scheme,
    get_token_from_request,
    get_current_user,
    require_roles,
    require_password_changed,
)

# Re-export auth helpers so callers can also do `from app.core.security import hash_password`
from app.services.auth_service import (  # noqa: F401
    hash_password,
    hash_password_sync,
    verify_password,
)
