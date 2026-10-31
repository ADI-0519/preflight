import importlib

import preflight

MODULES = ["schema", "models", "sources", "ingest", "evidence", "claims", "check", "agent", "eval", "api"]


def test_version():
    assert preflight.__version__ == "0.1.0"


def test_modules_import():
    for name in MODULES:
        importlib.import_module(f"preflight.{name}")
