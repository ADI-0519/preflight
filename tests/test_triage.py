import json
import os
import ssl
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from dotenv import load_dotenv
from test_eval import screening

from preflight import triage
from preflight.models import ChatResult, Glimmer, Store
from preflight.schema import Segment
from preflight.triage import MODELS, Decision, Unit, baseten_client, classify, units


class Client:
    model = MODELS[0]

    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def ask(self, text, **kwargs):
        self.calls.append((text, kwargs))
        return ChatResult(self.model, self.answer, {"prompt_tokens": 12, "completion_tokens": 8})


def test_ids_retain_media_and_modality_and_batch_ad_once():
    s = screening("image-1", ["Vitamin C supports immunity", "Orange flavour"], {})
    s = s.model_copy(update={"segments": (Segment(
        segment_id="text-0", turn=0, text="Helps reduce fatigue", start=0, end=1, timing="turn",
    ),)})
    ad = units([s, screening("image-2", ["Just £9"], {})])
    assert len({u.id for u in ad}) == 4
    assert ad[3].screening_id == "image-1" and ad[3].source_id == "text-0"
    client = Client(json.dumps({"units": [{"id": u.id, "needs_review": True} for u in reversed(ad)]}))
    result = classify(client, ad)
    assert result.decisions == tuple(Decision(u.id, True) for u in ad)
    assert len(client.calls) == 1 and not result.fallback
    assert client.calls[0][1] == {"prompt_version": "triage_v1"}


@pytest.mark.parametrize("answer", [
    "", "not JSON", '```json\n{"units": []}\n```', '{"units": []}',
    '{"units": [{"id":"u","needs_review":"false"}]}',
    '{"units": [{"id":"u","needs_review":0}]}',
    '{"units": [{"id":"unknown","needs_review":false}]}',
    '{"units": [{"id":"u","needs_review":false},{"id":"u","needs_review":false}]}',
    '{"units": [{"id":"u","needs_review":false,"extra":"omit this"}]}',
    '{"units": [{"id":"u","needs_review":false}],"extra":true}',
])
def test_invalid_output_keeps_every_unit(answer):
    client = Client(answer)
    result = classify(client, [Unit("u", "s", "text", "t", "Claim")])
    assert result.fallback and result.decisions == (Decision("u", True),)


def test_no_units_make_no_model_call():
    client = Client("unneeded")
    assert classify(client, []).decisions == () and client.calls == []


def test_unsupported_model_fails_before_request():
    with pytest.raises(ValueError, match="Meta open-weights"):
        classify(SimpleNamespace(model="non-meta"), [])


def test_duplicate_evidence_is_rejected():
    s = screening("s", ["synthetic"], {})
    with pytest.raises(ValueError, match="unique"):
        units([s, s])


def test_baseten_transport_keeps_tls_verification_and_closes(monkeypatch):
    original = httpx.Client
    created = []
    class Transport(original):
        def __init__(self, **kwargs):
            context = kwargs["verify"]
            assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
            super().__init__(transport=httpx.MockTransport(lambda _: pytest.fail("unexpected request")), **kwargs)
            created.append(self)
    monkeypatch.setattr(triage.httpx, "Client", Transport)
    with baseten_client("synthetic") as client:
        assert str(client.base_url) == "https://inference.baseten.co/v1/"
    assert created[0].is_closed


@pytest.mark.live
def test_baseten_triage_live(tmp_path):
    """Fresh-cache synthetic smoke; deliberately requires no benchmark inputs."""
    load_dotenv()
    key = os.environ.get("BASETEN_API_KEY")
    if not key:
        pytest.skip("BASETEN_API_KEY is not configured")
    model = os.environ.get("GLIMMER_MODEL") or MODELS[0]
    ad = [Unit("synthetic/text:0", "synthetic", "text", "0", "Vitamin C supports immune function"),
          Unit("synthetic/text:1", "synthetic", "text", "1", "Orange flavour")]
    with baseten_client(key) as api:
        result = classify(Glimmer(Store(tmp_path), model, api), ad)
    assert not result.fallback and result.decisions[0].needs_review
    print(json.dumps({"model": result.model, "date": datetime.now(UTC).date().isoformat(), "usage": result.usage}))
