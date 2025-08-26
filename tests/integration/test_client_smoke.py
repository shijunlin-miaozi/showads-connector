"""
Smoke tests for AuthClient ↔ ShowAdsClient wiring.

Note: not full integration tests — HTTP calls to /auth and /banners/show are
stubbed with `responses`. These tests exercise the end-to-end flow
(token fetch, header injection, 401→refresh→retry) without real network calls.
"""

import time
import responses

from showads_connector.showads.auth import AuthClient
from showads_connector.showads.client import ShowAdsClient

BASE = "https://api.example.test"

@responses.activate
def test_auth_then_single_200_header_injected():
    # 1) No token yet → /auth 200 → /banners/show 200
    responses.add(responses.POST, f"{BASE}/auth", json={"AccessToken": "T1"}, status=200)
    responses.add(responses.POST, f"{BASE}/banners/show", json={}, status=200)

    auth = AuthClient(base_url=BASE, project_key="mykey")
    client = ShowAdsClient(base_url=BASE, auth=auth, timeout_single=(0.01, 0.01), timeout_bulk=(0.01, 0.01))

    ok = client.send_single("cookie", 42)   # send_single->_post_with_retry->_auth.get_header()->_needs_refresh()(no token)->refresh()(got token)->post->200
    assert ok is True
    # Verify exactly two HTTP calls: /auth then /banners/show
    assert len(responses.calls) == 2
    assert responses.calls[0].request.url.endswith("/auth")
    assert responses.calls[1].request.url.endswith("/banners/show")
    # Header injected on the data call
    assert responses.calls[1].request.headers.get("Authorization") == "Bearer T1"

@responses.activate
def test_single_401_then_refresh_then_200():
    # Initialize auth with a recent but invalid token so get_header() won’t pre-refresh
    auth = AuthClient(base_url=BASE, project_key="mykey")
    auth._token = "OLD"
    auth._issued_at = time.time()  # fresh enough to skip proactive refresh

    client = ShowAdsClient(base_url=BASE, auth=auth, timeout_single=(0.01, 0.01), timeout_bulk=(0.01, 0.01))

    # Sequence: first data call 401 → refresh (/auth 200 T2) → retry 200
    responses.add(responses.POST, f"{BASE}/banners/show", json={}, status=401)
    responses.add(responses.POST, f"{BASE}/auth", json={"AccessToken": "T2"}, status=200)
    responses.add(responses.POST, f"{BASE}/banners/show", json={}, status=200)

    ok = client.send_single("cookie", 7)    # send_single->_post_with_retry->_auth.get_header()(invalid token)->post->401->_auth.on_unauthorized()->refresh()(got valid token)->post->200
    assert ok is True

    # Three calls total: show(401), auth(200), show(200)
    assert len(responses.calls) == 3
    assert responses.calls[0].request.url.endswith("/banners/show")
    assert responses.calls[1].request.url.endswith("/auth")
    assert responses.calls[2].request.url.endswith("/banners/show")

    # The retry must use the refreshed token
    assert responses.calls[2].request.headers.get("Authorization") == "Bearer T2"

