"""Go runtime adapter based on compiler-instrumented coverage.

Go's built-in coverage instrumentation identifies project source files that
actually execute. It does not claim to provide function-call edges; those are
left empty rather than inferred or fabricated.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from architecture_model.runtime_model import RuntimeArchitecture


IGNORED_DIRS = {
    ".git", "vendor", "testdata", "node_modules", "build", "dist",
    "coverage", ".idea", ".vscode",
}
SERVER_MARKERS = (
    "http.listenandserve(", "http.listenandservetls(",
    "net.listen(", "router.run(", "gin.run(",
    "http.server(", "fasthttp.listenandserve(",
)


def discover_go_entrypoints(worktree_path):
    """Find explicit Go main packages that can be run as bounded scenarios."""
    root = Path(worktree_path).resolve()
    candidates = []
    for path in root.rglob("*.go"):
        relative = path.relative_to(root)
        if any(part.lower() in IGNORED_DIRS for part in relative.parts[:-1]):
            continue
        if path.name.endswith("_test.go"):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not re.search(r"(?m)^\s*package\s+main\b", source):
            continue
        if not re.search(r"(?m)^\s*func\s+main\s*\(", source):
            continue
        if any(marker in source.lower() for marker in SERVER_MARKERS):
            continue
        # A Go scenario must belong to a module so that its dependencies and
        # package boundaries can be resolved deterministically.
        if not any(parent.joinpath("go.mod").is_file() for parent in [path.parent, *path.parent.parents] if parent == root or root in parent.parents):
            continue
        candidates.append(relative.as_posix())

    def rank(value):
        name = Path(value).name.lower()
        return (0 if name == "runtime_scenario.go" else 1 if name == "main.go" else 2, len(Path(value).parts), value.lower())
    return sorted(candidates, key=rank)


def _module_root(root: Path, scenario_path: Path) -> Path:
    current = scenario_path.parent
    while True:
        if (current / "go.mod").is_file():
            return current
        if current == root or root not in current.parents:
            break
        current = current.parent
    raise FileNotFoundError(
        f"No go.mod was found between the Go scenario and repository root: {scenario_path}"
    )


def run_go_version(worktree_path, scenario, timeout=300):
    """Build and execute one Go main package with Go's native coverage mode."""
    root = Path(worktree_path).resolve()
    scenario_path = (root / scenario).resolve()
    try:
        scenario_path.relative_to(root)
    except ValueError as error:
        raise ValueError("Runtime scenario must be inside the selected repository.") from error
    if not scenario_path.is_file() or scenario_path.suffix.lower() != ".go":
        raise FileNotFoundError(f"Go runtime scenario not found: {scenario_path}")

    go = shutil.which("go")
    if not go:
        raise RuntimeError("Go is required for Go runtime tracing but was not found on PATH.")

    source = scenario_path.read_text(encoding="utf-8", errors="ignore")
    if not re.search(r"(?m)^\s*package\s+main\b", source):
        raise ValueError("The selected Go scenario must belong to package main.")
    module_root = _module_root(root, scenario_path)
    package_dir = scenario_path.parent
    architecture = RuntimeArchitecture(entry_point=scenario)
    architecture.modules.add(scenario_path.relative_to(root).as_posix())

    with tempfile.TemporaryDirectory(prefix="architecture_go_runtime_") as temporary:
        temporary_path = Path(temporary)
        binary = temporary_path / ("scenario.exe" if os.name == "nt" else "scenario")
        coverage_dir = temporary_path / "coverage"
        coverage_dir.mkdir()
        env = os.environ.copy()
        env["GOCOVERDIR"] = str(coverage_dir)
        env.setdefault("GOTOOLCHAIN", "local")

        build = subprocess.run(
            [go, "build", "-cover", "-o", str(binary), "."],
            cwd=str(package_dir), env=env, capture_output=True, text=True,
            timeout=timeout,
        )
        if build.returncode != 0:
            details = (build.stderr or build.stdout or "go build failed")[-5000:]
            raise RuntimeError(f"Go coverage build failed:\n{details}")

        try:
            process = subprocess.run(
                [str(binary)], cwd=str(module_root), env=env,
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"Go runtime scenario timed out after {timeout} seconds: {scenario}") from error
        if process.returncode != 0:
            details = (process.stderr or process.stdout or "Go program exited unsuccessfully")[-5000:]
            raise RuntimeError(f"Go runtime scenario failed ({process.returncode}):\n{details}")

        coverage_text = temporary_path / "coverage.txt"
        converted = subprocess.run(
            [go, "tool", "covdata", "textfmt", "-i", str(coverage_dir), "-o", str(coverage_text)],
            cwd=str(module_root), env=env, capture_output=True, text=True,
            timeout=timeout,
        )
        if converted.returncode != 0:
            details = (converted.stderr or converted.stdout or "go tool covdata failed")[-5000:]
            raise RuntimeError(f"Could not read Go runtime coverage:\n{details}")
        if not coverage_text.is_file():
            raise RuntimeError("Go coverage conversion produced no coverage evidence.")

        for line in coverage_text.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line or line.startswith("mode:"):
                continue
            try:
                location, count_text = line.rsplit(" ", 1)
                file_part = location.split(":", 1)[0]
                count = int(count_text)
            except (ValueError, IndexError):
                continue
            if count <= 0:
                continue
            candidate = Path(file_part)
            if not candidate.is_absolute():
                candidate = (module_root / candidate).resolve()
            else:
                candidate = candidate.resolve()
            try:
                relative = candidate.relative_to(root).as_posix()
            except (ValueError, OSError, RuntimeError):
                continue
            if any(part.lower() in IGNORED_DIRS for part in Path(relative).parts):
                continue
            architecture.modules.add(relative)

    return architecture
