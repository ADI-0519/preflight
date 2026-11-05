import pytest


@pytest.fixture(autouse=True)
def login_off(monkeypatch):
    # a developer's .env may turn sign-in on; tests that want it build their own Auth
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "")


@pytest.fixture(autouse=True)
def turn_timing(request, monkeypatch):
    # recorded model answers were made from turn-timed segments; only the transcribe tests exercise word timing
    if request.module.__name__ != "test_transcribe":
        monkeypatch.setattr("preflight.evidence.transcribe.mms_aligner", lambda: None)
