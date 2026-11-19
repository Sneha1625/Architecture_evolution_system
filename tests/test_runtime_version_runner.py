from pathlib import Path

from architecture_model.runtime_version_runner import (
    LEGACY_STDLIB_DISTRIBUTIONS,
    _missing_module_name,
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


def test_runtime_version_pair_populates_both_versions(tmp_path):
    import subprocess

    from architecture_model.runtime_version_runner import run_version_pair

    repository = tmp_path / "sample_repo"
    repository.mkdir()

    def git(*args):
        subprocess.run(
            ["git", "-C", str(repository), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    git("init")
    git("config", "user.name", "Runtime Test")
    git("config", "user.email", "runtime-test@example.com")

    (repository / "main.py").write_text(
        "from helper import calculate\nprint(calculate())\n",
        encoding="utf-8",
    )
    (repository / "helper.py").write_text(
        "def calculate():\n    return 1\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "V1")
    v1_commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    (repository / "helper.py").write_text(
        "def calculate():\n    return 2\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "V2")
    v2_commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    result = run_version_pair(
        repository_path=repository,
        v1_commit=v1_commit,
        v2_commit=v2_commit,
        scenario="main.py",
        timeout=30,
    )

    assert result["v1_commit"]
    assert result["v2_commit"]
    assert result["v1_runtime"].get_module_count() >= 2
    assert result["v2_runtime"].get_module_count() >= 2
    assert result["v1_runtime"].get_relationship_count() >= 1
    assert result["v2_runtime"].get_relationship_count() >= 1
    assert result["v1_metrics"]["modules"] > 0
    assert result["v2_metrics"]["modules"] > 0



def test_removed_standard_library_module_is_mapped_to_compatibility_distribution():
    assert LEGACY_STDLIB_DISTRIBUTIONS["aifc"] == "standard-aifc"
    assert _missing_module_name("ModuleNotFoundError: No module named 'aifc'") == "aifc"
    assert _missing_module_name("ModuleNotFoundError: No module named 'pkg.submodule'") == "pkg"
    assert _missing_module_name("ImportError: cannot import name 'X'") is None


def test_unknown_missing_module_does_not_get_guessed():
    assert "some_project_module" not in LEGACY_STDLIB_DISTRIBUTIONS
