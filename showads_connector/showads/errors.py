from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

MAX_BODY_CHARS = 300

# ---- exceptions ----

class ShowAdsError(Exception):
    def __init__(
        self, 
        message: str,
        *,
        status: int | None = None,
        body: str | None = None, 
        retry_after_s: float | None = None,
        endpoint: str | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.retry_after_s = retry_after_s
        self.endpoint = endpoint

class BadRequest(ShowAdsError): ...          # 400
class Unauthorized(ShowAdsError): ...        # 401
class TooManyRequests(ShowAdsError): ...     # 429
class ServerError(ShowAdsError): ...         # 5xx
class TransportError(ShowAdsError): ...      # network/timeout
class UnexpectedStatus(ShowAdsError): ...    # anything else


# ---- helpers ----

def parse_retry_after(value: str | None) -> float | None:
    """Parse Retry-After header: seconds or HTTP-date -> seconds; else None."""
    if not value:
        return None
    v = value.strip()
    if v.isdigit():
        return float(v)
    try:
        dt = parsedate_to_datetime(v)  # HTTP-date format: e.g. "Wed, 21 Oct 2015 07:28:00 GMT"
        if dt is None:
            return None
        # Convert to UTC and compute a delta
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())   # negative -> 0
    except Exception:
        return None


def raise_for_status(resp, *, endpoint: str) -> None:
    """
    If 2xx: return silently.
    Else: raise a typed error with status/body/retry_after/endpoint.
    """
    status = getattr(resp, "status_code", None)
    if status is None:
        raise UnexpectedStatus("Missing status_code on response",
                               status=None, endpoint=endpoint, body=None, retry_after_s=None)

    if 200 <= status < 300:
        return

    body = (getattr(resp, "text", "") or "")[:MAX_BODY_CHARS]
    headers = getattr(resp, "headers", {}) or {}
    retry_after_s = parse_retry_after(headers.get("Retry-After"))

    if status == 400:
        raise BadRequest("Bad request", status=status, body=body,
                         retry_after_s=retry_after_s, endpoint=endpoint)
    if status == 401:
        raise Unauthorized("Unauthorized", status=status, body=body,
                           retry_after_s=retry_after_s, endpoint=endpoint)
    if status == 429:
        raise TooManyRequests("Too Many Requests", status=status, body=body,
                              retry_after_s=retry_after_s, endpoint=endpoint)
    if 500 <= status < 600:
        raise ServerError("Server error", status=status, body=body,
                          retry_after_s=retry_after_s, endpoint=endpoint)

    raise UnexpectedStatus(f"Unexpected status {status}", status=status, body=body,
                           retry_after_s=retry_after_s, endpoint=endpoint)

def from_transport(exc: Exception, *, endpoint: str) -> TransportError:
    """Wrap network/timeout errors into a TransportError with context.
    convert low-level errors (timeouts, DNS failures, connection resets) into typed exception
    so the client can handle them uniformly (retry)
    """
    return TransportError(f"Transport error: {exc.__class__.__name__}: {exc}",
                          status=None, body=None, retry_after_s=None, endpoint=endpoint)




