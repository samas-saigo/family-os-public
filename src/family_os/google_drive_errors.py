"""Safe public Drive categories; no provider values in diagnostic messages."""
from .errors import IngestionError


class DriveError(IngestionError):
    pass


class DriveIdentityError(DriveError):
    def __init__(self):
        super().__init__("Google Drive identity missing or mismatched; register and explicitly bind the intended account")


class DriveAuthError(DriveError):
    def __init__(self):
        super().__init__("Google Drive authentication/keyring unavailable; explicitly connect with drive.metadata.readonly")


class DrivePolicyError(DriveError):
    def __init__(self):
        super().__init__("Google Drive scope/policy rejected; use only approved metadata permission and explicit Shared Drive IDs")


class SharedDriveUnavailableError(DrivePolicyError):
    def __init__(self):
        DriveError.__init__(self, "Configured Shared Drive inaccessible or not found; check explicit Drive selection and access")


class DriveAPIError(DriveError):
    def __init__(self, status=None):
        self.status = status
        category = "retryable" if status is None or status == 429 or status >= 500 else "request rejected"
        super().__init__(f"Google Drive {category}; retry or check metadata-only connection")


class DriveResponseError(DriveError):
    def __init__(self):
        super().__init__("Malformed Google Drive response; saved page retained")


class DriveResyncRequiredError(DriveError):
    def __init__(self, stream=None):
        self.stream = stream  # Non-secret routing target available programmatically, not logged.
        category = "personal stream" if stream == "user" else "Shared Drive stream" if stream else "cursor"
        super().__init__(f"Google Drive {category} resync required; history retained. See docs/google-drive.md")
