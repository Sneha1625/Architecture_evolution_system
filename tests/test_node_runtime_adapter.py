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


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
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


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
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


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_typescript_runtime_adapter_detects_executed_modules(tmp_path):
    (tmp_path / "main.ts").write_text(
        "import { calculate } from './helper.ts';\n"
        "console.log(calculate());\n",
        encoding="utf-8",
    )
    (tmp_path / "helper.ts").write_text(
        "export function calculate(): number {\n"
        "  let total = 0;\n"
        "  for (let i = 0; i < 100000; i++) total += i;\n"
        "  return total;\n"
        "}\n",
        encoding="utf-8",
    )

    architecture = run_node_version(tmp_path, "main.ts", timeout=30)

    assert "main.ts" in architecture.modules
    assert "helper.ts" in architecture.modules
    assert architecture.get_module_count() >= 2




def test_node_entrypoint_discovery_ignores_react_jsx_frontend(tmp_path):
    frontend = tmp_path / "client" / "src"
    frontend.mkdir(parents=True)
    (frontend / "index.js").write_text(
        "import React from 'react';\n"
        "import { createRoot } from 'react-dom/client';\n"
        "createRoot(document.getElementById('root')).render(\n"
        "  <React.StrictMode><App /></React.StrictMode>\n"
        ");\n",
        encoding="utf-8",
    )
    (tmp_path / "runtime_scenario.js").write_text(
        "const { calculate } = require('./logic');\n"
        "console.log(calculate());\n",
        encoding="utf-8",
    )
    (tmp_path / "logic.js").write_text(
        "exports.calculate = () => 42;\n",
        encoding="utf-8",
    )

    candidates = discover_node_entrypoints(tmp_path)

    assert "runtime_scenario.js" in candidates
    assert "client/src/index.js" not in candidates


def test_node_runtime_rejects_explicit_jsx_scenario_with_guidance(tmp_path, monkeypatch):
    from architecture_model.node_runtime_adapter import _resolve_node_executable

    (tmp_path / "index.js").write_text(
        "import React from 'react';\n"
        "root.render(<React.StrictMode><App /></React.StrictMode>);\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "architecture_model.node_runtime_adapter._resolve_node_executable",
        lambda: pytest.fail("JSX should be rejected before Node.js is launched"),
    )

    with pytest.raises(RuntimeError, match="contains JSX"):
        run_node_version(tmp_path, "index.js", timeout=10)

def test_node_binary_discovery_finds_cached_executable(tmp_path):
    from architecture_model.node_runtime_adapter import _find_node_binary
    import os

    bin_dir = tmp_path / "node-bin"
    bin_dir.mkdir()
    executable = bin_dir / ("node.exe" if os.name == "nt" else "node")
    executable.write_text("", encoding="utf-8")

    assert _find_node_binary(tmp_path) == executable


def test_node_resolver_prefers_path_before_auto_provision(monkeypatch):
    from architecture_model.node_runtime_adapter import _resolve_node_executable

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/node" if name == "node" else None)
    monkeypatch.setattr(
        "architecture_model.node_runtime_adapter._provision_node_runtime",
        lambda: pytest.fail("Should not provision when Node.js is already on PATH"),
    )

    assert _resolve_node_executable() == "/usr/bin/node"


def test_node_resolver_auto_provisions_when_missing(monkeypatch):
    from architecture_model.node_runtime_adapter import _resolve_node_executable

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        "architecture_model.node_runtime_adapter._provision_node_runtime",
        lambda: "/cached/node",
    )

    assert _resolve_node_executable() == "/cached/node"

def test_node_runtime_installs_dependencies_from_package_json(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from architecture_model.node_runtime_adapter import _install_node_dependencies

    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"express": "^5.1.0"}}),
        encoding="utf-8",
    )
    npm_calls = []

    monkeypatch.setattr(
        "architecture_model.node_runtime_adapter.shutil.which",
        lambda name: "npm.cmd" if name in {"npm", "npm.cmd"} else None,
    )

    def fake_run(command, **kwargs):
        npm_calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "architecture_model.node_runtime_adapter.subprocess.run", fake_run
    )

    assert _install_node_dependencies(tmp_path, node_executable="node") is True
    assert len(npm_calls) == 1
    command, options = npm_calls[0]
    assert "install" in command
    assert "--ignore-scripts" in command
    assert options["cwd"] == str(tmp_path)


def test_node_runtime_skips_npm_install_without_declared_dependencies(tmp_path, monkeypatch):
    import json
    from architecture_model.node_runtime_adapter import _install_node_dependencies

    (tmp_path / "package.json").write_text(
        json.dumps({"name": "no-dependencies", "scripts": {"start": "node main.js"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "architecture_model.node_runtime_adapter.shutil.which",
        lambda _name: pytest.fail("npm should not be required without dependencies"),
    )

    assert _install_node_dependencies(tmp_path) is False



def test_node_entrypoint_discovery_prefers_declared_test_script(tmp_path):
    import json

    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"}}),
        encoding="utf-8",
    )
    app = tmp_path / "src"
    app.mkdir()
    (app / "index.ts").write_text(
        "const app = { listen() {} }; app.listen(3000);\n",
        encoding="utf-8",
    )

    candidates = discover_node_entrypoints(tmp_path)

    assert "npm:test" in candidates
    assert "src/index.ts" not in candidates


@pytest.mark.skipif(
    shutil.which("node") is None or not (shutil.which("npm") or shutil.which("npm.cmd")),
    reason="Node.js and npm are required",
)
def test_npm_test_workload_collects_project_runtime_modules(tmp_path):
    import json

    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "node --test"}}),
        encoding="utf-8",
    )
    source = tmp_path / "src"
    tests = tmp_path / "test"
    source.mkdir()
    tests.mkdir()
    (source / "service.js").write_text(
        "exports.calculate = (value) => value * 2;\n",
        encoding="utf-8",
    )
    (tests / "service.test.js").write_text(
        "const test = require('node:test');\n"
        "const assert = require('node:assert/strict');\n"
        "const { calculate } = require('../src/service');\n"
        "test('calculate', () => assert.equal(calculate(21), 42));\n",
        encoding="utf-8",
    )

    architecture = run_node_version(tmp_path, "npm:test", timeout=60)

    assert "src/service.js" in architecture.modules
    assert architecture.get_module_count() >= 1


@pytest.mark.skipif(
    shutil.which("node") is None or not (shutil.which("npm") or shutil.which("npm.cmd")),
    reason="Node.js and npm are required",
)
def test_runtime_pair_automatically_uses_npm_test_for_both_commits(tmp_path):
    import json
    import subprocess

    repository = tmp_path / "node_test_repo"
    repository.mkdir()

    def git(*args):
        subprocess.run(
            ["git", "-C", str(repository), *args],
            check=True, capture_output=True, text=True,
        )

    git("init")
    git("config", "user.name", "Node Runtime Test")
    git("config", "user.email", "node-runtime@example.com")
    (repository / "src").mkdir()
    (repository / "test").mkdir()
    (repository / "package.json").write_text(
        json.dumps({"scripts": {"test": "node --test"}}),
        encoding="utf-8",
    )
    (repository / "src" / "service.js").write_text(
        "exports.calculate = (value) => value + 1;\n",
        encoding="utf-8",
    )
    (repository / "test" / "service.test.js").write_text(
        "const test = require('node:test');\n"
        "const assert = require('node:assert/strict');\n"
        "const { calculate } = require('../src/service');\n"
        "test('calculate', () => assert.equal(calculate(1), 2));\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "V1")
    v1 = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    (repository / "src" / "service.js").write_text(
        "exports.calculate = (value) => value + 2;\n",
        encoding="utf-8",
    )
    (repository / "test" / "service.test.js").write_text(
        "const test = require('node:test');\n"
        "const assert = require('node:assert/strict');\n"
        "const { calculate } = require('../src/service');\n"
        "test('calculate', () => assert.equal(calculate(1), 3));\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "V2")
    v2 = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    result = run_version_pair(
        repository_path=repository,
        v1_commit=v1,
        v2_commit=v2,
        timeout=60,
    )

    assert result["scenario"] == "npm:test"
    assert "src/service.js" in result["v1_runtime"].modules
    assert "src/service.js" in result["v2_runtime"].modules
    assert result["v1_runtime"].get_module_count() > 0
    assert result["v2_runtime"].get_module_count() > 0


def test_npm_resolver_uses_bundled_runtime_when_path_has_no_npm(tmp_path, monkeypatch):
    from architecture_model.node_runtime_adapter import _resolve_npm_invocation

    node_home = tmp_path / "node-runtime"
    node_home.mkdir()
    node = node_home / ("node.exe" if __import__("os").name == "nt" else "node")
    node.write_text("", encoding="utf-8")
    npm_cli = node_home / "node_modules" / "npm" / "bin" / "npm-cli.js"
    npm_cli.parent.mkdir(parents=True)
    npm_cli.write_text("// npm cli placeholder\n", encoding="utf-8")

    monkeypatch.setattr(
        "architecture_model.node_runtime_adapter.shutil.which",
        lambda _name: None,
    )
    monkeypatch.setattr(
        "architecture_model.node_runtime_adapter._provision_node_runtime",
        lambda: str(node),
    )

    resolved_node, resolved_cli, npm_command = _resolve_npm_invocation("missing-node")

    assert resolved_node == str(node.resolve())
    assert resolved_cli == str(npm_cli)
    assert npm_command is None
