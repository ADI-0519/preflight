import csv

import pytest

from preflight.eval import final
from preflight.eval.registry import FIELDS


def write_runs(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, restval="")
        writer.writeheader()
        writer.writerows(rows)


def row(run_id, metric, hits, total, low="", high="", part="test", sha="abc1234", stage="screen", split="v2"):
    return {"run_id": run_id, "created_at": "2026-11-04T00:00:00+00:00", "git_sha": sha, "split": split, "part": part,
            "stage": stage, "model": "m", "prompt": "claims_v5+judge_v8+vote3", "metric": metric, "hits": hits,
            "total": total, "low": low, "high": high}


@pytest.fixture
def results(tmp_path, monkeypatch):
    monkeypatch.setattr(final, "RUNS", tmp_path / "runs.csv")
    monkeypatch.setattr(final, "RESULTS", tmp_path)
    monkeypatch.setattr(final, "void_runs", lambda: {"screen-void": "leak"})
    return tmp_path


def test_table_quotes_registered_figures_with_intervals(results):
    write_runs(results / "runs.csv", [
        row("screen-t", "ad_recall", 50, 59, 0.73, 0.93),
        row("screen-t", "screen_cost_usd", 20.1, 79),
        row("screen-t", "negative_ads_flagged", 2, 20, 0.01, 0.32),
        row("baseline-t", "ad_recall", 30, 59, 0.37, 0.64, stage="baseline"),
    ])
    text = final.render(final.load_runs(["screen-t", "baseline-t"]))
    # a baseline column shows its figures without a verdict against the bar
    assert "| at least 48 of 59 | 50 / 59 (84.7%) [0.730, 0.930] **met** | 30 / 59 (50.8%) [0.370, 0.640] |" in text
    assert "$20.10 for 79 items" in text
    assert "2 / 20 (10.0%) [0.010, 0.320] **not met**" in text
    assert "- `screen-t`: " in text and "git_sha abc1234" in text


def test_dev_columns_say_the_prompts_were_tuned_on_them(results):
    write_runs(results / "runs.csv", [row("screen-d", "ad_recall", 35, 35, 0.9, 1.0, part="dev", sha="abc-dirty")])
    assert "v2 dev split (prompts tuned on it)" in final.render(final.load_runs(["screen-d"]))


@pytest.mark.parametrize("run_id, rows, message", [
    ("screen-void", [row("screen-void", "ad_recall", 1, 1)], "void"),
    ("screen-x", [], "not in"),
    ("screen-dirty", [row("screen-dirty", "ad_recall", 1, 1, sha="abc-dirty")], "dirty tree"),
])
def test_unquotable_runs_are_refused(results, run_id, rows, message):
    write_runs(results / "runs.csv", rows)
    with pytest.raises(SystemExit, match=message):
        final.load_runs([run_id])


def test_negatives_are_also_given_by_cohort(results, monkeypatch):
    monkeypatch.setattr(final, "load_split", lambda version: type("S", (), {"test": ["T02", "T03"]}))
    (results / "runs").mkdir()
    with (results / "runs" / "screen-t.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["item_id", "label", "flags"])
        writer.writeheader()
        writer.writerows([{"item_id": "T02", "label": "negative", "flags": 2},
                          {"item_id": "T03", "label": "negative", "flags": 0},
                          {"item_id": "T14", "label": "negative", "flags": 1},
                          {"item_id": "T26", "label": "negative", "flags": 0},
                          {"item_id": "A25-1", "label": "positive", "flags": 4}])
    expected = "1 of 2 split v1, 1 of 2 added in v2, 1 of 3 without T14"
    assert final.negatives_by_cohort("screen-t", "v2", "test") == expected


def test_the_one_test_screening_run_is_named_for_the_web_scoreboard(results):
    from preflight.api.web import scoreboard
    write_runs(results / "runs.csv", [
        row("screen-t", "ad_recall", 50, 59, 0.73, 0.93),
        row("baseline-t", "ad_recall", 30, 59, 0.37, 0.64, stage="baseline"),
        row("screen-d", "ad_recall", 35, 35, 0.9, 1.0, part="dev"),
    ])
    text = final.render(final.load_runs(["screen-t", "baseline-t", "screen-d"]))
    assert text.count("run_id:") == 1 and "\nrun_id: screen-t\n" in text
    (results / "final.md").write_text(text, encoding="utf-8")
    board = scoreboard(results)
    assert board["available"] and board["run_id"] == "screen-t"
    assert "\nbaseline_id: baseline-t\n" in text
    assert board["baseline_id"] == "baseline-t"
    assert board["metrics"][0]["baseline"]["hits"] == 30


def test_a_baseline_from_another_split_is_not_shown_beside_the_models(results):
    from preflight.api.web import scoreboard
    write_runs(results / "runs.csv", [
        row("screen-t", "ad_recall", 50, 59, 0.73, 0.93),
        row("baseline-t", "ad_recall", 30, 59, 0.37, 0.64, stage="baseline", split="v1"),
    ])
    (results / "final.md").write_text("run_id: screen-t\nbaseline_id: baseline-t\n", encoding="utf-8")
    board = scoreboard(results)
    assert board["available"] and board["baseline_id"] is None and board["metrics"][0]["baseline"] is None


@pytest.mark.parametrize("columns", [["baseline-t", "screen-d"], ["screen-t", "screen-u"]])
def test_no_run_is_named_unless_one_test_screening_run_is_given(results, columns):
    write_runs(results / "runs.csv", [
        row("screen-t", "ad_recall", 50, 59, 0.73, 0.93),
        row("screen-u", "ad_recall", 51, 59, 0.74, 0.94),
        row("baseline-t", "ad_recall", 30, 59, 0.37, 0.64, stage="baseline"),
        row("screen-d", "ad_recall", 35, 35, 0.9, 1.0, part="dev"),
    ])
    assert "run_id:" not in final.render(final.load_runs(columns))
