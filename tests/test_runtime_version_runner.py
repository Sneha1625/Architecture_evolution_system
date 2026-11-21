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


def test_runtime_scenario_receives_multiline_stdin(tmp_path):
    (tmp_path / "interactive.py").write_text(
        "first = int(input('Enter first number: '))\n"
        "second = int(input('Enter second number: '))\n"
        "print(first + second)\n",
        encoding="utf-8",
    )

    architecture = run_version(
        tmp_path,
        scenario="interactive.py",
        timeout=30,
        runtime_input="2\n3\n",
    )

    assert "interactive" in architecture.modules
    assert architecture.total_calls >= 0


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


def test_runtime_evolution_detects_modified_executed_function_body():
    from architecture_model.runtime_model import RuntimeArchitecture
    from architecture_model.runtime_evolution import compare_runtime_architectures

    v1 = RuntimeArchitecture(entry_point="main.py")
    v2 = RuntimeArchitecture(entry_point="main.py")
    v1.executed_functions.add("main.calculate")
    v2.executed_functions.add("main.calculate")
    v1.executed_function_fingerprints["main.calculate"] = "hash-add"
    v2.executed_function_fingerprints["main.calculate"] = "hash-multiply"
    v1.executed_function_counts["main.calculate"] = 1
    v2.executed_function_counts["main.calculate"] = 1

    comparison = compare_runtime_architectures(v1, v2)

    assert comparison["executed_function_changes"]["added"] == []
    assert comparison["executed_function_changes"]["removed"] == []
    assert comparison["executed_function_changes"]["modified"] == ["main.calculate"]
    assert comparison["summary"]["functions_modified"] == 1
    assert comparison["summary"]["function_changes"] == 1


def test_runtime_evolution_detects_per_function_call_count_changes():
    from architecture_model.runtime_model import RuntimeArchitecture
    from architecture_model.runtime_evolution import compare_runtime_architectures

    v1 = RuntimeArchitecture(entry_point="main.py")
    v2 = RuntimeArchitecture(entry_point="main.py")
    v1.executed_functions.add("main.calculate")
    v2.executed_functions.add("main.calculate")
    v1.executed_function_counts["main.calculate"] = 2
    v2.executed_function_counts["main.calculate"] = 5

    comparison = compare_runtime_architectures(v1, v2)

    assert comparison["summary"]["function_call_count_changes"] == 1
    assert comparison["function_call_count_changes"][0]["difference"] == 3


def test_stdlib_only_scenario_skips_heavy_requirements_install(tmp_path):
    # A bounded sample scenario should run without installing unrelated
    # application requirements such as the web/ML stack.
    (tmp_path / "requirements.txt").write_text(
        "sentence-transformers\nscikit-learn\nstreamlit\n",
        encoding="utf-8",
    )
    (tmp_path / "sample_project.py").write_text(
        "import math\n"
        "class Calculator:\n"
        "    def add(self, a, b):\n"
        "        return a + b\n"
        "result = Calculator().add(2, 3)\n"
        "print(math.sqrt(result))\n",
        encoding="utf-8",
    )

    architecture = run_version(
        tmp_path,
        scenario="sample_project.py",
        timeout=30,
    )

    assert "sample_project" in architecture.modules
    assert architecture.total_calls > 0
    assert "sample_project.Calculator.add" in architecture.executed_functions


def test_runtime_evolution_detects_executed_functions():
    from architecture_model.runtime_model import RuntimeArchitecture
    from architecture_model.runtime_evolution import compare_runtime_architectures

    v1 = RuntimeArchitecture(entry_point="main.py")
    v2 = RuntimeArchitecture(entry_point="main.py")
    v1.executed_functions.update({"main.main", "service.old_path"})
    v2.executed_functions.update({"main.main", "service.new_path"})

    comparison = compare_runtime_architectures(v1, v2)

    assert comparison["executed_function_changes"]["added"] == ["service.new_path"]
    assert comparison["executed_function_changes"]["removed"] == ["service.old_path"]
    assert comparison["summary"]["functions_added"] == 1
    assert comparison["summary"]["functions_removed"] == 1
    assert comparison["summary"]["function_changes"] == 2


def test_sample_project_is_not_auto_selected_as_repository_runtime_entrypoint(tmp_path):
    (tmp_path / "sample_project.py").write_text(
        "def calculate():\\n    return 42\\n\\nprint(calculate())\\n",
        encoding="utf-8",
    )

    assert "sample_project.py" not in discover_python_entrypoints(tmp_path)



def test_architecture_recovery_workflow_is_discovered_automatically(tmp_path):
    (tmp_path / "test_architecture_recovery.py").write_text(
        "from src.parser import parse_folder\n"
        "from architecture_model.recovery import recover_architecture\n"
        "parsed = parse_folder('.')\n"
        "snapshot = recover_architecture(parsed)\n",
        encoding="utf-8",
    )

    assert "test_architecture_recovery.py" in discover_python_entrypoints(tmp_path)


def test_runtime_version_pair_automatically_uses_recovery_workload(tmp_path):
    import subprocess
    from architecture_model.runtime_version_runner import run_version_pair

    repository = tmp_path / "automatic_repo"
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

    (repository / "src").mkdir()
    (repository / "architecture_model").mkdir()
    (repository / "src" / "__init__.py").write_text("", encoding="utf-8")
    (repository / "architecture_model" / "__init__.py").write_text("", encoding="utf-8")
    (repository / "src" / "parser.py").write_text(
        "def parse_folder(path):\n    from helper import calculate\n    return calculate()\n",
        encoding="utf-8",
    )
    (repository / "architecture_model" / "recovery.py").write_text(
        "def recover_architecture(value):\n    from helper import calculate\n    return calculate()\n",
        encoding="utf-8",
    )
    (repository / "helper.py").write_text(
        "def calculate():\n    return 1\n",
        encoding="utf-8",
    )
    (repository / "test_architecture_recovery.py").write_text(
        "from src.parser import parse_folder\n"
        "from architecture_model.recovery import recover_architecture\n"
        "parsed = parse_folder('.')\n"
        "snapshot = recover_architecture(parsed)\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "V1")
    v1_commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    (repository / "helper.py").write_text(
        "def calculate():\n    return 2\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "V2")
    v2_commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    result = run_version_pair(
        repository_path=repository,
        v1_commit=v1_commit,
        v2_commit=v2_commit,
    )

    assert Path(result["scenario"]).name == "architecture_runtime_workload.py"
    assert result["v1_runtime"].get_module_count() > 0
    assert result["v2_runtime"].get_module_count() > 0
    assert result["v1_runtime"].get_relationship_count() > 0
    assert result["v2_runtime"].get_relationship_count() > 0
    assert "helper.calculate" in result["v1_runtime"].executed_functions
    assert "helper.calculate" in result["v2_runtime"].executed_functions



def test_runtime_version_pair_generates_shared_workload_for_older_commits(tmp_path):
    import subprocess
    from architecture_model.runtime_version_runner import run_version_pair

    repository = tmp_path / "older_automatic_repo"
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

    (repository / "src").mkdir()
    (repository / "src" / "parser.py").write_text(
        "def parse_folder(path):\n    from helper import calculate\n    return calculate()\n",
        encoding="utf-8",
    )
    (repository / "helper.py").write_text(
        "def calculate():\n    return 1\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "V1 without recovery module")
    v1_commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    (repository / "architecture_model").mkdir()
    (repository / "architecture_model" / "recovery.py").write_text(
        "def recover_architecture(value):\n    from helper import calculate\n    return calculate()\n",
        encoding="utf-8",
    )
    (repository / "test_architecture_recovery.py").write_text(
        "from src.parser import parse_folder\n"
        "from architecture_model.recovery import recover_architecture\n"
        "parsed = parse_folder('.')\n"
        "snapshot = recover_architecture(parsed)\n",
        encoding="utf-8",
    )
    (repository / "helper.py").write_text(
        "def calculate():\n    return 2\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "V2 adds recovery module")
    v2_commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    result = run_version_pair(
        repository_path=repository,
        v1_commit=v1_commit,
        v2_commit=v2_commit,
    )

    assert Path(result["scenario"]).name == "architecture_runtime_workload.py"
    assert result["v1_runtime"].get_module_count() > 0
    assert result["v2_runtime"].get_module_count() > 0
    assert "helper.calculate" in result["v1_runtime"].executed_functions
    assert "helper.calculate" in result["v2_runtime"].executed_functions
    assert "architecture_model.recovery.recover_architecture" not in result["v1_runtime"].executed_functions
    assert "architecture_model.recovery.recover_architecture" in result["v2_runtime"].executed_functions
