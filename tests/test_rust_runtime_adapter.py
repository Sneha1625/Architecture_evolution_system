import shutil
import subprocess

import pytest

from architecture_model.rust_runtime_adapter import (
    discover_rust_entrypoints,
    run_rust_version,
)


pytestmark = pytest.mark.skipif(
    not shutil.which("cargo") or not shutil.which("cargo-llvm-cov"),
    reason="Rust Cargo and cargo-llvm-cov are not installed in this test environment",
)


def test_rust_runtime_adapter_reports_executed_project_sources(tmp_path):
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "sample_runtime"\nversion = "0.1.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.rs").write_text(
        "mod helper;\nfn main() { println!(\"{}\", helper::calculate()); }\n",
        encoding="utf-8",
    )
    (source / "helper.rs").write_text(
        "pub fn calculate() -> u64 { let mut total = 0; "
        "for value in 0..1000000 { total += value; } total }\n",
        encoding="utf-8",
    )

    architecture = run_rust_version(tmp_path, "Cargo.toml", timeout=180)

    assert "src/main.rs" in architecture.modules
    assert "src/helper.rs" in architecture.modules
    assert architecture.total_calls == 0


def test_rust_entrypoint_discovery_requires_main_and_skips_server(tmp_path):
    project = tmp_path / "console"
    (project / "src").mkdir(parents=True)
    (project / "Cargo.toml").write_text(
        '[package]\nname = "console"\nversion = "0.1.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    (project / "src" / "main.rs").write_text("fn main() { println!(\"ok\"); }\n", encoding="utf-8")
    web = tmp_path / "web"
    (web / "src").mkdir(parents=True)
    (web / "Cargo.toml").write_text(
        '[package]\nname = "web"\nversion = "0.1.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    (web / "src" / "main.rs").write_text(
        "fn main() { axum::serve(listener, app); }\n", encoding="utf-8"
    )

    candidates = discover_rust_entrypoints(tmp_path)

    assert "console/Cargo.toml" in candidates
    assert "web/Cargo.toml" not in candidates
