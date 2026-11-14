"""Shared helpers for HTTP providers: retries with backoff, polling, clear errors."""
from __future__ import annotations

import time
from typing import Callable

import httpx

from .. import config


class ProviderError(RuntimeError):
    """A provider failed in a way the user can act on (message says what to do)."""


class MissingCredentials(ProviderError):
    pass


def require(key: str, provider: str) -> str:
    val = config.env(key)
    if not val:
        raise MissingCredentials(f"{provider} needs {key}. Add it in the dashboard's API Settings page or in .env "
                                 f"(see docs/API_SETUP.md). No request was sent.")
    return val


def request(method: str, url: str, retries: int = 3, timeout: float = 120, ok=(200, 201, 202), **kw) -> httpx.Response:
    last = None
    for attempt in range(retries + 1):
        try:
            r = httpx.request(method, url, timeout=timeout, follow_redirects=True, **kw)
        except httpx.HTTPError as e:
            last = f"network error: {e}"
        else:
            if r.status_code in ok:
                return r
            if r.status_code in (401, 403):
                raise ProviderError(f"{url.split('/')[2]} rejected the credentials ({r.status_code}): {r.text[:300]}")
            if r.status_code == 402:
                raise ProviderError(f"{url.split('/')[2]} says payment/credits are required (402): {r.text[:300]}")
            if r.status_code in (400, 404, 422):
                raise ProviderError(f"{url.split('/')[2]} rejected the request ({r.status_code}): {r.text[:500]}")
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code == 429:
                time.sleep(float(r.headers.get("retry-after", 0) or 0) or 5 * (attempt + 1))
                continue
        time.sleep(2 ** attempt * 2)
    raise ProviderError(f"{url.split('/')[2]} failed after {retries + 1} attempts: {last}")


def poll(fetch: Callable[[], dict], done: Callable[[dict], bool], failed: Callable[[dict], str | None],
         timeout: float = 900, interval: float = 5) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        data = fetch()
        err = failed(data)
        if err:
            raise ProviderError(err)
        if done(data):
            return data
        time.sleep(interval)
    raise ProviderError(f"timed out after {int(timeout)}s waiting for the provider")


def download(url: str, dest, timeout: float = 300):
    r = request("GET", url, timeout=timeout)
    dest.write_bytes(r.content)
    return dest
