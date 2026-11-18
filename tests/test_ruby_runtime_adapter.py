import shutil
import subprocess

import pytest

from architecture_model.ruby_runtime_adapter import (
    discover_ruby_entrypoints,
    run_ruby_version,
)
from architecture_model.runtime_version_runner import (
    list_common_runtime_entrypoints,
    run_version_pair,
)


pytestmark = pytest.mark.skipif(
    shutil.which("ruby") is None,
    reason="Ruby is not installed in this test environment",
)


def test_ruby_runtime_adapter_detects_project_files_and_calls(tmp_path):
    (tmp_path / "main.rb").write_text(
        "require_relative 'helper'\n"
        "puts Helper.calculate\n",
        encoding="utf-8",
    )
    (tmp_path / "helper.rb").write_text(
        "module Helper\n"
        "  def self.calculate\n"
        "    total = 0\n"
        "    1000.times { |value| total += value }\n"
        "    total\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )

    architecture = run_ruby_version(tmp_path, "main.rb", timeout=30)

    assert "main.rb" in architecture.modules
    assert "helper.rb" in architecture.modules
    assert architecture.get_module_count() >= 2


def test_ruby_entrypoint_discovery_skips_tests_and_server(tmp_path):
    (tmp_path / "server.rb").write_text(
        "require 'webrick'\n"
        "server = WEBrick::HTTPServer.new(Port: 8000)\n",
        encoding="utf-8",
    )
    (tmp_path / "main.rb").write_text(
        "puts 'bounded scenario'\n",
        encoding="utf-8",
    )
    (tmp_path / "main_test.rb").write_text(
        "puts 'not an entry point'\n",
        encoding="utf-8",
    )

    candidates = discover_ruby_entrypoints(tmp_path)

    assert "main.rb" in candidates
    assert "server.rb" not in candidates
    assert "main_test.rb" not in candidates


def test_ruby_v1_v2_runtime_comparison_uses_ruby_adapter(tmp_path):
    repository = tmp_path / "ruby_repo"
    repository.mkdir()

    def git(*args):
        subprocess.run(
            ["git", "-C", str(repository), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    git("init")
    git("config", "user.name", "Ruby Runtime Test")
    git("config", "user.email", "ruby-runtime@example.com")
    (repository / "main.rb").write_text(
        "require_relative 'helper'\n"
        "puts Helper.calculate\n",
        encoding="utf-8",
    )
    (repository / "helper.rb").write_text(
        "module Helper\n"
        "  def self.calculate\n"
        "    1000.times.reduce(0, :+)\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "V1")
    v1 = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    (repository / "helper.rb").write_text(
        "module Helper\n"
        "  def self.calculate\n"
        "    1000.times.reduce(1, :+)\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "V2")
    v2 = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    assert "main.rb" in list_common_runtime_entrypoints(repository, v1, v2)
    result = run_version_pair(
        repository_path=repository,
        v1_commit=v1,
        v2_commit=v2,
        scenario="main.rb",
        timeout=30,
    )
    assert "helper.rb" in result["v1_runtime"].modules
    assert "helper.rb" in result["v2_runtime"].modules
