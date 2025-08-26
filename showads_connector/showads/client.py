import requests
import time
import random
import logging
from . import errors as err
from .auth import AuthClient
from showads_connector.types import BatchResult

logger = logging.getLogger(__name__)

class ShowAdsClient:
    def __init__(
        self,
        base_url: str,
        auth: AuthClient,
        *,
        session: requests.Session | None = None,
        timeout_single: tuple[float, float] = (3, 10),
        timeout_bulk: tuple[float, float] = (3, 15),
        max_batch: int = 1000,
        max_retries: int = 3,
        backoff_base_s: float = 0.5,
        backoff_cap_s: float = 8.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = auth
        self._session = session or requests.Session()
        self._timeout_single = timeout_single
        self._timeout_bulk = timeout_bulk
        self._max_batch = max_batch
        self._max_retries = max_retries
        self._backoff_base_s = backoff_base_s
        self._backoff_cap_s = backoff_cap_s
        
        logger.debug(
            "Client init base_url=%s timeouts_single=%s timeouts_bulk=%s "
            "max_batch=%d max_retries=%d backoff(base=%.2f cap=%.2f) session_provided=%s",
            self._base_url, self._timeout_single, self._timeout_bulk,
            self._max_batch, self._max_retries, self._backoff_base_s, self._backoff_cap_s,
            session is not None,
        )
    # ---------- public API ------------

    def send_single(self, cookie: str, banner_id: int) -> bool:
        """
        Send one item via POST /banners/show.
        - Returns True on 2xx.
        - Returns False only for 400 (bad payload for that item).
        - Any other failure is raised to the caller (401-after-refresh, 429/5xx after retries, transport).
        """
        endpoint = "/banners/show"
        payload = {"VisitorCookie": cookie, "BannerId":banner_id}
        try:
            self._post_with_retry(endpoint, payload, timeout=self._timeout_single)
            return True
        except err.BadRequest:
            logger.warning("Single 400 at %s banner_id=%d (bad item payload).", endpoint, banner_id)
            return False
        
    def send_bulk(self, items: list[dict[str, object]]) -> BatchResult:
        """
        Send up to max_batch items via POST /banners/show/bulk.
        - 2xx → {"sent": len(items), "failed": []}
        - 400 → do not retry; fall back to per-item sends to identify bad rows.
        - 429/5xx/transport → retried inside _post_with_retry; if still failing per-item, record reason.
        """
        if len(items) > self._max_batch:
            logger.error("Batch too large: size=%d > max_batch=%d", len(items), self._max_batch)
            raise ValueError(f"batch too large: {len(items)} > {self._max_batch}")
        
        endpoint = "/banners/show/bulk"
        payload = {"Data": items}
        logger.debug("POST %s batch_size=%d", endpoint, len(items))
        try:
            self._post_with_retry(endpoint, payload, timeout=self._timeout_bulk)
            logger.debug("Bulk 2xx sent=%d", len(items))
            return {"sent": len(items), "failed": []}
        except err.BadRequest:  
            # Fallback to per-item request: identify bad rows
            logger.warning(
                "Bulk 400 at %s (batch_size=%d). Falling back to per-item sends.",
                endpoint, len(items)
            )
            failed, sent = [], 0
            for it in items:
                try:
                    ok = self.send_single(str(it["VisitorCookie"]), int(it["BannerId"]))
                    if ok:
                        sent += 1
                    else:
                        # Only 400 returns False from send_single
                        failed.append({
                            "item": {"VisitorCookie": "***redacted***", "BannerId": it.get("BannerId")},
                            "reason": "BAD_REQUEST", 
                            "status": 400
                        })
                except err.Unauthorized:
                    # refresh already attempted inside send_single; treat as fatal
                    raise
                except (err.TooManyRequests, err.ServerError, err.TransportError) as e:
                    # retries already exhausted in send_single; record and continue
                    logger.debug("Per-item failed banner_id=%s reason=%s status=%s",
                            it.get("BannerId"), e.__class__.__name__, getattr(e, "status", None))
                    failed.append({
                        "item": {"VisitorCookie": "***redacted***", "BannerId": it.get("BannerId")}, 
                        "reason": e.__class__.__name__, 
                        "status": e.status
                    })
                    
            # summary of the fallback
            logger.warning(
                "Per-item fallback done: sent=%d, failed=%d (batch_size=%d).",
            sent, len(failed), len(items)
            )        
            return {"sent": sent, "failed": failed}


    # ---------- helpers -----------

    def _compute_backoff(self, *, attempt: int, retry_after_s: float | None) -> float:
        """
        Compute sleep before the next retry:
        - If server provided Retry-After, honor it (but cap).
        - Else exponential backoff (base * 2^attempt), capped, with ±10% jitter to avoid thundering herd.
        """
        if retry_after_s is not None:
            return min(retry_after_s, self._backoff_cap_s)

        # Exponential backoff: base * 2^attempt, capped, with jitter
        delay = min(self._backoff_base_s * (2 ** attempt), self._backoff_cap_s)
        # Add ±10% jitter to avoid thundering herd
        jitter = delay * (0.1 * (random.random() - 0.5) * 2)
        return max(0.0, delay + jitter)

        
    def _post_with_retry(self, path: str, payload: dict | list, *, timeout: tuple[float, float]) -> requests.Response:
        """
        Core HTTP engine:
        - Adds Authorization header from AuthClient.
        - Maps non-2xx to typed errors.
        - On 401: refresh once, then retry (prevents refresh loops).
        - On 429/5xx/transport: exponential backoff with jitter (honor Retry-After), up to max_retries.
        """
        attempted_refresh = False
        attempt = 0  # counts retryable errors (429/5xx/transport), NOT the 401 refresh
        url = self._base_url + path
        
        while True:
            headers = self._auth.get_header()
            try:
                resp = self._session.post(url, json=payload, headers=headers, timeout=timeout)
                err.raise_for_status(resp, endpoint=path)  # 2xx returns; otherwise raises typed error
                logger.debug("Success %s status=%d", path, getattr(resp, "status_code", None))
                return resp  # success
            
            except err.Unauthorized:
                if attempted_refresh:
                    # Avoid refresh loops: only refresh once per call
                    logger.error("Second 401 after refresh on %s; giving up.", path)
                    raise
                self._auth.on_unauthorized()    # refresh once
                attempted_refresh = True
                continue
            
            except (err.TooManyRequests, err.ServerError, err.TransportError) as ex:
                # retryable; fall through to backoff logic below
                retry_exc = ex
            
            except requests.RequestException as ex:
                # Convert to TransportError and retry like other retryables
                retry_exc = err.from_transport(ex, endpoint=path)
                logger.warning("Transport error on %s: %s", path, retry_exc.__class__.__name__)

            # common retry/backoff path for retryable errors (429/5xx/transport)
            if attempt >= self._max_retries:
                logger.error("Retries exhausted on %s (%s).", path, retry_exc.__class__.__name__)
                raise retry_exc
            sleep_s = self._compute_backoff(
                attempt=attempt,
                retry_after_s=getattr(retry_exc, "retry_after_s", None)
            )
            logger.warning(
                "Retrying %s attempt=%d sleep=%.2fs (%s)",
                path, attempt + 1, sleep_s, retry_exc.__class__.__name__
            )
            time.sleep(sleep_s)
            attempt += 1