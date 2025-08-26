import requests
import pytest
from datetime import datetime, timedelta, timezone
from email.utils import formatdate

from showads_connector.showads.errors import (
    parse_retry_after, raise_for_status, from_transport,
    BadRequest, TooManyRequests, ServerError, ShowAdsError
)

class FakeResp:  # a stand-in for a requests.Response
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

# --- parse_retry_after ---

def test_retry_after_numeric_and_invalid():
    assert parse_retry_after("10") == 10.0
    assert parse_retry_after("not-a-date") is None
    assert parse_retry_after(None) is None

def test_retry_after_http_date_future_is_positive():
    future = datetime.now(timezone.utc) + timedelta(seconds=30)
    v = formatdate(future.timestamp(), usegmt=True)     # Format future time as an HTTP date
    secs = parse_retry_after(v)
    assert secs is not None and secs > 0

# --- raise_for_status ---

def test_2xx_no_raise():
    assert raise_for_status(FakeResp(204), endpoint="/ok") is None  # 2xx must not raise.

def test_400_bad_request():
    with pytest.raises(BadRequest):
        raise_for_status(FakeResp(400, "bad"), endpoint="/x")

def test_429_with_retry_after():
    with pytest.raises(TooManyRequests) as excinfo:
        raise_for_status(FakeResp(429, headers={"Retry-After": "5"}), endpoint="/rate")
    assert excinfo.value.retry_after_s == 5.0

def test_5xx_server_error():
    with pytest.raises(ServerError):
        raise_for_status(FakeResp(503, "down"), endpoint="/x")

# --- from_transport ---

def test_from_transport_wraps_requests_exc():
    e = from_transport(requests.Timeout("boom"), endpoint="/auth")  # Wrap a requests timeout into TransportError
    assert isinstance(e, ShowAdsError)
    assert e.endpoint == "/auth"
