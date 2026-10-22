"""Primary CalendarList identity only; no alias, dot, or plus rewriting."""
from .google_calendar_errors import CalendarIdentityError


def calendar_identity(value):
    if not isinstance(value, str):
        raise CalendarIdentityError()
    identity = value.strip().casefold()
    if not identity or any(char.isspace() or ord(char) < 32 for char in identity) or len(identity) > 4096:
        raise CalendarIdentityError()
    return identity


def require_calendar_account(account):
    if account.provider != "google_calendar" or not account.enabled:
        raise CalendarIdentityError()
    return calendar_identity(account.external_account)
