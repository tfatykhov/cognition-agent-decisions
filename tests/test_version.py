"""The server's version string must not drift from pyproject.toml."""

import tomllib
from pathlib import Path

from a2a._version import __version__
from a2a.config import AgentConfig

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_version_matches_pyproject() -> None:
    with PYPROJECT.open("rb") as f:
        declared = tomllib.load(f)["project"]["version"]
    assert __version__ == declared


def test_agent_card_default_follows_package_version() -> None:
    assert AgentConfig().version == __version__
