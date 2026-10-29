import json

import pytest

from upgrade_scout.cli import main


def test_surface_prints_json(capsys):
    assert main(["surface"]) == 0
    assert "sdk_version" in json.loads(capsys.readouterr().out)


def test_run_refuses_a_provider_whose_key_is_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert main(["run", "--provider", "openai", "--home", str(tmp_path / "home")]) == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().err
    assert not (tmp_path / "home").exists()


@pytest.mark.runtime
def test_run_on_echo_prints_a_run_record(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert main(["run", "--home", str(tmp_path / "home")]) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["ok"] is True
    assert record["model_inference"] == "none: echo provider"
    assert record["run_state"] == "completed"
