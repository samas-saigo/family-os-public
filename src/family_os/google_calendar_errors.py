"""Safe Calendar errors; never include provider payloads or continuation tokens."""
from .errors import IngestionError


class CalendarError(IngestionError):
    pass


class CalendarIdentityError(CalendarError):
    def __init__(self):
        super().__init__("Google Calendar identity missing or mismatched; register the intended primary calendar explicitly")


class CalendarAuthError(CalendarError):
    def __init__(self):
        super().__init__("Google Calendar authentication/keyring unavailable; explicitly connect with the two approved read-only scopes")


class CalendarPolicyError(CalendarError):
    def __init__(self):
        super().__init__("Google Calendar policy/scope rejected; check approved read-only scopes and inclusion policy")


class CalendarAPIError(CalendarError):
    def __init__(self, status=None):
        self.status = status
        category = "retryable" if status is None or status == 429 or status >= 500 else "request rejected"
        super().__init__(f"Google Calendar {category}; retry or check read-only access")


class CalendarResyncRequiredError(CalendarError):
    def __init__(self, stream="state"):
        # A routing ID is exposed only as an attribute, never in diagnostics.
        self.stream = stream
        category = "CalendarList" if stream == "calendar_list" else "event stream" if stream != "state" else "cursor"
        super().__init__(f"Google Calendar {category} resync required; saved history/cursor retained. See docs/google-calendar.md")
