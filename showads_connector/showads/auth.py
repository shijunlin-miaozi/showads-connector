import requests
import time
import logging
from . import errors as err

logger = logging.getLogger(__name__)

class AuthClient:
    """
    AuthClient: fetches and caches the /auth token.
    - Adds "Authorization: Bearer <token>" header for API calls.
    - Proactively refreshes near expiry (refresh threshold defaults to 23h).
    - Lets the caller refresh once on a 401 to avoid refresh loops.
    """
    def __init__(
        self,
        base_url: str,
        project_key: str,
        *, 
        session: requests.Session | None = None,
        timeout: tuple[float, float] = (3, 10),
        proactive_refresh_seconds: float = 23 * 3600  # refresh if token age ≥ 23h
    ) -> None: 
        self._base_url = base_url.rstrip("/")
        self._project_key = project_key
        self._session = session or requests.Session()
        self._timeout = timeout
        self._proactive_refresh_seconds = float(proactive_refresh_seconds)
        # token cache
        self._token: str | None = None
        self._issued_at: float = 0.0 
        
        logger.debug(
            "AuthClient init base_url=%s timeout=%s proactive_refresh_s=%s session_provided=%s",
            self._base_url, self._timeout, self._proactive_refresh_seconds, session is not None
        )
        
    # ---------- public API ------------

    def get_header(self) -> dict[str, str]:
        """ Return the Authorization header. Refresh first if no token or token is old. """
        if self._needs_refresh():
            logger.debug("Refreshing token before building header")
            self.refresh()
        # If refresh() fails, let it raise; caller should log appropriately.
        return {"Authorization": f"Bearer {self._token}"}
        
    def refresh(self) -> None:
        """
        POST {base_url}/auth with {"ProjectKey": ...}; 
        cache AccessToken on 200 or raise typed errors.
        """
        url = f"{self._base_url}/auth"
        logger.debug("POST %s", url)
        try:
            resp = self._session.post(
                url, json={"ProjectKey": self._project_key}, timeout=self._timeout)
            logger.debug("Auth response status=%s", getattr(resp, "status_code", None))
        # Wrap timeouts/DNS/connection errors into our TransportError so caller can retry uniformly.
        except requests.RequestException as e:
            logger.warning("Auth transport error: %s", e.__class__.__name__)
            raise err.from_transport(e, endpoint="/auth") from e  # keep original traceback
        
        err.raise_for_status(resp, endpoint="/auth")
        
        try:
            data = resp.json()
            token = data["AccessToken"]
        except Exception:
            logger.warning("Auth 200 but missing AccessToken; body=%r", (resp.text or "")[:120])
            raise err.UnexpectedStatus(
                "Invalid /auth response (missing or non-JSON AccessToken)",
                status=getattr(resp, "status_code", None),
                body=(resp.text or "")[:300],
                retry_after_s=None,
                endpoint="/auth",
            )
        self._token = token
        self._issued_at = time.time()
        logger.info("Auth token refreshed")

    def on_unauthorized(self) -> None:
        """ Refresh once after the caller gets a 401 on a data request. """
        logger.info("401 received by caller; refreshing token once")
        self.refresh()

    # ---------- helpers -----------

    def _needs_refresh(self) -> bool:
        """Return True if no token cached or if token age (seconds) >= proactive_refresh_seconds."""
        if self._token is None:
            logger.debug("Token refresh needed: no token cached yet")
            return True
        age = time.time() - self._issued_at
        if age >= self._proactive_refresh_seconds:
            logger.debug("Token refresh needed: age=%.1fs threshold=%.1fs", age, self._proactive_refresh_seconds)
            return True
        return False
