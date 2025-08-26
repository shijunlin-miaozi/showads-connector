import pytest
import responses
import requests

from showads_connector.showads.auth import AuthClient
from showads_connector.showads import errors as err

BASE = "https://api.example.test"   # test base URL (no actual network call will be made)

@responses.activate     # patches requests, all HTTP calls are intercepted by the responses library (no real I/O)
def test_get_header_refreshes_when_no_token():
    responses.add(
        responses.POST, f"{BASE}/auth",
        json={"AccessToken": "T1"}, status=200,
    )    # register a fake endpoint, simulates the auth server
    c = AuthClient(base_url=BASE, project_key="k")  # create an auth client (no token cached yet)
    header = c.get_header()
    assert header == {"Authorization": "Bearer T1"}
    assert len(responses.calls) == 1    # confirms no extra/duplicate requests

@responses.activate
def test_get_header_refreshes_when_old_token():
    # First call gives T1; second call gives T2
    responses.add(responses.POST, f"{BASE}/auth", json={"AccessToken": "T1"}, status=200)
    c = AuthClient(base_url=BASE, project_key="k", proactive_refresh_seconds=1)
    # First header -> fetch T1
    assert c.get_header()["Authorization"] == "Bearer T1"

    # Make token "old" so it refreshes again
    c._issued_at = 0.0
    responses.add(responses.POST, f"{BASE}/auth", json={"AccessToken": "T2"}, status=200)
    assert c.get_header()["Authorization"] == "Bearer T2"

@responses.activate
def test_refresh_400_maps_to_bad_request():
    responses.add(
        responses.POST, f"{BASE}/auth",
        json={"error": "bad key"}, status=400,
    )
    c = AuthClient(base_url=BASE, project_key="k")
    with pytest.raises(err.BadRequest):
        c.refresh()

def test_refresh_transport_error_is_wrapped(monkeypatch):   # monkeypatch fixture lets you temporarily modify attributes (like functions) during the test
    c = AuthClient(base_url=BASE, project_key="k")
    def boom(*a, **kw):     # stub function that accepts any positional/keyword args
        raise requests.ConnectionError("no route to host")  # simulates a network failure during POST
    monkeypatch.setattr(c._session, "post", boom)   # replace the POST on requests.Session with boom fn
    with pytest.raises(err.TransportError):
        c.refresh()     # session.post(...)->boom->ConnectionError->RequestException->TransportError

@responses.activate
def test_refresh_bad_json_raises_unexpected_status():
    # 200 but missing AccessToken -> should raise UnexpectedStatus
    responses.add(responses.POST, f"{BASE}/auth", json={"nope": "x"}, status=200)
    c = AuthClient(base_url=BASE, project_key="k")
    with pytest.raises(err.UnexpectedStatus):
        c.refresh()
