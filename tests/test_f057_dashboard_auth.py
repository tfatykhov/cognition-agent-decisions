"""F057: dashboard authentication hardening.

The defect these guard against: `config.validate()` — the only check rejecting an
empty DASHBOARD_PASS — lived in `main()`, but `dashboard/Dockerfile` runs
`gunicorn app:app`, which imports the module and never calls `main()`. So the
guard did not execute in any deployment we ship, and an unset DASHBOARD_PASS
admitted any request presenting username `admin` and an empty password.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# Flask is not installed in CI for the main suite — skip before importing anything
# that transitively pulls it in.
if importlib.util.find_spec("flask") is None:
    pytest.skip("flask not installed (CI environment)", allow_module_level=True)

_dashboard_dir = str(Path(__file__).resolve().parent.parent / "dashboard")
if _dashboard_dir not in sys.path:
    sys.path.insert(0, _dashboard_dir)

import auth  # noqa: E402
from auth import (  # noqa: E402
    LOCKOUT_SECONDS,
    MAX_FAILED_ATTEMPTS,
    check_auth,
    is_locked_out,
    record_failure,
    reset_failures,
)
from config import Config, enforce_security_config  # noqa: E402


class TestSecurityConfigEnforcement:
    def test_empty_password_is_a_security_error(self) -> None:
        cfg = Config(dashboard_pass="", cstp_token="t", secret_key="s")
        assert cfg.security_errors() == ["DASHBOARD_PASS is required"]

    def test_set_password_is_clean(self) -> None:
        cfg = Config(dashboard_pass="hunter2", cstp_token="t", secret_key="s")
        assert cfg.security_errors() == []

    def test_enforce_raises_on_empty_password(self) -> None:
        cfg = Config(dashboard_pass="", cstp_token="t", secret_key="s")
        with pytest.raises(RuntimeError, match="DASHBOARD_PASS is required"):
            enforce_security_config(cfg)

    def test_enforce_passes_with_password(self) -> None:
        cfg = Config(dashboard_pass="hunter2", cstp_token="t", secret_key="s")
        enforce_security_config(cfg)  # must not raise

    def test_default_secret_key_is_a_warning_not_a_blocker(self) -> None:
        """A weak SECRET_KEY is worth flagging but is not an open door.

        It must stay out of security_errors() or every default-config dev run
        becomes unstartable for a reason unrelated to authentication.

        The weak key is passed explicitly rather than relying on the dataclass
        default: those defaults are bound from os.environ once at import time, so
        a sibling test that sets SECRET_KEY first would change what the default is.
        """
        cfg = Config(
            dashboard_pass="hunter2", cstp_token="t", secret_key="dev-secret-change-me"
        )
        assert cfg.security_errors() == []
        assert any("SECRET_KEY" in e for e in cfg.validate())


class TestCheckAuth:
    def test_correct_credentials_accepted(self) -> None:
        cfg = Config(dashboard_user="admin", dashboard_pass="hunter2")
        assert check_auth("admin", "hunter2", cfg) is True

    @pytest.mark.parametrize(
        ("user", "password"),
        [
            ("admin", "wrong"),
            ("wrong", "hunter2"),
            ("admin", ""),
            ("", ""),
            (None, None),
        ],
    )
    def test_bad_credentials_rejected(self, user: str | None, password: str | None) -> None:
        cfg = Config(dashboard_user="admin", dashboard_pass="hunter2")
        assert check_auth(user, password, cfg) is False

    def test_empty_configured_password_never_matches(self) -> None:
        """Defence in depth for the exact bypass F057 closes."""
        cfg = Config(dashboard_user="admin", dashboard_pass="")
        assert check_auth("admin", "", cfg) is False
        assert check_auth("admin", None, cfg) is False


class TestLockout:
    def setup_method(self) -> None:
        auth._failed.clear()

    def test_locks_out_after_threshold(self) -> None:
        for _ in range(MAX_FAILED_ATTEMPTS):
            assert not is_locked_out("1.2.3.4")
            record_failure("1.2.3.4")
        assert is_locked_out("1.2.3.4")

    def test_lockout_is_per_client(self) -> None:
        for _ in range(MAX_FAILED_ATTEMPTS):
            record_failure("1.2.3.4")
        assert is_locked_out("1.2.3.4")
        assert not is_locked_out("5.6.7.8")

    def test_window_expiry_clears_lockout(self) -> None:
        for _ in range(MAX_FAILED_ATTEMPTS):
            record_failure("1.2.3.4", now=1000.0)
        assert is_locked_out("1.2.3.4", now=1000.0)
        assert not is_locked_out("1.2.3.4", now=1000.0 + LOCKOUT_SECONDS + 1)

    def test_success_resets_counter(self) -> None:
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            record_failure("1.2.3.4")
        reset_failures("1.2.3.4")
        record_failure("1.2.3.4")
        assert not is_locked_out("1.2.3.4")


class TestProxyAwareClientKey:
    """Codex review: behind a reverse proxy every request carries the proxy's
    address, so one attacker's ten failures would lock out every user sharing it.
    """

    def _key_with(self, monkeypatch: pytest.MonkeyPatch, *, proxies: int,
                  remote: str, xff: str | None) -> str:
        from flask import Flask

        monkeypatch.setattr(auth, "TRUSTED_PROXIES", proxies)
        headers = {"X-Forwarded-For": xff} if xff is not None else {}
        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": remote},
                                      headers=headers):
            return auth._client_key()

    def test_ignores_forwarded_header_when_no_trusted_proxies(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Untrusted XFF must not be honoured: a caller could spoof a fresh
        bucket per request and skip throttling entirely."""
        key = self._key_with(monkeypatch, proxies=0, remote="10.0.0.1",
                             xff="1.1.1.1, 2.2.2.2")
        assert key == "10.0.0.1"

    def test_uses_client_entry_behind_one_proxy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # One proxy appends the peer it received from — the client — so the
        # chain holds the client alone and remote_addr is the proxy.
        key = self._key_with(monkeypatch, proxies=1, remote="10.0.0.1",
                             xff="203.0.113.9")
        assert key == "203.0.113.9"

    def test_counts_hops_from_the_right(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only the rightmost hops were appended by infrastructure we control."""
        key = self._key_with(monkeypatch, proxies=2, remote="10.0.0.1",
                             xff="spoofed, 203.0.113.9, 10.0.0.1")
        assert key == "203.0.113.9"

    def test_falls_back_when_chain_shorter_than_hop_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        key = self._key_with(monkeypatch, proxies=3, remote="10.0.0.1",
                             xff="203.0.113.9")
        assert key == "10.0.0.1"

    def test_distinct_clients_get_distinct_buckets_behind_proxy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The actual regression: two users behind one proxy must not share a bucket."""
        a = self._key_with(monkeypatch, proxies=1, remote="10.0.0.1",
                           xff="198.51.100.1")
        b = self._key_with(monkeypatch, proxies=1, remote="10.0.0.1",
                           xff="198.51.100.2")
        assert a != b
        # Before the fix both would have been the shared proxy address.
        assert a == "198.51.100.1"
        assert b == "198.51.100.2"
