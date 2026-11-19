import shutil
import subprocess

import pytest

from architecture_model.go_runtime_adapter import (
    discover_go_entrypoints,
    run_go_version,
)
from architecture_model.runtime_version_runner import (
    list_common_runtime_entrypoints,
    run_version_pair,
)


pytestmark = pytest.mark.skipif(
    shutil.which("go") is None,
    reason="Go is not installed in this test environment",
)


def _git(repository, *args):
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True, capture_output=True, text=True,
    )


def test_go_runtime_adapter_reports_executed_project_files(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/sample\n\ngo 1.20\n", encoding="utf-8")
    (tmp_path / "main.go").write_text(
        "package main\nimport \"fmt\"\nfunc main() { fmt.Println(helper()) }\n",
        encoding="utf-8",
    )
    (tmp_path / "helper.go").write_text(
        "package main\nfunc helper() int { total := 0; for i := 0; i < 10000; i++ { total += i }; return total }\n",
        encoding="utf-8",
    )

    architecture = run_go_version(tmp_path, "main.go", timeout=60)

    assert "main.go" in architecture.modules
    assert "helper.go" in architecture.modules
    # Go coverage proves executed source files, not call edges.
    assert architecture.get_module_count() >= 2
    assert architecture.total_calls == 0


def test_go_entrypoint_discovery_excludes_server_and_tests(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/sample\n\ngo 1.20\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
    (tmp_path / "server.go").write_text(
        "package main\nimport \"net/http\"\nfunc main() { http.ListenAndServe(\":8080\", nil) }\n",
        encoding="utf-8",
    )
    (tmp_path / "main_test.go").write_text("package main\n", encoding="utf-8")

    candidates = discover_go_entrypoints(tmp_path)

    assert "main.go" in candidates
    assert "server.go" not in candidates
    assert "main_test.go" not in candidates


def test_go_v1_v2_runtime_comparison_uses_coverage_adapter(tmp_path):
    repository = tmp_path / "go_repo"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.name", "Go Runtime Test")
    _git(repository, "config", "user.email", "go-runtime@example.com")
    (repository / "go.mod").write_text("module example.com/sample\n\ngo 1.20\n", encoding="utf-8")
    (repository / "main.go").write_text(
        "package main\nimport \"fmt\"\nfunc main() { fmt.Println(helper()) }\n",
        encoding="utf-8",
    )
    (repository / "helper.go").write_text(
        "package main\nfunc helper() int { return 10 }\n",
        encoding="utf-8",
    )
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "V1")
    v1 = _git(repository, "rev-parse", "HEAD").stdout.strip()

    (repository / "helper.go").write_text(
        "package main\nfunc helper() int { return 20 }\n",
        encoding="utf-8",
    )
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "V2")
    v2 = _git(repository, "rev-parse", "HEAD").stdout.strip()

    assert "main.go" in list_common_runtime_entrypoints(repository, v1, v2)
    result = run_version_pair(repository, v1, v2, scenario="main.go", timeout=60)

    assert "helper.go" in result["v1_runtime"].modules
    assert "helper.go" in result["v2_runtime"].modules
