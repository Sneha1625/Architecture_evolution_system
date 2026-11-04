from pathlib import Path

import pytest

from architecture_model.runtime_adapters import (
    common_entrypoint,
    discover_entrypoints,
    execute_scenario,
    language_for_path,
)


def test_language_detection_covers_parser_languages():
    assert language_for_path("src/main.py") == "python"
    assert language_for_path("src/index.js") == "javascript"
    assert language_for_path("src/index.ts") == "typescript"
    assert language_for_path("src/Main.java") == "java"
    assert language_for_path("src/main.go") == "go"
    assert language_for_path("src/main.rs") == "rust"
    assert language_for_path("src/main.cpp") == "cpp"
    assert language_for_path("src/Program.cs") == "csharp"
    assert language_for_path("src/index.php") == "php"
    assert language_for_path("src/main.rb") == "ruby"


def test_discovery_ignores_tests_and_dependency_directories(tmp_path):
    (tmp_path / "main.js").write_text("console.log('ok')", encoding="utf-8")
    (tmp_path / "test_main.py").write_text("print('test')", encoding="utf-8")
    vendor = tmp_path / "node_modules" / "pkg"
    vendor.mkdir(parents=True)
    (vendor / "index.js").write_text("console.log('vendor')", encoding="utf-8")
    found = discover_entrypoints(tmp_path)
    assert found["javascript"] == ["main.js"]
    assert "python" not in found


def test_common_entrypoint_requires_same_file_and_language(tmp_path):
    first, second = tmp_path / "v1", tmp_path / "v2"
    first.mkdir()
    second.mkdir()
    (first / "main.js").write_text("console.log('v1')", encoding="utf-8")
    (second / "main.js").write_text("console.log('v2')", encoding="utf-8")
    assert common_entrypoint(first, second) == ("javascript", "main.js")


def test_unsupported_language_is_never_reported_as_runtime_calls(tmp_path):
    scenario = tmp_path / "Main.java"
    scenario.write_text("class Main {}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="call-level runtime adapter is not implemented"):
        execute_scenario(tmp_path, "main.go")
