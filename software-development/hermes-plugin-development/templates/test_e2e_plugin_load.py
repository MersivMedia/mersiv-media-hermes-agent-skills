"""Template: end-to-end load of a standalone plugin through Hermes' real PluginManager.

Copy into <plugin-repo>/tests/, then set PLUGIN_NAME and adjust the config and assertions.
Proven on the Jermes repo against Hermes origin/main 9514d35.
Skips cleanly when no Hermes checkout is present.

Run it with an interpreter that has Hermes' dependencies installed, e.g.:
    PYTHONPATH=. ~/hermes-agent/.venv/bin/python -m pytest tests/test_e2e_hermes.py
    HERMES_AGENT_DIR=/tmp/hermes-main ...   # a `git worktree` of origin/main
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import httpx
import pytest

PLUGIN_NAME = "myplugin"  # must match plugin.yaml `name`
REPO = Path(__file__).resolve().parents[1]
HERMES_DIR = os.environ.get("HERMES_AGENT_DIR", str(Path.home() / "hermes-agent"))

pytestmark = pytest.mark.skipif(
    not (Path(HERMES_DIR) / "hermes_cli" / "plugins.py").exists(),
    reason="Hermes Agent checkout not found",
)


def fake_handler(request: httpx.Request) -> httpx.Response:
    # Replace with the plugin's remote API fake.
    return httpx.Response(200, json={})


@pytest.fixture
def hermes(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    (home / "plugins").mkdir(parents=True)
    (home / "plugins" / PLUGIN_NAME).symlink_to(REPO, target_is_directory=True)
    # General plugins are opt-in: nothing loads unless listed here.
    (home / "config.yaml").write_text(f"plugins:\n  enabled: [{PLUGIN_NAME}]\n")
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.syspath_prepend(HERMES_DIR)

    # Hermes imports the plugin as hermes_plugins.<slug>, so patching your own
    # package's modules has no effect. Patch the shared HTTP library instead.
    real_init = httpx.Client.__init__

    def init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(fake_handler)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", init)

    for mod in [m for m in sys.modules if m == "hermes_cli.plugins" or m.startswith("hermes_plugins")]:
        del sys.modules[mod]
    plugins = importlib.import_module("hermes_cli.plugins")
    plugins.discover_plugins(force=True)
    yield plugins
    for mod in [m for m in sys.modules if m.startswith("hermes_plugins")]:
        del sys.modules[mod]


def test_plugin_loads_and_registers(hermes):
    mgr = hermes.get_plugin_manager()
    assert PLUGIN_NAME in mgr._plugins, list(mgr._plugins)
    assert mgr._hooks.get("pre_tool_call")  # adjust to the hooks you register


def test_real_dispatch(hermes):
    # Fire through Hermes' own dispatch, not your callback directly.
    hermes.invoke_hook("pre_llm_call", session_id="e2e", user_message="hello",
                       conversation_history=[], is_first_turn=True, model="m", platform="cli")
    block, modified = hermes._dispatch_pre_tool_call_hooks(
        "terminal", {"command": "ls"}, task_id="e2e", session_id="e2e")
    assert block is None
