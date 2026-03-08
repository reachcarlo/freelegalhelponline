"""Authentication module for Employee Help.

Provides OAuth 2.0 / OIDC integration with Google and Microsoft.
No email/password. No local credential storage.
"""

from employee_help.auth.models import AuthSession, Membership, Organization, User
from employee_help.auth.provider import AuthError, AuthProvider, AuthResult

__all__ = [
    "AuthError",
    "AuthProvider",
    "AuthResult",
    "AuthSession",
    "Membership",
    "Organization",
    "User",
]
