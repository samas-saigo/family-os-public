"""Deterministic MSAL sign-in username identity; no Gmail or alias rewriting."""
from .outlook_errors import OutlookIdentityError


def outlook_identity(value):
    if not isinstance(value, str):
        raise OutlookIdentityError()
    identity = value.strip().casefold()
    if identity.count("@") != 1 or any(char.isspace() for char in identity):
        raise OutlookIdentityError()
    if not all(identity.split("@")):
        raise OutlookIdentityError()
    return identity


def require_outlook_account(account):
    if account.provider != "outlook" or not account.enabled:
        raise OutlookIdentityError()
    return outlook_identity(account.external_account)
