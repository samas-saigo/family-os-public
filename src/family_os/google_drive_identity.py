"""Registered email binding: trim/casefold only, no Google alias inference."""
from .google_drive_errors import DriveIdentityError


def drive_identity(value):
    if not isinstance(value, str):
        raise DriveIdentityError()
    address = value.strip().casefold()
    if len(address) > 4096 or address.count("@") != 1 or not all(address.split("@")) or any(c.isspace() or ord(c) < 32 for c in address):
        raise DriveIdentityError()
    return address


def require_drive_account(account):
    if account.provider != "google_drive" or not account.enabled:
        raise DriveIdentityError()
    return drive_identity(account.external_account)
