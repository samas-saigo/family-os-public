"""Mailbox identity policy shared by registry and Gmail connection boundaries."""


def mailbox_identity(value: str | None) -> str:
    if not isinstance(value, str):
        raise ValueError("Gmail requires an explicitly registered mailbox address")
    address = value.strip().casefold()
    if address.count("@") != 1 or any(char.isspace() for char in address):
        raise ValueError("Gmail requires a mailbox address")
    local, domain = address.split("@")
    if domain in {"gmail.com", "googlemail.com"}:
        domain = "gmail.com"
        local = local.split("+", 1)[0].replace(".", "")
    if not local or not domain:
        raise ValueError("Gmail requires a mailbox address")
    return f"{local}@{domain}"
