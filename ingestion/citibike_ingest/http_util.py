"""Small HTTP GET helper with retries (standard library only)."""
from __future__ import annotations

import time
import urllib.error
import urllib.request

USER_AGENT = "citibike-jc-lakehouse/0.1 (portfolio project)"
RETRY_STATUS = {429, 500, 502, 503, 504}


def http_get(url: str, timeout: int = 60, retries: int = 3, backoff_s: float = 2.0) -> bytes:
    """GET a URL and return the body. Retries network errors and 429/5xx responses."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as err:
            body = err.read()[:300].decode("utf-8", "replace")
            last_error = RuntimeError(f"HTTP {err.code} for {url}: {body}")
            if err.code not in RETRY_STATUS:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            last_error = RuntimeError(f"Network error for {url}: {err}")
        if attempt < retries:
            time.sleep(backoff_s * attempt)
    raise last_error  # type: ignore[misc]
