from pathlib import Path

import pytest

from upgrade_scout.home import openminion_env, write_config


@pytest.fixture
def scout_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolated OpenMinion home on the echo provider; yields the config path.

    The working directory moves to tmp_path because APIRuntime creates
    .openminion/browser-playwright/ under the cwd even with OPENMINION_HOME set.
    """
    home = tmp_path / "home"
    config_path = write_config(home, provider="echo")
    monkeypatch.chdir(tmp_path)
    with openminion_env(home):
        yield config_path
