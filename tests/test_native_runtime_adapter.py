import shutil

import pytest

from architecture_model.native_runtime_adapter import (
    discover_native_entrypoints,
    run_native_version,
)


pytestmark = pytest.mark.skipif(
    not all(shutil.which(name) for name in ("gcc", "g++", "gcov")),
    reason="GCC, G++, and gcov are not installed in this test environment",
)


def test_c_runtime_adapter_reports_executed_project_sources(tmp_path):
    (tmp_path / "main.c").write_text(
        "#include <stdio.h>\nint helper(void);\n"
        "int main(void) { printf(\"%d\\n\", helper()); return 0; }\n",
        encoding="utf-8",
    )
    (tmp_path / "helper.c").write_text(
        "int helper(void) { int value = 0; for (int i = 0; i < 10000; ++i) value += i; return value; }\n",
        encoding="utf-8",
    )

    architecture = run_native_version(tmp_path, "main.c", timeout=60)

    assert "main.c" in architecture.modules
    assert "helper.c" in architecture.modules
    assert architecture.get_module_count() >= 2
    assert architecture.total_calls == 0


def test_cpp_runtime_adapter_reports_executed_project_sources(tmp_path):
    (tmp_path / "main.cpp").write_text(
        "#include <iostream>\nint helper();\n"
        "int main() { std::cout << helper() << std::endl; return 0; }\n",
        encoding="utf-8",
    )
    (tmp_path / "helper.cpp").write_text(
        "int helper() { int value = 0; for (int i = 0; i < 10000; ++i) value += i; return value; }\n",
        encoding="utf-8",
    )

    architecture = run_native_version(tmp_path, "main.cpp", timeout=60)

    assert "main.cpp" in architecture.modules
    assert "helper.cpp" in architecture.modules
    assert architecture.get_module_count() >= 2


def test_native_entrypoint_discovery_excludes_tests_and_server_files(tmp_path):
    (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    (tmp_path / "server.cpp").write_text(
        "int main() { listen(8080); return 0; }\n", encoding="utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.c").write_text(
        "int main(void) { return 0; }\n", encoding="utf-8"
    )

    candidates = discover_native_entrypoints(tmp_path)

    assert "main.c" in candidates
    assert "server.cpp" not in candidates
    assert "tests/test_main.c" not in candidates
