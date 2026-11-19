"""PHP runtime adapter using Xdebug computerized function traces."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from architecture_model.runtime_model import RuntimeArchitecture, RuntimeCall


IGNORED_DIRS = {
    ".git", "vendor", "node_modules", "tests", "test", "cache",
    "storage", "build", "dist", "coverage",
}
SERVER_MARKERS = (
    "->run(", "->listen(", "serve_forever(", "php_sapi_name()",
    "fastcgi_finish_request(",
)
PREFERRED = (
    "runtime_scenario.php", "main.php", "cli.php",
    "index.php", "console.php", "sample_project.php",
)


def discover_php_entrypoints(worktree_path):
    """Find conventional PHP CLI scripts, excluding tests and web servers."""
    root = Path(worktree_path).resolve()
    candidates = []
    for path in root.rglob("*.php"):
        relative = path.relative_to(root)
        if any(part.lower() in IGNORED_DIRS for part in relative.parts[:-1]):
            continue
        if path.name.lower().endswith(("test.php", "tests.php", "spec.php")):
            continue
        if path.name.lower() not in PREFERRED:
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(marker in source.lower() for marker in SERVER_MARKERS):
            continue
        candidates.append(relative.as_posix())
    order = {name: index for index, name in enumerate(PREFERRED)}
    return sorted(candidates, key=lambda value: (order.get(Path(value).name.lower(), 999), value.lower()))


def _inside_project(filename, root):
    if not filename:
        return None
    path = Path(filename)
    try:
        resolved = path.resolve()
        return resolved.relative_to(root).as_posix()
    except (ValueError, OSError, RuntimeError):
        return None


def _parse_xdebug_trace(trace_path, root, entry_point):
    architecture = RuntimeArchitecture(entry_point=entry_point)
    stack = {}
    for raw_line in trace_path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = raw_line.split("\t")
        if len(fields) < 10 or fields[2] != "0":
            continue
        try:
            level = int(fields[0])
        except ValueError:
            continue
        function_name = fields[5] or "(unknown)"
        # Xdebug computerized entry records include include/require path in
        # column 8 and the executing source filename in column 9 (1-based).
        filename = fields[8]
        module = _inside_project(filename, root)
        if module:
            architecture.modules.add(module)
        current = {
            "function": function_name,
            "module": module,
        }
        parent = stack.get(level - 1)
        if parent and parent.get("module") and module:
            architecture.add_call(RuntimeCall(
                caller_module=parent["module"],
                caller_function=parent["function"],
                callee_module=module,
                callee_function=function_name,
                caller_file=parent["module"],
                callee_file=module,
            ))
        stack[level] = current
        # Remove deeper frames if a trace reuses a level after a return.
        for deeper in [key for key in stack if key > level]:
            del stack[deeper]
    return architecture


def run_php_version(worktree_path, scenario, timeout=300):
    """Run one PHP scenario with Xdebug tracing enabled."""
    root = Path(worktree_path).resolve()
    scenario_path = (root / scenario).resolve()
    try:
        scenario_path.relative_to(root)
    except ValueError as error:
        raise ValueError("PHP runtime scenario must be inside the selected repository.") from error
    if not scenario_path.is_file() or scenario_path.suffix.lower() != ".php":
        raise FileNotFoundError(f"PHP runtime scenario not found: {scenario_path}")
    php = shutil.which("php")
    if not php:
        raise RuntimeError("PHP CLI is required for PHP runtime tracing but was not found.")
    extension_check = subprocess.run(
        [php, "-r", "exit(extension_loaded('xdebug') ? 0 : 1);"],
        capture_output=True, text=True, timeout=15,
    )
    if extension_check.returncode != 0:
        raise RuntimeError(
            "Xdebug is required for PHP runtime tracing. Enable/install the Xdebug "
            "extension with its 'trace' mode; static PHP architecture recovery remains available."
        )

    with tempfile.TemporaryDirectory(prefix="architecture_php_runtime_") as temporary:
        temp = Path(temporary)
        trace_path = temp / "runtime_trace"
        prepend = temp / "trace_prepend.php"
        prepend.write_text(
            "<?php\n"
            f"xdebug_start_trace({str(trace_path)!r}, XDEBUG_TRACE_COMPUTERIZED | XDEBUG_TRACE_NAKED_FILENAME);\n"
            "register_shutdown_function(function () { xdebug_stop_trace(); });\n",
            encoding="utf-8",
        )
        command = [
            php,
            "-d", "xdebug.mode=trace",
            "-d", "xdebug.start_with_request=no",
            "-d", f"auto_prepend_file={prepend}",
            str(scenario_path),
        ]
        try:
            process = subprocess.run(
                command, cwd=str(root), capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"PHP runtime scenario timed out after {timeout} seconds: {scenario}") from error
        if process.returncode != 0:
            details = (process.stderr or process.stdout or "PHP exited unsuccessfully")[-5000:]
            raise RuntimeError(f"PHP runtime scenario failed ({process.returncode}):\n{details}")
        if not trace_path.is_file():
            raise RuntimeError("Xdebug did not produce a function trace.")
        return _parse_xdebug_trace(trace_path, root, scenario)
