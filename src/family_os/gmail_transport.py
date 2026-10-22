"""Gmail-only GET exception boundary; never retain raw transport/auth details."""
from .errors import GmailAPIError, GmailAuthError, GmailTransportError


def transport_get(session, url, **kwargs):
    # Lazy imports preserve the core's optional Gmail dependency boundary.
    from google.auth.exceptions import GoogleAuthError, RefreshError, TransportError
    from requests.exceptions import (RequestException, HTTPError, InvalidJSONError,
        InvalidURL, InvalidHeader, InvalidSchema, MissingSchema, URLRequired,
        TooManyRedirects, SSLError, StreamConsumedError, UnrewindableBodyError)

    try:
        return session.get(url, **kwargs)
    except RefreshError:
        # Even RefreshError(retryable=True) remains a credential/auth failure here.
        raise GmailAuthError() from None
    except TransportError:
        raise GmailTransportError() from None
    except GoogleAuthError:
        raise GmailAuthError() from None
    except (HTTPError, InvalidJSONError, InvalidURL, InvalidHeader, InvalidSchema,
            MissingSchema, URLRequired, TooManyRedirects, SSLError,
            StreamConsumedError, UnrewindableBodyError):
        # Deterministic request/configuration or response errors are not network retries.
        raise GmailAPIError() from None
    except RequestException:
        raise GmailTransportError() from None
