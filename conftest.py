"""Root pytest configuration.

Sets safe dashboard credentials before any test module can import the dashboard
`config` module.

`dashboard/config.py` builds its `Config` dataclass defaults from `os.environ` at
class-definition time and exposes a module-level `config` singleton, so the very
first import of that module freezes the values for the whole session. Two test
trees import it — `tests/test_f049_deliberation.py` (flat `config`) and
`dashboard/tests/conftest.py` (via `dashboard.app`) — and since F057 an empty
DASHBOARD_PASS makes `enforce_security_config()` raise at import. That left the
combined suite depending on which tree imported first, with a collection error as
the failure mode.

`setdefault` keeps any value a developer or CI job has already exported.
"""

import os

os.environ.setdefault("DASHBOARD_USER", "admin")
os.environ.setdefault("DASHBOARD_PASS", "test-pass")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("CSTP_TOKEN", "test-token")
