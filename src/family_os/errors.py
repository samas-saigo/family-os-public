"""Public error categories. Messages never contain provider exception text."""


class IngestionError(RuntimeError):
    """Safe ingestion failure; the failed page does not advance its cursor."""


class ConcurrentSyncError(IngestionError):
    """Another run advanced this account. Retry from the persisted cursor."""


class GmailError(IngestionError):
    """Safe Gmail connector/authentication failure."""


class ResyncRequiredError(GmailError):
    def __init__(self):
        super().__init__("Gmail resync required; saved cursor retained. See docs/gmail.md")


class MailboxIdentityError(GmailError):
    def __init__(self):
        super().__init__("Gmail mailbox identity mismatch or missing; register the intended mailbox explicitly")


class GmailAuthError(GmailError):
    def __init__(self):
        super().__init__("Gmail authentication/keyring unavailable; explicitly connect with gmail.readonly")


class GmailTransportError(GmailError):
    """Internal category consumed by the bounded HTTP GET retry loop."""
    def __init__(self):
        super().__init__("Gmail transport unavailable")


class GmailAPIError(GmailError):
    def __init__(self, status=None, *, transient_403=False):
        self.status = status
        category = "retryable" if (status is None or status == 429 or (status and status >= 500)
            or (status == 403 and transient_403)) else "request rejected"
        super().__init__(f"Gmail {category}; retry or check read-only connection/configuration")
