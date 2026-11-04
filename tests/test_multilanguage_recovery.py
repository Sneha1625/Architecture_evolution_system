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

def test_java_package_import_creates_dependency_relationship():
    results = [
        make_file(
            "src/main/java/com/example/controller/UserController.java",
            "java",
            ["import com.example.service.UserService;"]
        ),
        make_file(
            "src/main/java/com/example/service/UserService.java",
            "java",
            []
        ),
    ]

    assert (
        "component_controller",
        "component_service"
    ) in get_edges(results)
