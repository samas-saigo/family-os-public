"""Safe Outlook categories; never include provider responses or cursor URLs."""
from .errors import IngestionError


class OutlookError(IngestionError):
    pass


class OutlookIdentityError(OutlookError):
    def __init__(self):
        super().__init__("Outlook identity mismatch or missing; register the intended sign-in username explicitly")


class OutlookAuthError(OutlookError):
    def __init__(self):
        super().__init__("Outlook authentication/keyring unavailable; explicitly reconnect with Mail.ReadBasic")


class OutlookPolicyError(OutlookError):
    def __init__(self):
        super().__init__("Outlook consent/tenant policy rejected read-basic access; check app registration and permissions")


class OutlookResyncRequiredError(OutlookError):
    def __init__(self, folder_id=None):
        self.folder_id = folder_id  # Structured recovery hint; never printed in the safe message.
        super().__init__("Outlook folder/account resync required; saved cursor retained. See docs/outlook.md")


class OutlookAPIError(OutlookError):
    def __init__(self, status=None):
        self.status = status
        category = "retryable" if status is None or status == 429 or status >= 500 else "request rejected"
        super().__init__(f"Outlook {category}; retry or check read-basic connection/configuration")
