"""Rust runtime adapter using cargo-llvm-cov LCOV coverage reports.

The adapter identifies Rust source files with executed lines. Coverage does
not provide runtime caller/callee edges, so no call relationships are fabricated.
A selected Cargo.toml must describe a bounded executable package.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from architecture_model.runtime_model import RuntimeArchitecture


IGNORED_DIRS = {
    ".git", "target", "vendor", "tests", "test", "benches",
    "examples", ".cargo", "node_modules", "coverage",
}
SERVER_MARKERS = (
    "httpserver::bind", "httpserver::new", "axum::serve", "warp::serve",
    "actix_web::httpserver", "rocket::build", "tcp_listener::bind",
)


def discover_rust_entrypoints(worktree_path):
    """Find Cargo packages with a bounded src/main.rs entry point."""
    root = Path(worktree_path).resolve()
    candidates = []
    for manifest in root.rglob("Cargo.toml"):
        relative = manifest.relative_to(root)
        if any(part.lower() in IGNORED_DIRS for part in relative.parts[:-1]):
            continue
        package_root = manifest.parent
        main_files = [package_root / "src" / "main.rs"]
        try:
            text = manifest.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # Also support an explicitly declared [[bin]] path.
        for match in re.finditer(r'(?ms)^\s*\[\[bin\]\](.*?)(?=^\s*\[|\Z)', text):
            path_match = re.search(r'(?m)^\s*path\s*=\s*"([^"]+)"', match.group(1))
            if path_match:
                main_files.append(package_root / path_match.group(1))
        entry = next((path for path in main_files if path.is_file()), None)
        if not entry:
            continue
        try:
            source = entry.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not re.search(r"\\bfn\\s+main\\s*\\(", source):
            continue
        if any(marker in source.lower() for marker in SERVER_MARKERS):
            continue
        candidates.append(relative.as_posix())
    return sorted(
        set(candidates),
        key=lambda value: (
            0 if Path(value).parent == Path(".") else 1,
            len(Path(value).parts),
            value.lower(),
        ),
    )


def run_rust_version(worktree_path, scenario, timeout=600):
    """Execute a Cargo binary under cargo-llvm-cov and parse its LCOV output."""
    root = Path(worktree_path).resolve()
    manifest = (root / scenario).resolve()
    try:
        manifest.relative_to(root)
    except ValueError as error:
        raise ValueError("Cargo manifest must be inside the selected repository.") from error
    if not manifest.is_file() or manifest.name != "Cargo.toml":
        raise FileNotFoundError(f"Rust Cargo manifest not found: {manifest}")
    cargo = shutil.which("cargo")
    if not cargo:
        raise RuntimeError("Rust/Cargo is required for Rust runtime coverage but cargo was not found.")
    if not shutil.which("cargo-llvm-cov"):
        raise RuntimeError(
            "cargo-llvm-cov is required for Rust runtime coverage. Install it with "
            "'cargo install cargo-llvm-cov --locked' and add the Rust llvm-tools-preview component."
        )

    report = root.parent / (manifest.parent.name + "_runtime_coverage.lcov")
    try:
        process = subprocess.run(
            [cargo, "llvm-cov", "run", "--manifest-path", str(manifest),
             "--lcov", "--output-path", str(report)],
            cwd=str(manifest.parent), capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"Rust runtime scenario timed out after {timeout} seconds: {scenario}") from error
    if process.returncode != 0:
        details = (process.stderr or process.stdout or "cargo llvm-cov failed")[-5000:]
        raise RuntimeError(f"Rust runtime scenario failed:\n{details}")
    if not report.is_file():
        raise RuntimeError("cargo-llvm-cov did not produce an LCOV report.")

    architecture = RuntimeArchitecture(entry_point=scenario)
    current_source = None
    current_executed = False

    def retain_current():
        if current_source and current_executed:
            try:
                relative = current_source.relative_to(root).as_posix()
            except (ValueError, OSError, RuntimeError):
                return
            if not any(part.lower() in IGNORED_DIRS for part in Path(relative).parts):
                architecture.modules.add(relative)

    for line in report.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("SF:"):
            retain_current()
            source = Path(line[3:])
            current_source = (source if source.is_absolute() else (manifest.parent / source)).resolve()
            current_executed = False
        elif line.startswith("DA:"):
            try:
                _, hits = line[3:].split(",", 1)
                if int(hits) > 0:
                    current_executed = True
            except (ValueError, TypeError):
                continue
        elif line == "end_of_record":
            retain_current()
            current_source = None
            current_executed = False
    retain_current()
    return architecture
