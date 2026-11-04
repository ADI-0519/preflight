import pytest


@pytest.fixture(autouse=True)
def login_off(monkeypatch):
    # a developer's .env may turn sign-in on; tests that want it build their own Auth
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "")
