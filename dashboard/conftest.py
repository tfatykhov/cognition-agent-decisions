"""Pytest bootstrap for the dashboard package.

`dashboard/app.py` imports its siblings flat (`from auth import requires_auth`)
because that is how it is deployed: the Dockerfile copies the dashboard directory
into /app and runs `gunicorn app:app` from there, so the package directory itself
is the import root.

Under pytest the repo root is the import root instead, so those flat imports fail
and the whole dashboard suite is uncollectable. Putting the dashboard directory on
sys.path resolves them without changing the app to an import style production does
not use — the tests then exercise the same module wiring that ships.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
