import shutil

import pytest

from architecture_model.node_runtime_adapter import (
    discover_node_entrypoints,
    run_node_version,
)
from architecture_model.runtime_version_runner import (
    list_common_runtime_entrypoints,
    run_version_pair,
)


pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="Node.js is not installed in this test environment",
)


def test_node_runtime_adapter_detects_executed_project_modules(tmp_path):
    (tmp_path / "main.js").write_text(
        "const { calculate } = require('./helper');\n"
        "console.log(calculate());\n",
        encoding="utf-8",
    )
    (tmp_path / "helper.js").write_text(
        "exports.calculate = function calculate() {\n"
        "  let total = 0;\n"
        "  for (let i = 0; i < 100000; i++) total += i;\n"
        "  return total;\n"
        "};\n",
        encoding="utf-8",
    )

    architecture = run_node_version(tmp_path, "main.js", timeout=30)

    assert "main.js" in architecture.modules
    assert "helper.js" in architecture.modules
    assert architecture.get_module_count() >= 2


def test_node_entrypoint_discovery_ignores_dev_server(tmp_path):
    (tmp_path / "server.js").write_text(
        "const app = require('http').createServer();\n"
        "app.listen(3000);\n",
        encoding="utf-8",
    )
    (tmp_path / "main.js").write_text(
        "const value = 42;\nconsole.log(value);\n",
        encoding="utf-8",
    )

    candidates = discover_node_entrypoints(tmp_path)

    assert "main.js" in candidates
    assert "server.js" not in candidates


def test_javascript_v1_v2_runtime_comparison_uses_node_adapter(tmp_path):
    import subprocess

    repository = tmp_path / "javascript_repo"
    repository.mkdir()

    def git(*args):
        subprocess.run(
            ["git", "-C", str(repository), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    git("init")
    git("config", "user.name", "Node Runtime Test")
    git("config", "user.email", "node-runtime@example.com")

    (repository / "main.js").write_text(
        "const { calculate } = require('./helper');\n"
        "console.log(calculate());\n",
        encoding="utf-8",
    )
    (repository / "helper.js").write_text(
        "exports.calculate = function calculate() {\n"
        "  let total = 0;\n"
        "  for (let i = 0; i < 100000; i++) total += i;\n"
        "  return total;\n"
        "};\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "V1")
    v1 = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    (repository / "helper.js").write_text(
        "exports.calculate = function calculate() {\n"
        "  let total = 1;\n"
        "  for (let i = 0; i < 100000; i++) total += i;\n"
        "  return total;\n"
        "};\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "V2")
    v2 = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    assert "main.js" in list_common_runtime_entrypoints(repository, v1, v2)

    result = run_version_pair(
        repository_path=repository,
        v1_commit=v1,
        v2_commit=v2,
        scenario="main.js",
        timeout=30,
    )

    assert result["scenario"] == "main.js"
    assert "helper.js" in result["v1_runtime"].modules
    assert "helper.js" in result["v2_runtime"].modules
    assert result["v1_metrics"]["modules"] >= 2
    assert result["v2_metrics"]["modules"] >= 2
