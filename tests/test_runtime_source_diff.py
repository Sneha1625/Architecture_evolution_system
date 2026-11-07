"""Tests for Git source-change evidence returned by runtime comparisons."""

import subprocess

from architecture_model.runtime_version_runner import get_commit_source_changes


def _git(repository, *arguments):
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def test_commit_source_changes_reports_added_modified_and_removed_files(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.email", "runtime-test@example.invalid")
    _git(repository, "config", "user.name", "Runtime Test")

    (repository / "modified.py").write_text("value = 1\n", encoding="utf-8")
    (repository / "removed.py").write_text("old = True\n", encoding="utf-8")
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "baseline")
    base = _git(repository, "rev-parse", "HEAD").stdout.strip()

    (repository / "modified.py").write_text("value = 2\nextra = 3\n", encoding="utf-8")
    (repository / "removed.py").unlink()
    (repository / "added.py").write_text("new = True\n", encoding="utf-8")
    _git(repository, "add", "-A")
    _git(repository, "commit", "-m", "change source files")
    head = _git(repository, "rev-parse", "HEAD").stdout.strip()

    changes = get_commit_source_changes(repository, base, head)
    by_file = {item["file"]: item for item in changes}

    assert by_file["added.py"]["status"] == "A"
    assert by_file["modified.py"]["status"] == "M"
    assert by_file["removed.py"]["status"] == "D"
    assert by_file["modified.py"]["additions"] == 1
    assert by_file["modified.py"]["deletions"] == 1


def test_discovery_prefers_architecture_recovery_over_demo(tmp_path):
    from architecture_model.runtime_version_runner import discover_python_entrypoints

    (tmp_path / "sample_project.py").write_text(
        "def demo():\n    return 1\n", encoding="utf-8"
    )
    (tmp_path / "test_architecture_recovery.py").write_text(
        "def run_recovery():\n    return True\n", encoding="utf-8"
    )

    candidates = discover_python_entrypoints(tmp_path)

    assert candidates[0] == "test_architecture_recovery.py"
