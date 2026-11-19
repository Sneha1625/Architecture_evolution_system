import shutil

import pytest

from architecture_model.java_runtime_adapter import (
    discover_java_entrypoints,
    run_java_version,
)


pytestmark = pytest.mark.skipif(
    not all(shutil.which(name) for name in ("java", "javac", "jfr")),
    reason="A full JDK is not installed in this test environment",
)


def test_java_runtime_adapter_observes_project_stack_frames(tmp_path):
    source = tmp_path / "src" / "demo"
    source.mkdir(parents=True)
    (source / "Main.java").write_text(
        "package demo;\n"
        "public class Main { public static void main(String[] args) { Helper.work(); } }\n",
        encoding="utf-8",
    )
    (source / "Helper.java").write_text(
        "package demo;\n"
        "public class Helper { static void work() { long value = 0; "
        "for (long i = 0; i < 150000000L; i++) value += i; "
        "System.out.println(value); } }\n",
        encoding="utf-8",
    )

    architecture = run_java_version(tmp_path, "src/demo/Main.java", timeout=90)

    assert "src/demo/Main.java" in architecture.modules
    assert "src/demo/Helper.java" in architecture.modules
    assert architecture.get_module_count() >= 2
    assert architecture.total_calls > 0


def test_java_entrypoint_discovery_excludes_tests_and_servers(tmp_path):
    (tmp_path / "Main.java").write_text(
        "public class Main { public static void main(String[] args) {} }\n",
        encoding="utf-8",
    )
    (tmp_path / "Server.java").write_text(
        "import com.sun.net.httpserver.HttpServer;\n"
        "public class Server { public static void main(String[] args) { HttpServer.create(null, 0); } }\n",
        encoding="utf-8",
    )
    (tmp_path / "MainTest.java").write_text(
        "public class MainTest { public static void main(String[] args) {} }\n",
        encoding="utf-8",
    )

    candidates = discover_java_entrypoints(tmp_path)

    assert "Main.java" in candidates
    assert "Server.java" not in candidates
    assert "MainTest.java" not in candidates


def test_jdk_tool_discovery_requires_complete_toolchain(tmp_path):
    from architecture_model.java_runtime_adapter import _find_jdk_binaries

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    names = ("java.exe", "javac.exe", "jfr.exe") if __import__("os").name == "nt" else ("java", "javac", "jfr")
    for name in names[:2]:
        (bin_dir / name).write_text("", encoding="utf-8")

    assert _find_jdk_binaries(tmp_path) is None

    (bin_dir / names[2]).write_text("", encoding="utf-8")
    if __import__("os").name != "nt":
        for name in names:
            (bin_dir / name).chmod(0o755)
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "jfr").write_text("internal JFR library", encoding="utf-8")
    found = _find_jdk_binaries(tmp_path)
    assert found is not None
    assert set(found) == set(names)
    assert all(path.parent == bin_dir for path in found.values())


def test_jdk_resolver_uses_java_home_before_path(tmp_path, monkeypatch):
    import os
    import shutil
    from architecture_model.java_runtime_adapter import _resolve_java_tools

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    names = ("java.exe", "javac.exe", "jfr.exe") if os.name == "nt" else ("java", "javac", "jfr")
    for name in names:
        (bin_dir / name).write_text("", encoding="utf-8")

    monkeypatch.setenv("JAVA_HOME", str(tmp_path))
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    found = _resolve_java_tools()
    assert all(path.parent == bin_dir for path in found.values())
