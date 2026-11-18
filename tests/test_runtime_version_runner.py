from pathlib import Path

from architecture_model.runtime_version_runner import (
    discover_python_entrypoints,
    run_version,
)


def test_runtime_trace_includes_module_scope_entrypoint_and_helper(tmp_path):
    (tmp_path / "main.py").write_text(
        "from helper import calculate\nresult = calculate()\n",
        encoding="utf-8",
    )
    (tmp_path / "helper.py").write_text(
        "def calculate():\n    return 42\n",
        encoding="utf-8",
    )

    architecture = run_version(tmp_path, scenario="main.py", timeout=30)

    assert "main" in architecture.modules
    assert "helper" in architecture.modules
    assert architecture.get_module_count() >= 2
    assert architecture.get_relationship_count() >= 1


def test_entrypoint_discovery_ignores_server_launchers(tmp_path):
    (tmp_path / "app.py").write_text(
        "from flask import Flask\napp = Flask(__name__)\napp.run()\n",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        "def main():\n    return 1\n\nif __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )

    candidates = discover_python_entrypoints(tmp_path)

    assert "main.py" in candidates
    assert "app.py" not in candidates
