import shutil
import subprocess

import pytest

from architecture_model.php_runtime_adapter import (
    discover_php_entrypoints,
    run_php_version,
)


def _has_xdebug():
    php = shutil.which("php")
    if not php:
        return False
    result = subprocess.run(
        [php, "-r", "exit(extension_loaded('xdebug') ? 0 : 1);"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


pytestmark = pytest.mark.skipif(
    not _has_xdebug(),
    reason="PHP CLI with Xdebug is required for PHP runtime tracing",
)


def test_php_runtime_adapter_observes_project_and_included_files(tmp_path):
    (tmp_path / "main.php").write_text(
        "<?php\nrequire_once __DIR__ . '/helper.php';\n"
        "echo Helper::calculate();\n",
        encoding="utf-8",
    )
    (tmp_path / "helper.php").write_text(
        "<?php\nclass Helper { public static function calculate() { "
        "$total = 0; for ($i = 0; $i < 10000; $i++) { $total += $i; } "
        "return $total; } }\n",
        encoding="utf-8",
    )

    architecture = run_php_version(tmp_path, "main.php", timeout=60)

    assert "main.php" in architecture.modules
    assert "helper.php" in architecture.modules


def test_php_entrypoint_discovery_excludes_tests_and_server_files(tmp_path):
    (tmp_path / "main.php").write_text("<?php echo 'bounded';", encoding="utf-8")
    (tmp_path / "index.php").write_text(
        "<?php $app->run();", encoding="utf-8"
    )
    (tmp_path / "main_test.php").write_text(
        "<?php echo 'test';", encoding="utf-8"
    )

    candidates = discover_php_entrypoints(tmp_path)

    assert "main.php" in candidates
    assert "index.php" not in candidates
    assert "main_test.php" not in candidates
