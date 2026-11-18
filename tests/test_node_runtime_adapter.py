import shutil

import pytest

from architecture_model.node_runtime_adapter import (
    discover_node_entrypoints,
    run_node_version,
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
