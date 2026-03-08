"""Authentication module for Employee Help.

Provides OAuth 2.0 / OIDC integration with Google and Microsoft.
No email/password. No local credential storage.
"""

from employee_help.auth.models import AuthSession, Membership, Organization, User
from employee_help.auth.provider import AuthError, AuthProvider, AuthResult
from employee_help.auth.session import SessionManager
from employee_help.auth.storage import AuthStorage
from employee_help.auth.tokens import AccessTokenClaims

__all__ = [
    "AccessTokenClaims",
    "AuthError",
    "AuthProvider",
    "AuthResult",
    "AuthSession",
    "AuthStorage",
    "Membership",
    "Organization",
    "SessionManager",
    "User",
]
