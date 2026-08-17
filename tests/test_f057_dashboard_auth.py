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
        from auth import check_auth

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
        from auth import check_auth

        cfg = Config(dashboard_user="admin", dashboard_pass="hunter2")
        assert check_auth(user, password, cfg) is False

    def test_empty_configured_password_never_matches(self) -> None:
        """Defence in depth for the exact bypass F057 closes."""
        from auth import check_auth

        cfg = Config(dashboard_user="admin", dashboard_pass="")
        assert check_auth("admin", "", cfg) is False
        assert check_auth("admin", None, cfg) is False


class TestLockout:
    def setup_method(self) -> None:
        import auth

        auth._failed.clear()

    def test_locks_out_after_threshold(self) -> None:
        from auth import MAX_FAILED_ATTEMPTS, is_locked_out, record_failure

        for _ in range(MAX_FAILED_ATTEMPTS):
            assert not is_locked_out("1.2.3.4")
            record_failure("1.2.3.4")
        assert is_locked_out("1.2.3.4")

    def test_lockout_is_per_client(self) -> None:
        from auth import MAX_FAILED_ATTEMPTS, is_locked_out, record_failure

        for _ in range(MAX_FAILED_ATTEMPTS):
            record_failure("1.2.3.4")
        assert is_locked_out("1.2.3.4")
        assert not is_locked_out("5.6.7.8")

    def test_window_expiry_clears_lockout(self) -> None:
        from auth import LOCKOUT_SECONDS, MAX_FAILED_ATTEMPTS, is_locked_out, record_failure

        for _ in range(MAX_FAILED_ATTEMPTS):
            record_failure("1.2.3.4", now=1000.0)
        assert is_locked_out("1.2.3.4", now=1000.0)
        assert not is_locked_out("1.2.3.4", now=1000.0 + LOCKOUT_SECONDS + 1)

    def test_success_resets_counter(self) -> None:
        from auth import MAX_FAILED_ATTEMPTS, is_locked_out, record_failure, reset_failures

        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            record_failure("1.2.3.4")
        reset_failures("1.2.3.4")
        record_failure("1.2.3.4")
        assert not is_locked_out("1.2.3.4")
