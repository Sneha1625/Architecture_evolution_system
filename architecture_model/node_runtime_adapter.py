"""Node.js runtime adapter using V8 coverage and sampled CPU profiles.

Coverage identifies project files that executed. V8 CPU profiles provide sampled
caller/callee evidence; they are deliberately not presented as exact call counts.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from architecture_model.runtime_model import RuntimeArchitecture, RuntimeCall


NODE_EXTENSIONS = {".js", ".mjs", ".cjs"}


def discover_node_entrypoints(worktree_path):
    """Return conservative, bounded JavaScript entry-point candidates."""
    root = Path(worktree_path).resolve()
    preferred = (
        "runtime_scenario.js", "main.js", "cli.js",
        "index.js", "sample_project.js",
        "runtime_scenario.mjs", "main.mjs", "index.mjs",
        "runtime_scenario.cjs", "main.cjs", "index.cjs",
    )
    ignored = {
        ".git", "node_modules", "vendor", "dist", "build",
        "coverage", ".next", ".nuxt", "test", "tests",
    }
    server_markers = (
        "app.listen(", "server.listen(", "http.createserver(",
        "https.createserver(", "listen(",
    )
    candidates = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in NODE_EXTENSIONS:
            continue
        relative = path.relative_to(root)
        if any(part.lower() in ignored for part in relative.parts[:-1]):
            continue
        if path.name.endswith((".test.js", ".spec.js", ".test.mjs", ".spec.mjs")):
            continue
        if path.name.lower() not in preferred:
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(marker in source.lower() for marker in server_markers):
            continue
        candidates.append(relative.as_posix())
    order = {name: index for index, name in enumerate(preferred)}
    return sorted(candidates, key=lambda name: (order.get(Path(name).name.lower(), 999), name.lower()))


def _project_module(url, root):
    parsed = urlparse(url or "")
    if parsed.scheme != "file":
        return None
    try:
        path = Path(unquote(parsed.path))
        if os.name == "nt" and path.as_posix().startswith("/") and len(path.as_posix()) > 2 and path.as_posix()[2] == ":":
            path = Path(path.as_posix()[1:])
        path = path.resolve()
        relative = path.relative_to(root)
    except (ValueError, OSError, RuntimeError):
        return None
    if any(part.lower() in {"node_modules", "vendor", ".git", "dist", "build"} for part in relative.parts):
        return None
    return relative.as_posix()


def run_node_version(worktree_path, scenario, timeout=300):
    """Execute one JS scenario and return project-only runtime evidence."""
    root = Path(worktree_path).resolve()
    scenario_path = (root / scenario).resolve()
    try:
        scenario_path.relative_to(root)
    except ValueError as error:
        raise ValueError("Runtime scenario must be inside the selected repository.") from error
    if not scenario_path.is_file() or scenario_path.suffix.lower() not in NODE_EXTENSIONS:
        raise FileNotFoundError(f"JavaScript runtime scenario not found: {scenario_path}")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for JavaScript runtime tracing but was not found on PATH.")

    architecture = RuntimeArchitecture(entry_point=scenario)
    architecture.modules.add(scenario_path.relative_to(root).as_posix())

    with tempfile.TemporaryDirectory(prefix="architecture_node_runtime_") as temp:
        temp_path = Path(temp)
        coverage_dir = temp_path / "coverage"
        profile_dir = temp_path / "profiles"
        coverage_dir.mkdir()
        profile_dir.mkdir()
        env = os.environ.copy()
        env["NODE_V8_COVERAGE"] = str(coverage_dir)
        command = [
            node, "--cpu-prof", "--cpu-prof-interval=100",
            f"--cpu-prof-dir={profile_dir}", str(scenario_path),
        ]
        try:
            process = subprocess.run(
                command, cwd=str(root), env=env, capture_output=True,
                text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"Node.js runtime scenario timed out after {timeout} seconds: {scenario}") from error
        if process.returncode != 0:
            details = (process.stderr or process.stdout or "Node.js exited unsuccessfully")[-5000:]
            raise RuntimeError(f"Node.js runtime scenario failed ({process.returncode}):\n{details}")

        # V8 coverage is the reliable source for which project modules executed.
        for coverage_file in coverage_dir.glob("*.json"):
            try:
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for item in coverage.get("result", []):
                module = _project_module(item.get("url", ""), root)
                if not module:
                    continue
                if any(
                    int(region.get("count", 0)) > 0
                    for function in item.get("functions", [])
                    for region in function.get("ranges", [])
                ):
                    architecture.modules.add(module)

        # CPU profiles are sampled, so each retained edge is one observed
        # profile-tree edge, not an exact invocation count.
        for profile_file in profile_dir.glob("*.cpuprofile"):
            try:
                profile = json.loads(profile_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            nodes = {node.get("id"): node for node in profile.get("nodes", [])}
            for parent in profile.get("nodes", []):
                parent_frame = parent.get("callFrame", {})
                caller_module = _project_module(parent_frame.get("url", ""), root)
                if not caller_module:
                    continue
                for child_id in parent.get("children", []):
                    child = nodes.get(child_id, {})
                    child_frame = child.get("callFrame", {})
                    callee_module = _project_module(child_frame.get("url", ""), root)
                    if not callee_module:
                        continue
                    architecture.add_call(RuntimeCall(
                        caller_module=caller_module,
                        caller_function=parent_frame.get("functionName") or "(anonymous)",
                        callee_module=callee_module,
                        callee_function=child_frame.get("functionName") or "(anonymous)",
                        caller_file=caller_module,
                        callee_file=callee_module,
                    ))

    return architecture
