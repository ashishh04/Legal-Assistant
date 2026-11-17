"""Sign-in for the web app: accounts from the user directory, password checks, sessions."""
from .service import Auth, AuthError

__all__ = ["Auth", "AuthError"]
