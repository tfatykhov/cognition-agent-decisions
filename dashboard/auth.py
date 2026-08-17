"""Basic authentication for Flask routes."""
import secrets
import time
from collections import OrderedDict
from collections.abc import Callable
from functools import wraps
from os import environ
from threading import Lock
from typing import Any

from flask import Response, request

from config import Config

# Failed-attempt throttling. Process-local by design: the dashboard is a small
# single-service app, and a shared store would pull in Redis for one counter.
# Under `gunicorn -w N` each worker throttles independently, so the effective
# limit is N * MAX_FAILED_ATTEMPTS per window — still a hard cap on brute force,
# just a looser one than the constant suggests.
MAX_FAILED_ATTEMPTS = 10
LOCKOUT_SECONDS = 300

# Number of trusted reverse proxies in front of the dashboard. Behind a proxy
# every request carries the proxy's address in `remote_addr`, so all users would
# share one throttle bucket and ten failures by a single attacker would lock out
# everyone. Set DASHBOARD_TRUSTED_PROXIES to the hop count to key on the real
# client instead. Left at 0 the header is ignored entirely — trusting an
# unvalidated X-Forwarded-For would let any caller spoof a fresh bucket per
# request and skip throttling altogether.
TRUSTED_PROXIES = int(environ.get("DASHBOARD_TRUSTED_PROXIES", "0"))

# Hard capacity for the failure table. Sweeping expired entries alone is not
# enough: an attacker presenting many distinct client keys inside one window has
# nothing expired to reclaim, so the table would keep growing and every insert
# past the sweep point would also rescan it — memory growth plus CPU
# amplification. At capacity the oldest entry is evicted instead.
#
# Eviction can in principle discard a real lockout, but that is inherent to any
# bounded cache and is strictly better than unbounded growth: an attacker able
# to evict entries must already be able to make MAX_TRACKED_CLIENTS distinct
# failed attempts, which the eviction itself does nothing to help them with.
MAX_TRACKED_CLIENTS = 4096

_failed: OrderedDict[str, tuple[int, float]] = OrderedDict()
_failed_lock = Lock()


def _client_key() -> str:
    """Identify the caller for throttling purposes.

    Uses `remote_addr` unless DASHBOARD_TRUSTED_PROXIES says a known number of
    proxies sit in front, in which case the corresponding X-Forwarded-For entry
    is taken instead — counting from the right, since only the rightmost hops
    were appended by infrastructure we control.
    """
    if TRUSTED_PROXIES > 0:
        forwarded = request.headers.get("X-Forwarded-For", "")
        chain = [part.strip() for part in forwarded.split(",") if part.strip()]
        if len(chain) >= TRUSTED_PROXIES:
            return chain[-TRUSTED_PROXIES]
    return request.remote_addr or "unknown"


def is_locked_out(key: str, now: float | None = None) -> bool:
    """Whether this client has exceeded the failed-attempt budget."""
    now = time.monotonic() if now is None else now
    with _failed_lock:
        entry = _failed.get(key)
        if entry is None:
            return False
        count, first_seen = entry
        if now - first_seen > LOCKOUT_SECONDS:
            del _failed[key]
            return False
        return count >= MAX_FAILED_ATTEMPTS


def record_failure(key: str, now: float | None = None) -> None:
    """Count a failed authentication attempt against this client."""
    now = time.monotonic() if now is None else now
    with _failed_lock:
        count, first_seen = _failed.get(key, (0, now))
        if now - first_seen > LOCKOUT_SECONDS:
            count, first_seen = 0, now
        _failed[key] = (count + 1, first_seen)
        # Insertion order tracks recency of first failure, so the oldest entry is
        # the front of the OrderedDict. Evicting one per insert keeps the table at
        # a fixed ceiling in O(1) — no scan, expired or not.
        _failed.move_to_end(key)
        while len(_failed) > MAX_TRACKED_CLIENTS:
            _failed.popitem(last=False)


def reset_failures(key: str) -> None:
    """Clear the failure counter after a successful login."""
    with _failed_lock:
        _failed.pop(key, None)


def check_auth(username: str | None, password: str | None, config: Config) -> bool:
    """Validate credentials against config.

    Both comparisons use `secrets.compare_digest` so the runtime does not leak
    how many leading characters matched. Both are always evaluated — returning
    early on a username mismatch would reintroduce the timing signal that using
    compare_digest is meant to remove.

    An empty configured password never matches. That is defence in depth: the
    real guard is the import-time check in app.py, but this keeps the predicate
    itself safe if it is ever called from somewhere that skipped it.

    Args:
        username: Provided username, or None when no credentials were sent
        password: Provided password, or None when no credentials were sent
        config: Config instance with expected credentials

    Returns:
        True if credentials match
    """
    if not config.dashboard_pass:
        return False

    user_ok = secrets.compare_digest(
        (username or "").encode("utf-8"),
        config.dashboard_user.encode("utf-8"),
    )
    pass_ok = secrets.compare_digest(
        (password or "").encode("utf-8"),
        config.dashboard_pass.encode("utf-8"),
    )
    return user_ok and pass_ok


def authenticate() -> Response:
    """Return 401 response requesting authentication."""
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="CSTP Dashboard"'},
    )


def requires_auth(config: Config) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory for Basic Auth protection.
    
    Args:
        config: Config instance with credentials
        
    Returns:
        Decorator that protects routes with Basic Auth
        
    Example:
        auth = requires_auth(config)
        
        @app.route("/protected")
        @auth
        def protected_route():
            return "secret"
    """
    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            key = _client_key()
            if is_locked_out(key):
                return Response(
                    "Too many failed authentication attempts",
                    429,
                    {"Retry-After": str(LOCKOUT_SECONDS)},
                )
            auth = request.authorization
            if not auth or not check_auth(auth.username, auth.password, config):
                record_failure(key)
                return authenticate()
            reset_failures(key)
            return f(*args, **kwargs)
        return decorated
    return decorator
