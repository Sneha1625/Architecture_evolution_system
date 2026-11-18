from architecture_model.recovery import recover_architecture


def make_file(path, language, imports):
    return {
        "file": path,
        "file_path": path,
        "language": language,
        "imports": imports,
        "classes": [],
        "functions": [],
        "variables": [],
        "call_graph": [],
    }


def get_edges(results):
    snapshot = recover_architecture(results)

    return {
        (r.source, r.target)
        for r in snapshot.relationships
    }


def test_javascript_relative_import():
    results = [
        make_file(
            "src/App.js",
            "javascript",
            ["import Header from './components/Header';"]
        ),
        make_file(
            "src/components/Header.js",
            "javascript",
            []
        ),
    ]

    assert (
        "component_app",
        "component_components"
    ) in get_edges(results)


def test_typescript_relative_import():
    results = [
        make_file(
            "src/main.ts",
            "typescript",
            ["import { User } from './models/User';"]
        ),
        make_file(
            "src/models/User.ts",
            "typescript",
            []
        ),
    ]

    assert (
        "component_main",
        "component_models"
    ) in get_edges(results)


def test_python_import():
    results = [
        make_file(
            "src/main.py",
            "python",
            ["models"]
        ),
        make_file(
            "src/models.py",
            "python",
            []
        ),
    ]

    assert (
        "component_main",
        "component_models"
    ) in get_edges(results)


def test_external_javascript_import_is_ignored():
    results = [
        make_file(
            "src/App.js",
            "javascript",
            ["import React from 'react';"]
        ),
    ]

    assert get_edges(results) == set()


def test_java_package_import():
    results = [
        make_file("src/main/java/alpha/App.java", "java", ["import beta.User;"]),
        make_file("src/main/java/beta/User.java", "java", []),
    ]
    assert ("component_alpha", "component_beta") in get_edges(results)


def test_c_local_header_include():
    results = [
        make_file("src/alpha/app.c", "c", ['#include "../beta/user.h"']),
        make_file("src/beta/user.h", "c", []),
    ]
    assert ("component_alpha", "component_beta") in get_edges(results)


def test_cpp_local_header_include():
    results = [
        make_file("src/alpha/app.cpp", "cpp", ['#include "../beta/user.hpp"']),
        make_file("src/beta/user.hpp", "cpp", []),
    ]
    assert ("component_alpha", "component_beta") in get_edges(results)


def test_csharp_namespace_import():
    results = [
        make_file("src/Alpha/App.cs", "csharp", ["using Beta.User;"]),
        make_file("src/Beta/User.cs", "csharp", []),
    ]
    assert ("component_alpha", "component_beta") in get_edges(results)


def test_go_module_import():
    results = [
        make_file("src/alpha/app.go", "go", ['import "example.com/project/beta"']),
        make_file("src/beta/beta.go", "go", []),
    ]
    assert ("component_alpha", "component_beta") in get_edges(results)


def test_rust_module_import():
    results = [
        make_file("src/alpha/app.rs", "rust", ["use crate::beta::User;"]),
        make_file("src/beta/beta.rs", "rust", []),
    ]
    assert ("component_alpha", "component_beta") in get_edges(results)


def test_php_namespace_import():
    results = [
        make_file("src/Alpha/App.php", "php", [r"use Beta\User;"]),
        make_file("src/Beta/User.php", "php", []),
    ]
    assert ("component_alpha", "component_beta") in get_edges(results)


def test_ruby_relative_require():
    results = [
        make_file("src/alpha/app.rb", "ruby", ["require_relative '../beta/user'"]),
        make_file("src/beta/user.rb", "ruby", []),
    ]
    assert ("component_alpha", "component_beta") in get_edges(results)


def test_arbitrary_repository_layout_groups_by_package():
    results = [
        make_file("application/controllers/home.py", "python", ["services.user"]),
        make_file("application/services/user.py", "python", []),
    ]
    edges = get_edges(results)
    assert ("component_controllers", "component_services") in edges


def test_parser_smoke_tests_for_all_supported_languages(tmp_path):
    from src.parser import parse_file

    samples = {
        "python": ("sample.py", "def main():\n    return 1\n"),
        "javascript": ("sample.js", "function main() { return 1; }\n"),
        "typescript": ("sample.ts", "function main(): number { return 1; }\n"),
        "tsx": ("sample.tsx", "export const App = () => <div />;\n"),
        "java": ("Sample.java", "class Sample { void main() {} }\n"),
        "c": ("sample.c", "int main(void) { return 1; }\n"),
        "cpp": ("sample.cpp", "class Sample { public: void run() {} };\n"),
        "csharp": ("Sample.cs", "class Sample { public void Run() {} }\n"),
        "go": ("sample.go", "package main\nfunc main() {}\n"),
        "rust": ("sample.rs", "fn main() {}\n"),
        "php": ("sample.php", "<?php function main() { return 1; }\n"),
        "ruby": ("sample.rb", "def main\n  1\nend\n"),
    }

    for expected_language, (filename, source) in samples.items():
        source_path = tmp_path / filename
        source_path.write_text(source, encoding="utf-8")
        parsed = parse_file(str(source_path))
        assert parsed["language"] == expected_language
        assert "error" not in parsed, f"{expected_language}: {parsed.get('error')}"
        method_count = sum(len(item.get("methods", [])) for item in parsed.get("classes", []))
        assert parsed.get("functions") or method_count or parsed.get("classes"), (
            f"{expected_language}: no program symbols were extracted"
        )


def test_flat_flask_repository_layout():
    results = [
        make_file("app.py", "python", ["flask", "sentiment_analysis"]),
        make_file("config.py", "python", ["os", "dotenv"]),
        make_file("sentiment_analysis.py", "python", ["urllib.request", "json", "ssl", "config"]),
    ]
    edges = get_edges(results)
    assert ("component_app", "component_sentiment_analysis") in edges
    assert ("component_sentiment_analysis", "component_config") in edges

