import pytest
import responses

from showads_connector.showads.client import ShowAdsClient
from showads_connector.showads import errors as err

BASE = "https://api.example.test"

class FakeAuth:
    """Minimal auth stub: returns a header; counts refresh calls."""
    def __init__(self):
        self.refresh_calls = 0
    def get_header(self) -> dict[str, str]:
        return {"Authorization": "Bearer T"}
    def on_unauthorized(self) -> None:
        self.refresh_calls += 1

def make_client(max_retries=3):
    return ShowAdsClient(
        base_url=BASE,
        auth=FakeAuth(),
        max_retries=max_retries,
        timeout_single=(0.01, 0.01),
        timeout_bulk=(0.01, 0.01),
        backoff_base_s=0.0,
        backoff_cap_s=0.0,  # Small timeouts, zero backoff -> fast tests
    )

# --- 401 → refresh once → retry succeeds ---
@responses.activate
def test_single_401_then_200_triggers_one_refresh(): 
    c = make_client()
    # 401 then 200 for /banners/show
    responses.add(responses.POST, f"{BASE}/banners/show", json={}, status=401)
    responses.add(responses.POST, f"{BASE}/banners/show", json={}, status=200)

    ok = c.send_single("cookie", 7) # send_single->_post_with_retry->401->on_unauthorized()->retry->200
    assert ok is True
    assert isinstance(c._auth, FakeAuth)
    assert c._auth.refresh_calls == 1   # refreshed once after 401
    assert len(responses.calls) == 2

# --- 401 twice → refresh once then still 401 → raises ---
@responses.activate
def test_single_401_twice_raises_unauthorized():
    c = make_client(max_retries=0)  # no additional retries beyond the refresh path
    responses.add(responses.POST, f"{BASE}/banners/show", json={}, status=401)
    responses.add(responses.POST, f"{BASE}/banners/show", json={}, status=401)

    with pytest.raises(err.Unauthorized):
        c.send_single("cookie", 7)  # send_single->_post_with_retry->401->on_unauthorized()->retry->401->raise
    assert c._auth.refresh_calls == 1
    assert len(responses.calls) == 2

# --- 429 with Retry-After honored (we set cap=0 so sleep ~0) → then 200 ---
@responses.activate
def test_single_429_then_200_retries_and_succeeds(monkeypatch):
    c = make_client(max_retries=1)
    # 429 with Retry-After header, then 200
    responses.add(
        responses.POST, f"{BASE}/banners/show",
        json={}, status=429, headers={"Retry-After": "0"}
    )
    responses.add(responses.POST, f"{BASE}/banners/show", json={}, status=200)

    # Avoid real sleep to keep test fast
    monkeypatch.setattr("time.sleep", lambda s: None)

    ok = c.send_single("cookie", 7)     # send_single->_post_with_retry->429->sleep->retry->200
    assert ok is True
    assert len(responses.calls) == 2

# --- 5xx repeatedly → retries exhausted → raises ServerError ---
@responses.activate
def test_single_5xx_gives_up_after_retries(monkeypatch):
    c = make_client(max_retries=1)
    responses.add(responses.POST, f"{BASE}/banners/show", json={}, status=503)
    responses.add(responses.POST, f"{BASE}/banners/show", json={}, status=503)
    monkeypatch.setattr("time.sleep", lambda s: None)

    with pytest.raises(err.ServerError):
        c.send_single("cookie", 7)  # send_single->_post_with_retry->503->sleep->retry->503->raise

# --- bulk 400 → fallback to per-item; one 200 and one 400; cookie redacted ---
@responses.activate
def test_bulk_400_fallback_to_per_item_and_redacts_cookie(caplog):  # caplog: pytest fixture that captures the code’s log records
    c = make_client()
    items = [
        {"VisitorCookie": "AAA", "BannerId": 1},
        {"VisitorCookie": "BBB", "BannerId": 2},
    ]

    # Bulk 400 triggers fallback
    responses.add(responses.POST, f"{BASE}/banners/show/bulk", json={}, status=400)
    # Per-item: first succeeds, second 400 (send_single returns False for 400)
    responses.add(responses.POST, f"{BASE}/banners/show", json={}, status=200)
    responses.add(responses.POST, f"{BASE}/banners/show", json={}, status=400)

    with caplog.at_level("WARNING"):    # capture the warning logs
        result = c.send_bulk(items)     # send_bulk->_post_with_retry->400->fallback: send_single->first item:200(update sent)->next item:400(update failed)

    assert result["sent"] == 1
    assert len(result["failed"]) == 1
    failed_item = result["failed"][0]["item"]
    # Cookie is redacted in failures
    assert failed_item["VisitorCookie"] == "***redacted***"
    # We logged the fallback warning
    assert any("Falling back to per-item sends" in r.message for r in caplog.records)
