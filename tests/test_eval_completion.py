import sys
from types import SimpleNamespace

import pytest
from test_eval import screening, truth

from preflight.eval import baseline, run
from preflight.eval.score import score_item
from preflight.schema import StageRun


@pytest.mark.parametrize("module", [run, baseline])
def test_a_test_run_refuses_an_open_split_before_reading_items(monkeypatch, module):
    monkeypatch.setattr(sys, "argv", ["test", "--split", "v2", "--part", "test"])
    monkeypatch.setattr(module, "load_split", lambda version: SimpleNamespace(frozen=False, test=["T26"]))

    def unexpected(*args):
        pytest.fail("an open split must be refused before the tree, labels or models are touched")

    for name in ("revision", "load_ground_truth"):
        monkeypatch.setattr(module, name, unexpected)
    with pytest.raises(SystemExit, match="not frozen"):
        module.main()


@pytest.mark.parametrize("status", ["skipped", "failed", None, "done"])
def test_registration_requires_a_completed_check(tmp_path, monkeypatch, status):
    item = truth("T-synthetic-negative", [])
    stages = (StageRun(stage="claims", status="done"),)
    if status is not None:
        stages += (StageRun(stage="check", status=status),)
    result = screening("synthetic", [], {}).model_copy(update={"stages": stages})
    registered = []
    monkeypatch.setattr(sys, "argv", ["test", "--part", "dev"])
    monkeypatch.setattr(run, "revision", lambda part: "synthetic")
    monkeypatch.setattr(run, "load_split", lambda version: SimpleNamespace(dev=[item.item_id]))
    monkeypatch.setattr(run, "media", lambda item_id: [tmp_path / "synthetic.png"])
    monkeypatch.setattr(run, "load_ground_truth", lambda version, item_id: item)
    monkeypatch.setattr(run, "load_precedents", lambda *args: None)
    monkeypatch.setattr(run, "from_env", lambda: None)
    monkeypatch.setattr(run, "screen_item", lambda *args: (score_item(item, [result]), [result], 0.0))
    monkeypatch.setattr(run, "WORK", tmp_path)
    monkeypatch.setattr(run, "RESULTS", tmp_path)
    monkeypatch.setattr(run, "register", lambda *args: registered.append(args))
    if status == "done":
        run.main()
        assert len(registered) == 1
    else:
        with pytest.raises(SystemExit, match="not registered"):
            run.main()
        assert not registered
    # Rejected attempts retain their item rows for diagnosis.
    assert len(list((tmp_path / "runs").glob("*.csv"))) == 1
