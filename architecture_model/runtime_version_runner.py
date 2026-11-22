"""
Runtime Version Runner

Executes corresponding, bounded workloads against two isolated Git worktrees
and captures language-specific runtime architecture evidence.

This allows the Architecture Evolution System to compare:

    Runtime Architecture V1
            vs
    Runtime Architecture V2

without checking out or modifying the main working repository.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

from architecture_model.runtime_model import (
    RuntimeArchitecture,
    RuntimeCall,
)


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARENT_DIR = PROJECT_ROOT.parent

DEFAULT_V1_PATH = PARENT_DIR / "runtime_v1"
DEFAULT_V2_PATH = PARENT_DIR / "runtime_v2"

DEFAULT_SCENARIO = ""


# Python 3.13 removed several deprecated standard-library modules. These
# redistributions restore the original import names inside the isolated
# runtime environment, without modifying the user's Python installation or
# the repository being analyzed.
LEGACY_STDLIB_DISTRIBUTIONS = {
    "aifc": "standard-aifc",
    "asynchat": "standard-asynchat",
    "asyncore": "standard-asyncore",
    "audioop": "audioop-lts",
    "cgi": "standard-cgi",
    "cgitb": "standard-cgitb",
    "chunk": "standard-chunk",
    "crypt": "standard-crypt",
    "imghdr": "standard-imghdr",
    "mailcap": "standard-mailcap",
    "nntplib": "standard-nntplib",
    "pipes": "standard-pipes",
    "sndhdr": "standard-sndhdr",
    "sunau": "standard-sunau",
    "telnetlib": "standard-telnetlib",
    "uu": "standard-uu",
    "xdrlib": "standard-xdrlib",
}


def _missing_module_name(error_text):
    """Extract a missing import name from a Python exception message."""
    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_text or "")
    return match.group(1).split(".", 1)[0] if match else None




def _python_entrypoint_runtime_blocker(worktree_path, entrypoint):
    """Find physical-camera blockers through the local Python import graph."""
    import ast

    root = Path(worktree_path).resolve()
    pending = [Path(entrypoint)]
    visited = set()
    hardware_patterns = (
        re.compile(r"\bcv2\s*\.\s*VideoCapture\b", re.IGNORECASE),
        re.compile(r"\bVideoCapture\s*\(", re.IGNORECASE),
        re.compile(r"\bCAP_(?:DSHOW|MSMF|V4L2|AVFOUNDATION)\b", re.IGNORECASE),
        re.compile(r"\bPicamera2\s*\(", re.IGNORECASE),
        re.compile(r"\bVideoStream\s*\(", re.IGNORECASE),
        re.compile(r"could not open camera source", re.IGNORECASE),
        re.compile(r"failed to open camera", re.IGNORECASE),
    )

    def local_module_paths(module_name, base):
        if not module_name:
            return []
        parts = [part for part in module_name.split(".") if part]
        if not parts:
            return []
        candidate = base.joinpath(*parts)
        found = []
        for item in (candidate.with_suffix(".py"), candidate / "__init__.py"):
            try:
                resolved = item.resolve()
                resolved.relative_to(root)
                if resolved.is_file():
                    found.append(resolved)
            except (OSError, ValueError, RuntimeError):
                continue
        return found

    while pending and len(visited) < 250:
        relative = pending.pop()
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except (ValueError, RuntimeError):
            continue
        if path in visited or not path.is_file() or path.suffix.lower() not in {".py", ".pyw"}:
            continue
        visited.add(path)

        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            if any(pattern.search(source) for pattern in hardware_patterns):
                return "camera"
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, ValueError):
            continue

        # Automatic comparison must never block waiting for a person at a
        # keyboard. Detect interactive input in the entry point and its local
        # imports before selecting a workload.
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in {"input", "raw_input"}:
                    return "keyboard_input"
                if isinstance(func, ast.Attribute):
                    receiver = func.value
                    if func.attr in {"read", "readline"} and (
                        (isinstance(receiver, ast.Attribute)
                         and isinstance(receiver.value, ast.Name)
                         and receiver.value.id == "sys"
                         and receiver.attr == "stdin")
                        or (isinstance(receiver, ast.Name) and receiver.id == "stdin")
                    ):
                        return "keyboard_input"
                    if func.attr == "getpass" and isinstance(receiver, ast.Name) and receiver.id == "getpass":
                        return "keyboard_input"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    pending.extend(item.relative_to(root) for item in local_module_paths(alias.name, root))
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    package_parts = list(path.parent.relative_to(root).parts)
                    if node.level > 1:
                        package_parts = package_parts[:max(0, len(package_parts) - node.level + 1)]
                    if node.module:
                        package_parts.extend(node.module.split("."))
                    base_module = ".".join(package_parts)
                    for item in local_module_paths(base_module, root):
                        pending.append(item.relative_to(root))
                    child_base = root.joinpath(*package_parts)
                    for alias in node.names:
                        if alias.name != "*":
                            pending.extend(item.relative_to(root) for item in local_module_paths(alias.name, child_base))
                else:
                    if node.module:
                        pending.extend(item.relative_to(root) for item in local_module_paths(node.module, root))
                        child_base = root.joinpath(*node.module.split("."))
                    else:
                        child_base = root.joinpath(*path.parent.relative_to(root).parts)
                    for alias in node.names:
                        if alias.name != "*":
                            pending.extend(item.relative_to(root) for item in local_module_paths(alias.name, child_base))

    return None


def _is_flask_test_client_project(worktree_path):
    """Return True for a Flask app that exposes routes suitable for test_client."""
    root = Path(worktree_path).resolve()
    app_file = root / "app.py"
    template_file = root / "templates" / "index.html"
    if not app_file.is_file() or not template_file.is_file():
        return False
    try:
        import ast
        tree = ast.parse(app_file.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError, ValueError):
        return False

    imports_flask = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "flask"
        and any(alias.name == "Flask" for alias in node.names)
        for node in ast.walk(tree)
    )
    has_route = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "route"
            for decorator in node.decorator_list
        )
        for node in tree.body
    )
    starts_server = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        for node in ast.walk(tree)
    )
    return imports_flask and has_route and starts_server


def _create_automatic_flask_test_client_workload(v1_path, v2_path, temporary_root):
    """Exercise Flask routes with its in-process test client, never starting a server."""
    if not all(_is_flask_test_client_project(path) for path in (v1_path, v2_path)):
        raise FileNotFoundError(
            "A shared Flask application with app.py and templates/index.html was not found."
        )

    workload = Path(temporary_root) / "flask_test_client_runtime.py"
    workload.write_text(
        "import json\n"
        "import os\n"
        "import urllib.request\n"
        "os.environ.setdefault('API_KEY', 'architecture-runtime-test-key')\n"
        "os.environ.setdefault('MODEL_URL', 'https://runtime.invalid/sentiment')\n"
        "class _RuntimeResponse:\n"
        "    def read(self):\n"
        "        return json.dumps([{'label': 'POSITIVE'}]).encode('utf-8')\n"
        "def _runtime_urlopen(request, *args, **kwargs):\n"
        "    return _RuntimeResponse()\n"
        "urllib.request.urlopen = _runtime_urlopen\n"
        "from app import app\n"
        "client = app.test_client()\n"
        "get_response = client.get('/')\n"
        "assert get_response.status_code == 200, get_response.status_code\n"
        "post_response = client.post('/', data={'text': 'runtime comparison test'})\n"
        "assert post_response.status_code == 200, post_response.status_code\n"
        "assert b'POSITIVE' in post_response.data, post_response.data[:500]\n",
        encoding="utf-8",
    )
    return str(workload)




def _is_smartmonitor_project(worktree_path):
    """Recognize SmartMonitor's safe, non-camera utility workflow."""
    root = Path(worktree_path).resolve()
    tracker_file = root / "tracker.py"
    timetable_file = root / "timetable_helper.py"
    config_file = root / "config.py"
    if not all(item.is_file() for item in (tracker_file, timetable_file, config_file)):
        return False
    try:
        import ast
        tracker_tree = ast.parse(tracker_file.read_text(encoding="utf-8", errors="ignore"))
        timetable_tree = ast.parse(timetable_file.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError, ValueError):
        return False
    tracker_api = any(
        isinstance(node, ast.ClassDef)
        and node.name == "FaceTracker"
        and any(
            isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            and child.name == "update"
            for child in node.body
        )
        for node in tracker_tree.body
    )
    timetable_api = {
        node.name for node in timetable_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return tracker_api and {
        "slot_to_mins", "load_timetable", "get_current_session",
        "get_all_todays_sessions", "get_session_email",
    }.issubset(timetable_api)


def _create_automatic_smartmonitor_workload(v1_path, v2_path, temporary_root):
    """Exercise deterministic tracking/timetable logic without camera, email, or database writes."""
    if not all(_is_smartmonitor_project(path) for path in (v1_path, v2_path)):
        raise FileNotFoundError(
            "The selected commits do not both contain the supported SmartMonitor utility modules."
        )
    workload = Path(temporary_root) / "smartmonitor_runtime_workload.py"
    workload.write_text(
        "from tracker import FaceTracker\n"
        "from timetable_helper import (\n"
        "    slot_to_mins, load_timetable, get_current_session,\n"
        "    get_all_todays_sessions, get_session_email,\n"
        ")\n"
        "assert slot_to_mins('08:00 AM') == 480\n"
        "assert slot_to_mins('12:00 PM') == 720\n"
        "timetable = load_timetable()\n"
        "assert isinstance(timetable, dict)\n"
        "current_session = get_current_session()\n"
        "assert isinstance(current_session, dict)\n"
        "assert {'subject', 'faculty', 'day', 'period'}.issubset(current_session)\n"
        "todays_sessions = get_all_todays_sessions()\n"
        "assert isinstance(todays_sessions, list)\n"
        "session_email = get_session_email()\n"
        "assert session_email is None or isinstance(session_email, str)\n"
        "tracker = FaceTracker()\n"
        "first = tracker.update([{'cx': 100, 'cy': 100, 'raw_name': 'runtime-student'}])\n"
        "assert first[0]['stable_name'] == 'runtime-student'\n"
        "second = tracker.update([{'cx': 104, 'cy': 102, 'raw_name': 'runtime-student'}])\n"
        "assert second[0]['stable_name'] == 'runtime-student'\n",
        encoding="utf-8",
    )
    return str(workload)

def discover_python_entrypoints(worktree_path):
    """Find likely bounded Python execution scenarios without guessing.

    A repository may contain many importable modules (settings, config,
    models, helpers). Importing one of those is not equivalent to exercising
    the application. Prefer explicit executable entry points and scripts
    with clear top-level execution; never fall back to an arbitrary module.
    """
    import ast

    root = Path(worktree_path).resolve()
    preferred = {
        "runtime_scenario.py": 0,
        "main.py": 1,
        "cli.py": 2,
        "run.py": 3,
        "__main__.py": 4,
        "manage.py": 5,
    }
    ignored = {
        ".git", ".venv", "venv", "env", "__pycache__", "site-packages",
        "node_modules", "tests", "test", "build", "dist", ".next",
        "migrations", "vendor",
    }
    non_entry_names = {
        "__init__.py", "config.py", "settings.py", "constants.py",
        "models.py", "schemas.py", "serializers.py", "admin.py",
        "apps.py", "wsgi.py", "asgi.py",
    }
    server_markers = (
        "streamlit.run", "uvicorn.run(", "hypercorn.run(",
        "gradio.launch(", "app.run(", "runserver(",
    )
    candidates = []

    for path in root.rglob("*.py"):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part.lower() in ignored for part in relative.parts[:-1]):
            continue
        if path.name.endswith("_test.py"):
            continue
        # Never select the standalone demo calculator as the application's
        # runtime workload; it is unrelated to the loaded repository logic.
        if path.name.lower() == "sample_project.py":
            continue
        if path.name.lower() in non_entry_names:
            continue

        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            if len(source) > 500000:
                continue
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, ValueError):
            continue

        call_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    call_names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    call_names.add(node.func.attr)

        # This root-level script runs the real parser and architecture
        # recovery pipeline. It is an application workflow, unlike the
        # repository's small synthetic demonstration scripts.
        is_recovery_workflow = (
            path.name.lower() == "test_architecture_recovery.py"
            and {"parse_folder", "recover_architecture"}.issubset(call_names)
        )
        if path.name.startswith("test_") and not is_recovery_workflow:
            continue
        if is_recovery_workflow:
            candidates.append((1000, -1, relative.as_posix()))
            continue

        lowered = source.lower()
        # Never start a long-running development server as an automated
        # comparison scenario. Framework modules remain part of static analysis.
        if any(marker in lowered for marker in server_markers):
            continue

        # Exclude entry points that require physical hardware or interactive
        # keyboard input. Runtime comparisons must be fully automatic.
        if _python_entrypoint_runtime_blocker(root, relative):
            continue

        has_main_guard = False
        has_cli_signal = False
        has_direct_main_call = False
        has_top_level_work = False

        for node in tree.body:
            if isinstance(node, ast.If):
                test = ast.dump(node.test, include_attributes=False)
                if "__name__" in test and "__main__" in test:
                    has_main_guard = True
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue
            has_top_level_work = True

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else (
                    func.attr if isinstance(func, ast.Attribute) else ""
                )
                if name in {"ArgumentParser", "parse_args", "click", "typer"}:
                    has_cli_signal = True
                if name == "main":
                    has_direct_main_call = True

        filename_rank = preferred.get(path.name.lower(), 99)
        # A named entry point is useful only if it contains executable work.
        # For other files require explicit CLI/main evidence or a meaningful
        # top-level script; this prevents config.py-like files being selected.
        if not (has_main_guard or has_cli_signal or has_direct_main_call or has_top_level_work):
            continue
        if filename_rank == 99 and not (has_main_guard or has_cli_signal or has_direct_main_call):
            continue

        score = (
            100 if has_main_guard else 0
        ) + (
            35 if has_cli_signal else 0
        ) + (
            25 if has_direct_main_call else 0
        ) + (
            20 if filename_rank < 99 else 0
        ) - min(len(relative.parts), 10)
        candidates.append((score, filename_rank, relative.as_posix()))

    if _is_flask_test_client_project(root):
        candidates.append((1100, -1, 'flask:test-client'))
    if _is_smartmonitor_project(root):
        candidates.append((1090, -1, 'python:smartmonitor-smoke'))

    candidates.sort(key=lambda item: (-item[0], item[1], item[2].lower()))
    return [item[2] for item in candidates[:100]]

# ============================================================
# CHILD-PROCESS TRACER
# ============================================================

TRACER_SCRIPT = r'''
import ast
import hashlib
import inspect
import json
import os
import runpy
import sys
import textwrap
import types
from pathlib import Path
from functools import lru_cache

worktree = Path(sys.argv[1]).resolve()
scenario = sys.argv[2]
output_file = Path(sys.argv[3]).resolve()
stdin_file = Path(sys.argv[4]).resolve() if len(sys.argv) > 4 else None

# Use an explicit file-backed stdin for the scenario. This avoids losing
# Streamlit-supplied input between the outer tracer process and runpy.
if stdin_file is not None:
    sys.stdin = stdin_file.open("r", encoding="utf-8")

sys.path.insert(0, str(worktree))

calls = []
executed_modules = set()
executed_functions = set()
executed_function_fingerprints = {}
executed_function_counts = {}
total_python_calls = 0


def _stable_code_value(value):
    if isinstance(value, types.CodeType):
        return {
            "name": value.co_name,
            "bytecode": value.co_code.hex(),
            "constants": [_stable_code_value(item) for item in value.co_consts],
            "names": list(value.co_names),
            "varnames": list(value.co_varnames),
        }
    if isinstance(value, tuple):
        return [_stable_code_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return type(value).__name__


@lru_cache(maxsize=4096)
def function_fingerprint(code):
    """Fingerprint normalized source for the exact code object that ran."""
    try:
        source = textwrap.dedent(inspect.getsource(code))
        normalized = ast.dump(ast.parse(source), include_attributes=False)
    except (OSError, IOError, TypeError, IndentationError, SyntaxError):
        normalized = json.dumps({
            "bytecode": code.co_code.hex(),
            "constants": _stable_code_value(code.co_consts),
            "names": list(code.co_names),
            "varnames": list(code.co_varnames),
            "argcount": code.co_argcount,
            "kwonlyargcount": code.co_kwonlyargcount,
        }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@lru_cache(maxsize=8192)
def is_project_file(filename):
    """Accept only real Python source files physically inside this commit's worktree.

    Frozen/builtin frames often expose pseudo-filenames such as
    '<frozen importlib._bootstrap>'. Path.resolve() would incorrectly treat
    those relative pseudo-filenames as files under the current worktree.
    """
    if not filename:
        return False

    raw_filename = str(filename)
    if raw_filename.startswith("<") and raw_filename.endswith(">"):
        return False

    try:
        source_path = Path(raw_filename).resolve(strict=True)
        relative_path = source_path.relative_to(worktree)
        # Test drivers are workload inputs, not application architecture modules.
        if source_path.name.lower().startswith("test_") or any(
            part.lower() in {"tests", "test"} for part in relative_path.parts[:-1]
        ):
            return False
        return source_path.is_file() and source_path.suffix.lower() in {".py", ".pyw"}
    except (ValueError, OSError, RuntimeError):
        return False

@lru_cache(maxsize=8192)
def module_from_filename(filename):
    """Resolve a module name from a filename, with caching."""
    try:
        relative = Path(filename).resolve().relative_to(worktree)
        return ".".join(relative.with_suffix("").parts) or "__main__"
    except (ValueError, OSError, RuntimeError):
        return "__main__"

def module_name(frame):
    name = frame.f_globals.get("__name__", "")

    if name and name != "__main__":
        return name

    return module_from_filename(frame.f_code.co_filename)

def is_architecture_module(module, filename):
    return bool(module) and is_project_file(filename)

def profiler(frame, event, arg):
    global total_python_calls

    if event != "call":
        return profiler

    callee_module = module_name(frame)

    # Record every project module whose function actually executes,
    # including entry-point modules that do not make a cross-file call.
    if is_architecture_module(callee_module, frame.f_code.co_filename):
        executed_modules.add(callee_module)
        qualified_name = f"{callee_module}.{frame.f_code.co_qualname}"
        executed_functions.add(qualified_name)
        executed_function_counts[qualified_name] = executed_function_counts.get(qualified_name, 0) + 1
        executed_function_fingerprints.setdefault(
            qualified_name, function_fingerprint(frame.f_code)
        )

    caller = frame.f_back
    if caller is None:
        return profiler

    caller_module = module_name(caller)

    # Keep dependency edges restricted to calls between project files.
    if not is_architecture_module(caller_module, caller.f_code.co_filename):
        return profiler

    if not is_architecture_module(callee_module, frame.f_code.co_filename):
        return profiler

    # Keep same-module function calls too. They are useful runtime evidence
    # for small/demo projects even when no cross-module edge is exercised.
    caller_file = caller.f_code.co_filename
    callee_file = frame.f_code.co_filename

    if not is_project_file(caller_file):
        return profiler

    if not is_project_file(callee_file):
        return profiler

    total_python_calls += 1

    calls.append({
        "caller_module": caller_module,
        "caller_function": caller.f_code.co_name,
        "callee_module": callee_module,
        "callee_function": frame.f_code.co_name,
        "caller_file": str(Path(caller_file).resolve()),
        "callee_file": str(Path(callee_file).resolve()),
    })

    return profiler

scenario_path = worktree / scenario

if not scenario_path.exists():
    raise FileNotFoundError(f"Scenario not found: {scenario_path}")

# A Python entry-point script often performs its work at module scope.
# Include it only when it is part of the selected repository. Automatically
# generated workload drivers live outside the worktree and are not project code.
try:
    relative_entrypoint = scenario_path.resolve().relative_to(worktree)
    entrypoint_module = ".".join(relative_entrypoint.with_suffix("").parts) or "__main__"
except (ValueError, OSError, RuntimeError):
    entrypoint_module = None
if entrypoint_module and not scenario_path.name.lower().startswith("test_"):
    executed_modules.add(entrypoint_module)

old_cwd = Path.cwd()
execution_error = None

try:
    os.chdir(worktree)
    sys.setprofile(profiler)

    try:
        runpy.run_path(str(scenario_path), run_name="__main__")
    except SystemExit as error:
        if error.code not in (None, 0):
            execution_error = f"SystemExit: {error.code}"
    except Exception as error:
        execution_error = f"{type(error).__name__}: {error}"
    finally:
        sys.setprofile(None)

finally:
    os.chdir(old_cwd)

result = {
    "entry_point": scenario,
    "worktree": str(worktree),
    "total_profiled_calls": total_python_calls,
    "modules": sorted(executed_modules),
    "executed_functions": sorted(executed_functions),
    "executed_function_fingerprints": dict(sorted(executed_function_fingerprints.items())),
    "executed_function_counts": dict(sorted(executed_function_counts.items())),
    "calls": calls,
    "error": execution_error,
}

output_file.write_text(
    json.dumps(result, indent=2),
    encoding="utf-8",
)

if execution_error:
    print(
        f"Runtime scenario failed: {execution_error}",
        file=sys.stderr,
    )
    sys.exit(1)
'''


# ============================================================
# VALIDATION
# ============================================================

def validate_worktree(
    worktree_path: Path,
    scenario: str,
) -> None:
    """
    Validate the selected Git worktree and scenario.
    """

    if not worktree_path.exists():

        raise FileNotFoundError(
            f"Worktree does not exist: "
            f"{worktree_path}"
        )

    if not worktree_path.is_dir():

        raise NotADirectoryError(
            f"Worktree is not a directory: "
            f"{worktree_path}"
        )

    if not scenario:
        candidates = discover_python_entrypoints(worktree_path)
        if not candidates:
            raise FileNotFoundError("No Python entry point found in this repository. Add/select a runnable .py entry point.")
        scenario = candidates[0]

    # These virtual workloads are generated outside the selected worktree.
    if scenario == "python:smartmonitor-smoke":
        if not _is_smartmonitor_project(worktree_path):
            raise FileNotFoundError("The selected commit does not expose the required SmartMonitor utility API.")
        return

    # npm:test is a virtual scenario executed from the selected commit's package.json.
    if scenario == "npm:test":
        if not (worktree_path / "package.json").is_file():
            raise FileNotFoundError("The selected commit has no package.json for npm:test.")
        return

    scenario_path = (
        worktree_path / scenario
    )

    if not scenario_path.exists():

        raise FileNotFoundError(
            f"Scenario does not exist: "
            f"{scenario_path}"
        )


# ============================================================
# GIT VERSION
# ============================================================

def get_commit_hash(
    worktree_path: Path,
) -> str:
    """
    Return the short Git commit hash for a worktree.
    """

    try:

        result = subprocess.run(
            [
                "git",
                "-C",
                str(worktree_path),
                "rev-parse",
                "--short",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        return result.stdout.strip()

    except Exception:

        return "unknown"


# ============================================================# RECONSTRUCT RUNTIME ARCHITECTURE
# ============================================================

def build_runtime_architecture(
    trace_data: dict,
) -> RuntimeArchitecture:
    """
    Convert child-process runtime trace JSON into a
    RuntimeArchitecture object.
    """

    architecture = RuntimeArchitecture(
        entry_point=trace_data.get(
            "entry_point",
            "",
        )
    )

    # Include all project modules that executed, even when a module
    # did not participate in a cross-module relationship.
    architecture.modules.update(
        trace_data.get("modules", [])
    )
    architecture.executed_functions.update(
        trace_data.get("executed_functions", [])
    )
    architecture.executed_function_fingerprints.update(
        trace_data.get("executed_function_fingerprints", {})
    )
    architecture.executed_function_counts.update(
        trace_data.get("executed_function_counts", {})
    )

    for item in trace_data.get(
        "calls",
        [],
    ):

        call = RuntimeCall(
            caller_module=item.get(
                "caller_module",
                "",
            ),
            caller_function=item.get(
                "caller_function",
                "",
            ),
            callee_module=item.get(
                "callee_module",
                "",
            ),
            callee_function=item.get(
                "callee_function",
                "",
            ),
            caller_file=item.get(
                "caller_file",
                "",
            ),
            callee_file=item.get(
                "callee_file",
                "",
            ),
        )

        architecture.add_call(
            call
        )

    return architecture


def _requirements_files(worktree_path: Path, scenario: str):
    """Return requirements files that belong to the selected scenario."""
    scenario_parent = (Path(worktree_path) / scenario).parent
    candidates = [
        Path(worktree_path) / "requirements.txt",
        scenario_parent / "requirements.txt",
    ]
    return [
        candidate for candidate in dict.fromkeys(candidates)
        if candidate.is_file()
    ]


def _requirements_need_python312(worktree_paths, scenario: str) -> bool:
    """Detect common pinned scientific packages that cannot build on Python 3.14."""
    legacy_patterns = (
        re.compile(r"^\s*numpy\s*(?:==|<=|<)\s*1\.", re.IGNORECASE),
        re.compile(r"^\s*mediapipe\s*(?:==|<=|<)\s*0\.", re.IGNORECASE),
    )
    for worktree_path in worktree_paths:
        for requirements_file in _requirements_files(Path(worktree_path), scenario):
            try:
                lines = requirements_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for line in lines:
                requirement = line.split("#", 1)[0].strip()
                if any(pattern.search(requirement) for pattern in legacy_patterns):
                    return True
    return False


def _select_python_for_pair(v1_path: Path, v2_path: Path, scenario: str):
    """Choose one compatible base interpreter for both snapshots."""
    if sys.version_info < (3, 13) or not _requirements_need_python312(
        (v1_path, v2_path), scenario
    ):
        return Path(sys.executable)

    # On Windows, use the Python launcher to locate the separately installed
    # 3.12 interpreter. Never change the user's global/default Python.
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["py", "-3.12", "-c", "import sys; print(sys.executable)"],
                capture_output=True, text=True, check=True, timeout=15,
            )
            candidate = Path(result.stdout.strip())
            if candidate.is_file():
                return candidate
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError(
                "This repository pins dependencies that require Python 3.12, "
                "but the Python 3.12 launcher could not be started. Install Python 3.12 "
                "or verify that 'py -3.12' works, then retry."
            ) from error
    raise RuntimeError(
        "This repository pins dependencies that require Python 3.12. "
        "The current runtime is not Windows and no compatible interpreter "
        "was selected automatically. Configure Python 3.12 and retry."
    )


def _prepare_runtime_interpreter(
    worktree_path: Path,
    scenario: str,
    environment_path: Path,
    python_executable: Path | None = None,
):
    """Create an isolated environment from the selected compatible Python."""
    requirements_files = _requirements_files(Path(worktree_path), scenario)
    environment_path = Path(environment_path)
    base_python = Path(python_executable or sys.executable)
    venv_command = [str(base_python), "-m", "venv"]
    if not requirements_files:
        # Preserve access to the active environment for repositories that
        # do not declare their own isolated dependency set.
        venv_command.append("--system-site-packages")
    venv_command.append(str(environment_path))
    subprocess.run(
        venv_command,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    interpreter = (
        environment_path / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    )
    return interpreter, requirements_files





# ============================================================
# RUN ONE VERSION
# ============================================================

def run_version(
    worktree_path,
    scenario: str = DEFAULT_SCENARIO,
    timeout: int = 600,
    runtime_input: str = "",
    python_executable: Path | None = None,
) -> RuntimeArchitecture:
    """
    Execute one runtime scenario inside one Git worktree.

    A separate Python process is used so that imports from
    V1 cannot contaminate imports from V2.
    """

    worktree_path = Path(
        worktree_path
    ).resolve()

    validate_worktree(
        worktree_path,
        scenario,
    )

    with tempfile.TemporaryDirectory(
        prefix="architecture_runtime_"
    ) as temporary_directory:

        temporary_directory = Path(
            temporary_directory
        )

        tracer_file = (
            temporary_directory
            / "runtime_trace_runner.py"
        )

        output_file = (
            temporary_directory
            / "runtime_trace.json"
        )
        stdin_file = temporary_directory / "runtime_stdin.txt"
        stdin_file.write_text(runtime_input or "", encoding="utf-8")
        environment_path = temporary_directory / "python_environment"

        tracer_file.write_text(
            TRACER_SCRIPT,
            encoding="utf-8",
        )

        interpreter, requirements_files = _prepare_runtime_interpreter(
            worktree_path,
            scenario,
            environment_path,
            python_executable=python_executable,
        )
        try:
            install_timeout = max(
                60,
                int(os.environ.get("ARCHITECTURE_DEPENDENCY_INSTALL_TIMEOUT", "900")),
            )
        except ValueError:
            install_timeout = 900

        def execute_scenario():
            if output_file.exists():
                output_file.unlink()
            return subprocess.run(
                [
                    str(interpreter),
                    str(tracer_file),
                    str(worktree_path),
                    scenario,
                    str(output_file),
                    str(stdin_file),
                ],
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        try:
            process = execute_scenario()
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                "\nRuntime execution timed out.\n"
                f"Worktree: {worktree_path}\n"
                f"Scenario: {scenario}\n"
                f"Timeout: {timeout} seconds\n"
                "Interactive keyboard input is not collected during automatic V1/V2 comparison. "
                "Use a non-interactive application workflow.\n"
            ) from error

        if not output_file.exists():
            raise RuntimeError(
                "Runtime trace was not generated."
                "\n\n"
                f"STDOUT:\n{process.stdout}"
                "\n\n"
                f"STDERR:\n{process.stderr}"
            )

        trace_data = json.loads(output_file.read_text(encoding="utf-8"))
        execution_error = trace_data.get("error")

        # If an older repository imports a module removed from Python's
        # standard library, install its official-style PyPI redistribution
        # into this temporary environment and retry the exact same scenario.
        # This keeps the observed execution genuine; no metrics are fabricated.
        installed_compatibility = set()
        while execution_error:
            missing_module = _missing_module_name(execution_error)
            distribution = LEGACY_STDLIB_DISTRIBUTIONS.get(missing_module)
            if not distribution or distribution in installed_compatibility:
                break

            installed_compatibility.add(distribution)
            try:
                subprocess.run(
                    [
                        str(interpreter), "-m", "pip", "install",
                        "--disable-pip-version-check",
                        "--no-input",
                        "--prefer-binary",
                        "--retries", "2",
                        "--timeout", "30",
                        distribution,
                    ],
                    cwd=str(worktree_path),
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=install_timeout,
                )
                process = execute_scenario()
                if not output_file.exists():
                    raise RuntimeError(
                        "Runtime trace was not generated after installing "
                        f"the compatibility package {distribution}. "
                        f"STDERR: {process.stderr}"
                    )
                trace_data = json.loads(output_file.read_text(encoding="utf-8"))
                execution_error = trace_data.get("error")
            except subprocess.CalledProcessError as error:
                details = (error.stderr or error.stdout or str(error))[-4000:]
                raise RuntimeError(
                    f"Could not install Python compatibility package "
                    f"{distribution} for removed standard-library module "
                    f"{missing_module}:\\n{details}"
                ) from error
            except subprocess.TimeoutExpired as error:
                raise RuntimeError(
                    f"Installing Python compatibility package {distribution} "
                    f"timed out after {install_timeout} seconds."
                ) from error

        # Install the repository's declared dependencies only when the
        # selected scenario actually fails because an import is missing. This
        # avoids downloading heavyweight packages for standard-library-only
        # scenarios while preserving a requirements-based retry for real apps.
        missing_module = _missing_module_name(execution_error)
        if execution_error and missing_module and requirements_files:
            try:
                for requirements_file in requirements_files:
                    subprocess.run(
                        [
                            str(interpreter), "-m", "pip", "install",
                            "--disable-pip-version-check",
                            "--no-input",
                            "--prefer-binary",
                            "--retries", "2",
                            "--timeout", "30",
                            "-r", str(requirements_file),
                        ],
                        cwd=str(worktree_path),
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=install_timeout,
                    )
                process = execute_scenario()
                if not output_file.exists():
                    raise RuntimeError(
                        "Runtime trace was not generated after installing declared requirements. "
                        f"STDERR: {process.stderr}"
                    )
                trace_data = json.loads(output_file.read_text(encoding="utf-8"))
                execution_error = trace_data.get("error")
            except subprocess.CalledProcessError as error:
                details = (error.stderr or error.stdout or str(error))[-5000:]
                raise RuntimeError(
                    "The scenario needs a declared dependency, but requirements "
                    f"installation failed for {requirements_file}:\\n{details}"
                ) from error
            except subprocess.TimeoutExpired as error:
                raise RuntimeError(
                    f"Dependency installation timed out after {install_timeout} seconds "
                    f"for {requirements_file}. The selected scenario could not be retried."
                ) from error

        if execution_error:

            if "EOFError" in execution_error:
                raise RuntimeError(
                    "The selected Python workload requested interactive keyboard input. "
                    "Automatic V1/V2 comparison requires a non-interactive workload. "
                    f"Workload: {scenario}; version: {get_commit_hash(worktree_path)}."
                )

            raise RuntimeError(
                "Runtime scenario failed."
                "\n\n"
                f"Version: "
                f"{get_commit_hash(worktree_path)}"
                "\n"
                f"Scenario: {scenario}"
                "\n"
                f"Error: {execution_error}"
                "\n\n"
                f"STDOUT:\n"
                f"{process.stdout}"
                "\n\n"
                f"STDERR:\n"
                f"{process.stderr}"
                + (
                    "\nDependencies installed from: "
                    + ", ".join(str(item.relative_to(worktree_path)) for item in requirements_files)
                    if requirements_files
                    else (
                        "\nNo requirements.txt was found at the repository root "
                        "or scenario directory. The temporary environment can still "
                        "use packages from the active environment. If this is a "
                        "third-party dependency, add its distribution to requirements.txt. "
                        "If it is a project-local module, verify that its source file "
                        "exists in this commit and that its import path is correct."
                    )
                )
            )

        architecture = (
            build_runtime_architecture(
                trace_data
            )
        )

        return architecture


# ============================================================
# RUN TWO VERSIONS
# ============================================================

def list_repository_commits(repository_path):
    """Return selectable commits from the repository used by Architecture Evolution."""
    repository = Path(repository_path).resolve()
    if not repository.is_dir():
        raise FileNotFoundError(f"Selected repository directory does not exist: {repository}")
    result = subprocess.run(
        ["git", "-C", str(repository), "log",
         "--date=iso-strict", "--pretty=format:%H%x1f%h%x1f%an%x1f%ad%x1f%s"],
        capture_output=True, text=True, check=True, timeout=30,
    )
    commits = []
    for line in result.stdout.splitlines():
        parts = line.split("\x1f", 4)
        if len(parts) == 5:
            commits.append({
                "sha": parts[0], "short_sha": parts[1], "author": parts[2],
                "date": parts[3], "message": parts[4],
            })
    return commits


def list_common_python_entrypoints(repository_path, v1_commit: str, v2_commit: str):
    """List bounded Python entry points present in both selected Git commits."""
    repository = Path(repository_path).resolve()
    if not repository.is_dir() or not (repository / ".git").exists():
        raise ValueError(f"Selected repository is not a Git checkout: {repository}")

    with tempfile.TemporaryDirectory(prefix="architecture_scenario_discovery_") as temp:
        root = Path(temp)
        v1_path = root / "version_1"
        v2_path = root / "version_2"
        added = []
        try:
            for path, commit in ((v1_path, v1_commit), (v2_path, v2_commit)):
                subprocess.run(
                    ["git", "-C", str(repository), "worktree", "add", "--detach", str(path), commit],
                    capture_output=True, text=True, check=True, timeout=120,
                )
                added.append(path)

            common = set(discover_python_entrypoints(v1_path)) & set(discover_python_entrypoints(v2_path))
            preferred = ("runtime_scenario.py", "main.py", "cli.py", "run.py", "__main__.py", "sample_project.py")
            order = {name: index for index, name in enumerate(preferred)}
            return sorted(
                common,
                key=lambda value: (
                    order.get(Path(value).name, len(preferred)),
                    len(Path(value).parts),
                    value.lower(),
                ),
            )
        finally:
            for path in reversed(added):
                subprocess.run(
                    ["git", "-C", str(repository), "worktree", "remove", "--force", str(path)],
                    capture_output=True, text=True, timeout=60,
                )
            subprocess.run(
                ["git", "-C", str(repository), "worktree", "prune"],
                capture_output=True, text=True, timeout=30,
            )


def discover_runtime_entrypoints(worktree_path):
    """Discover bounded scenarios for runtime adapters available in this build."""
    candidates = discover_python_entrypoints(worktree_path)
    try:
        from architecture_model.php_runtime_adapter import discover_php_entrypoints
        candidates.extend(discover_php_entrypoints(worktree_path))
    except ImportError:
        pass
    try:
        from architecture_model.rust_runtime_adapter import discover_rust_entrypoints
        candidates.extend(discover_rust_entrypoints(worktree_path))
    except ImportError:
        pass
    try:
        from architecture_model.csharp_runtime_adapter import discover_csharp_entrypoints
        candidates.extend(discover_csharp_entrypoints(worktree_path))
    except ImportError:
        pass
    try:
        from architecture_model.native_runtime_adapter import discover_native_entrypoints
        candidates.extend(discover_native_entrypoints(worktree_path))
    except ImportError:
        pass
    try:
        from architecture_model.java_runtime_adapter import discover_java_entrypoints
        candidates.extend(discover_java_entrypoints(worktree_path))
    except ImportError:
        pass
    try:
        from architecture_model.go_runtime_adapter import discover_go_entrypoints
        candidates.extend(discover_go_entrypoints(worktree_path))
    except ImportError:
        pass
    try:
        from architecture_model.ruby_runtime_adapter import discover_ruby_entrypoints
        candidates.extend(discover_ruby_entrypoints(worktree_path))
    except ImportError:
        pass
    try:
        from architecture_model.node_runtime_adapter import discover_node_entrypoints
        candidates.extend(discover_node_entrypoints(worktree_path))
    except ImportError:
        pass
    return sorted(set(candidates), key=lambda value: (
        0 if value == "npm:test" else 1,
        0 if Path(value).suffix.lower() == ".py" else 1,
        value.lower(),
    ))


def list_common_runtime_entrypoints(repository_path, v1_commit: str, v2_commit: str):
    """List same-language runnable scenarios present in both selected commits."""
    repository = Path(repository_path).resolve()
    if not repository.is_dir() or not (repository / ".git").exists():
        raise ValueError(f"Selected repository is not a Git checkout: {repository}")

    with tempfile.TemporaryDirectory(prefix="architecture_scenario_discovery_") as temp:
        root = Path(temp)
        v1_path, v2_path = root / "version_1", root / "version_2"
        added = []
        try:
            for path, commit in ((v1_path, v1_commit), (v2_path, v2_commit)):
                subprocess.run(
                    ["git", "-C", str(repository), "worktree", "add", "--detach", str(path), commit],
                    capture_output=True, text=True, check=True, timeout=120,
                )
                added.append(path)
            common = set(discover_runtime_entrypoints(v1_path)) & set(discover_runtime_entrypoints(v2_path))
            return sorted(common, key=lambda value: (
                0 if value == "npm:test" else 1,
                0 if Path(value).name.lower() in {"runtime_scenario.py", "runtime_scenario.js"} else 1,
                0 if Path(value).suffix.lower() == ".py" else 1,
                len(Path(value).parts),
                value.lower(),
            ))
        finally:
            for path in reversed(added):
                subprocess.run(
                    ["git", "-C", str(repository), "worktree", "remove", "--force", str(path)],
                    capture_output=True, text=True, timeout=60,                )
            subprocess.run(
                ["git", "-C", str(repository), "worktree", "prune"],
                capture_output=True, text=True, timeout=30,
            )


def list_runtime_entrypoints_by_commit(repository_path, v1_commit: str, v2_commit: str):
    """Discover runnable scenarios independently in each selected commit.

    Scenario filenames may change between versions. Returning both inventories
    lets the user map the corresponding V1 and V2 workflows explicitly.
    """
    repository = Path(repository_path).resolve()
    if not repository.is_dir() or not (repository / ".git").exists():
        raise ValueError(f"Selected repository is not a Git checkout: {repository}")

    with tempfile.TemporaryDirectory(prefix="architecture_scenario_pair_discovery_") as temp:
        root = Path(temp)
        v1_path, v2_path = root / "version_1", root / "version_2"
        added = []
        try:
            for path, commit in ((v1_path, v1_commit), (v2_path, v2_commit)):
                subprocess.run(
                    ["git", "-C", str(repository), "worktree", "add", "--detach", str(path), commit],
                    capture_output=True, text=True, check=True, timeout=120,
                )
                added.append(path)
            return {
                "v1": discover_runtime_entrypoints(v1_path),
                "v2": discover_runtime_entrypoints(v2_path),
            }
        finally:
            for path in reversed(added):
                subprocess.run(
                    ["git", "-C", str(repository), "worktree", "remove", "--force", str(path)],
                    capture_output=True, text=True, timeout=60,
                )
            subprocess.run(
                ["git", "-C", str(repository), "worktree", "prune"],
                capture_output=True, text=True, timeout=30,
            )


def _common_runtime_entrypoint(v1_path: Path, v2_path: Path) -> str:
    """Choose one bounded runtime workload shared by both selected commits."""
    v1_candidates = set(discover_runtime_entrypoints(v1_path))
    v2_candidates = set(discover_runtime_entrypoints(v2_path))
    common = v1_candidates & v2_candidates
    if not common:
        return None
    preferred = (
        "flask:test-client", "python:smartmonitor-smoke", "npm:test",
        "runtime_scenario.py", "test_architecture_recovery.py",
        "main.py", "run.py", "cli.py", "__main__.py",
    )
    preferred_order = {name: index for index, name in enumerate(preferred)}
    return sorted(
        common,
        key=lambda value: (
            0 if value == "npm:test" else preferred_order.get(Path(value).name.lower(), len(preferred)),
            0 if Path(value).suffix.lower() == ".py" else 1,
            len(Path(value).parts),
            value.lower(),
        ),
    )[0]




def _create_automatic_architecture_workload(
    v1_path: Path,
    v2_path: Path,
    temporary_root: Path,
) -> str:
    """Build one temporary workload when both versions expose the real parser."""
    parser_paths = (v1_path / "src" / "parser.py", v2_path / "src" / "parser.py")
    if not all(path.is_file() for path in parser_paths):
        raise FileNotFoundError(
            "No shared non-interactive runtime workload was found in the selected commits. "
            "The automatic runner could not identify a supported non-interactive "
            "application workload that exists in both versions. Interactive command-line "
            "programs and long-running server/browser launchers are not started automatically. "
            "Use Quick Static Architecture Comparison for source-level V1/V2 results, or "
            "select commits with a bounded runtime scenario or a declared test suite."
        )

    import ast

    for parser_path in parser_paths:
        try:
            tree = ast.parse(parser_path.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, SyntaxError, ValueError) as error:
            raise RuntimeError(
                f"Could not validate the parser workload in {parser_path}: {error}"
            ) from error
        if not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "parse_folder"
            for node in tree.body
        ):
            raise FileNotFoundError(
                f"{parser_path} does not expose the parse_folder application function."
            )

    # Keep this driver outside both Git worktrees. It calls the actual code
    # present in each selected commit and is excluded from project metrics.
    workload = Path(temporary_root) / "architecture_runtime_workload.py"
    workload.write_text(
        "import runpy\n"
        "from pathlib import Path\n"
        "root = Path.cwd()\n"
        "from src.parser import parse_folder\n"
        "parsed_results = parse_folder(str(root))\n"
        "try:\n"
        "    from architecture_model.recovery import recover_architecture\n"
        "except ModuleNotFoundError as error:\n"
        "    if error.name not in {'architecture_model', 'architecture_model.recovery'}:\n"
        "        raise\n"
        "else:\n"
        "    recover_architecture(parsed_results)\n"
        "def run_if_available(relative, required):\n"
        "    target = root / relative\n"
        "    if target.is_file() and all((root / item).is_file() for item in required):\n"
        "        runpy.run_path(str(target), run_name='__runtime_workload_' + target.stem)\n"
        "run_if_available('test_architecture_diff.py', ('architecture_model/model.py', 'architecture_model/diff.py'))\n"
        "run_if_available('test_architecture_model.py', ('architecture_model/model.py',))\n"
        "run_if_available('architecture_model/test_architecture_timeline.py', ('architecture_model/model.py', 'architecture_model/timeline.py', 'architecture_model/diff.py'))\n"
        "run_if_available('architecture_model/test_snapshot_store.py', ('architecture_model/model.py', 'architecture_model/snapshot_store.py'))\n",
        encoding="utf-8",
    )
    return str(workload)

def _runtime_metrics(architecture):
    """Return comparable measured metrics for one executed Git version."""
    return {
        "modules": architecture.get_module_count(),
        "relationships": architecture.get_relationship_count(),
        "total_calls": architecture.total_calls,
    }


def _runtime_metric_deltas(v1_runtime, v2_runtime):
    """Return V2 minus V1 runtime metric changes."""
    v1 = _runtime_metrics(v1_runtime)
    v2 = _runtime_metrics(v2_runtime)
    return {
        key: v2[key] - v1[key]
        for key in v1
    }


def run_version_pair(
    repository_path,
    v1_commit: str,
    v2_commit: str,
    scenario: str | None = None,
    timeout: int = 300,
    runtime_input: str | None = None,
    v1_scenario: str | None = None,
    v2_scenario: str | None = None,
):
    """
    Execute corresponding scenarios in two user-selected Git versions.

    V1 and V2 may use different entry-point paths (for example, main.py in V1
    and cli.py in V2). For Python, identical stdin text is supplied to both.
    """
    repository = Path(repository_path).resolve()
    if not repository.is_dir():
        raise FileNotFoundError(f"Selected GitHub repository path does not exist: {repository}")
    if not (repository / ".git").exists():
        raise ValueError(f"Selected repository is not a Git checkout: {repository}")

    runtime_input = runtime_input or ""

    if not v1_commit or not v2_commit:
        raise ValueError("Select two commits before running Runtime Architecture comparison.")
    if v1_commit == v2_commit:
        raise ValueError("Choose two different commits to compare.")

    for commit in (v1_commit, v2_commit):
        subprocess.run(
            ["git", "-C", str(repository), "cat-file", "-e", f"{commit}^{{commit}}"],
            capture_output=True, text=True, check=True, timeout=30,
        )

    with tempfile.TemporaryDirectory(prefix="architecture_commit_compare_") as temp:
        temp_root = Path(temp)
        v1_path, v2_path = temp_root / "version_1", temp_root / "version_2"
        added = []
        try:
            for path, commit in ((v1_path, v1_commit), (v2_path, v2_commit)):
                subprocess.run(
                    ["git", "-C", str(repository), "worktree", "add", "--detach", str(path), commit],
                    capture_output=True, text=True, check=True, timeout=120,
                )
                added.append(path)

            # Backward compatibility: a single scenario still runs in both
            # versions. If omitted, discover a common Python entry point.
            if v1_scenario is None and v2_scenario is None:
                if scenario:
                    v1_scenario = v2_scenario = scenario
                else:
                    # The Architecture Modeling System has a stable parser API
                    # across its history. Use one generated workload to exercise
                    # parser/recovery plus available core diff, timeline, model,
                    # and snapshot-store workflows in each selected commit.
                    has_shared_parser = all(
                        (path / "src" / "parser.py").is_file()
                        for path in (v1_path, v2_path)
                    )
                    if has_shared_parser:
                        generated_workload = _create_automatic_architecture_workload(
                            v1_path, v2_path, temp_root
                        )
                        v1_scenario = v2_scenario = generated_workload
                    else:
                        common_workload = _common_runtime_entrypoint(v1_path, v2_path)
                        if common_workload == "flask:test-client":
                            generated_workload = _create_automatic_flask_test_client_workload(
                                v1_path, v2_path, temp_root
                            )
                            v1_scenario = v2_scenario = generated_workload
                        elif common_workload == "python:smartmonitor-smoke":
                            generated_workload = _create_automatic_smartmonitor_workload(
                                v1_path, v2_path, temp_root
                            )
                            v1_scenario = v2_scenario = generated_workload
                        elif common_workload:
                            v1_scenario = v2_scenario = common_workload
                        else:
                            generated_workload = _create_automatic_architecture_workload(
                                v1_path, v2_path, temp_root
                            )
                            v1_scenario = v2_scenario = generated_workload
            else:
                v1_scenario = v1_scenario or scenario
                v2_scenario = v2_scenario or scenario

            if not v1_scenario or not v2_scenario:
                raise ValueError("Select a runnable scenario for both V1 and V2.")
            validate_worktree(v1_path, v1_scenario)
            validate_worktree(v2_path, v2_scenario)

            for worktree, selected in ((v1_path, v1_scenario), (v2_path, v2_scenario)):
                if Path(selected).suffix.lower() in {".py", ".pyw"}:
                    blocker = _python_entrypoint_runtime_blocker(worktree, selected)
                    if blocker == "camera":
                        raise ValueError(
                            f"Runtime scenario '{selected}' in {worktree.name} requires physical "
                            "camera access and cannot run in the isolated comparison worker. "
                            "Choose a bounded scenario that does not initialize hardware."
                        )

            def adapter_family(selected):
                if selected == "npm:test":
                    return "node"
                suffix = Path(selected).suffix.lower()
                if suffix in {".py", ".pyw"}:
                    return "python"
                if suffix in {".js", ".mjs", ".cjs", ".ts", ".mts", ".cts"}:
                    return "node"
                if suffix == ".rb":
                    return "ruby"
                if suffix == ".go":
                    return "go"
                if suffix == ".java":
                    return "java"
                if suffix in {".c", ".cc", ".cpp", ".cxx", ".c++"}:
                    return "native"
                if suffix == ".csproj":
                    return "csharp"
                if Path(selected).name.lower() == "cargo.toml":
                    return "rust"
                if suffix == ".php":
                    return "php"
                return "unsupported"

            v1_family, v2_family = adapter_family(v1_scenario), adapter_family(v2_scenario)
            if v1_family == "unsupported" or v2_family == "unsupported":
                raise ValueError(
                    "The selected V1 or V2 scenario has no supported runtime adapter."
                )
            if v1_family != v2_family:
                raise ValueError(
                    f"V1 uses the {v1_family} runtime adapter but V2 uses {v2_family}. "
                    "Choose scenarios implemented in the same language/runtime family "
                    "so their execution evidence can be compared fairly."
                )

            # Use one compatible interpreter for Python versions; other
            # language adapters select their own installed toolchains.
            pair_python = (
                _select_python_for_pair(v1_path, v2_path, v1_scenario)
                if v1_family == "python" else Path(sys.executable)
            )

            def execute_selected(worktree, selected):
                if selected == "npm:test":
                    from architecture_model.node_runtime_adapter import run_node_version
                    return run_node_version(worktree, scenario=selected, timeout=timeout)
                suffix = Path(selected).suffix.lower()
                if suffix in {".js", ".mjs", ".cjs", ".ts", ".mts", ".cts"}:
                    from architecture_model.node_runtime_adapter import run_node_version
                    return run_node_version(worktree, scenario=selected, timeout=timeout)
                if suffix == ".rb":
                    from architecture_model.ruby_runtime_adapter import run_ruby_version
                    return run_ruby_version(worktree, scenario=selected, timeout=timeout)
                if suffix == ".go":
                    from architecture_model.go_runtime_adapter import run_go_version
                    return run_go_version(worktree, scenario=selected, timeout=timeout)
                if suffix == ".java":
                    from architecture_model.java_runtime_adapter import run_java_version
                    return run_java_version(worktree, scenario=selected, timeout=timeout)
                if suffix in {".c", ".cc", ".cpp", ".cxx", ".c++"}:
                    from architecture_model.native_runtime_adapter import run_native_version
                    return run_native_version(worktree, scenario=selected, timeout=timeout)
                if suffix == ".csproj":
                    from architecture_model.csharp_runtime_adapter import run_csharp_version
                    return run_csharp_version(worktree, scenario=selected, timeout=timeout)
                if Path(selected).name.lower() == "cargo.toml":
                    from architecture_model.rust_runtime_adapter import run_rust_version
                    return run_rust_version(worktree, scenario=selected, timeout=timeout)
                if suffix == ".php":
                    from architecture_model.php_runtime_adapter import run_php_version
                    return run_php_version(worktree, scenario=selected, timeout=timeout)
                if suffix in {".py", ".pyw"}:
                    return run_version(
                        worktree, scenario=selected, timeout=timeout,
                        runtime_input=runtime_input, python_executable=pair_python,
                    )
                raise ValueError(f"No runtime adapter is available for scenario: {selected}")

            v1_runtime = execute_selected(v1_path, v1_scenario)
            v2_runtime = execute_selected(v2_path, v2_scenario)

            # A trace with no modules is not a valid comparison result. In
            # particular, never display a misleading all-zero V2 snapshot.
            if v1_runtime.get_module_count() == 0:
                raise RuntimeError(
                    f"V1 scenario '{v1_scenario}' completed without recording any runtime modules. "
                    "Check its entry point, imports, and execution errors."
                )
            if v2_runtime.get_module_count() == 0:
                raise RuntimeError(
                    f"V2 scenario '{v2_scenario}' completed without recording any runtime modules. "
                    "The comparison was stopped instead of treating an empty trace as zero changes."
                )

            return {
                "v1_commit": get_commit_hash(v1_path),
                "v2_commit": get_commit_hash(v2_path),
                "scenario": v2_scenario,
                "v1_scenario": v1_scenario,
                "v2_scenario": v2_scenario,
                "v1_runtime": v1_runtime,
                "v2_runtime": v2_runtime,
                "v1_metrics": _runtime_metrics(v1_runtime),
                "v2_metrics": _runtime_metrics(v2_runtime),
                "runtime_metric_deltas": _runtime_metric_deltas(v1_runtime, v2_runtime),
            }
        finally:
            for path in reversed(added):
                subprocess.run(
                    ["git", "-C", str(repository), "worktree", "remove", "--force", str(path)],
                    capture_output=True, text=True, timeout=60,
                )
            subprocess.run(
                ["git", "-C", str(repository), "worktree", "prune"],
                capture_output=True, text=True, timeout=30,
            )


    print(
        "=" * 60
    )

    print(
        "RUNTIME VERSION EXECUTION"
    )

    print(
        "=" * 60
    )

    print()

    print(
        f"V1: {v1_commit}"
    )

    print(
        f"V2: {v2_commit}"
    )

    print(
        f"Scenario: {scenario}"
    )

    # --------------------------------------------------------
    # V1
    # --------------------------------------------------------

    print()
    print(
        "Executing V1..."
    )

    v1_runtime = run_version(
        worktree_path=v1_path,
        scenario=scenario,
        timeout=timeout,
    )

    print(
        "V1 completed:"
        f" {v1_runtime.get_module_count()}"
        " modules,"
        f" {v1_runtime.get_relationship_count()}"
        " relationships,"
        f" {v1_runtime.total_calls}"
        " calls"
    )

    # --------------------------------------------------------
    # V2
    # --------------------------------------------------------

    print()
    print(
        "Executing V2..."
    )

    v2_runtime = run_version(
        worktree_path=v2_path,
        scenario=scenario,
        timeout=timeout,
    )

    print(
        "V2 completed:"
        f" {v2_runtime.get_module_count()}"
        " modules,"
        f" {v2_runtime.get_relationship_count()}"
        " relationships,"
        f" {v2_runtime.total_calls}"
        " calls"
    )

    return {
        "v1_commit": v1_commit,
        "v2_commit": v2_commit,
        "scenario": scenario,
        "v1_runtime": v1_runtime,
        "v2_runtime": v2_runtime,
        "v1_metrics": _runtime_metrics(v1_runtime),
        "v2_metrics": _runtime_metrics(v2_runtime),
        "runtime_metric_deltas": _runtime_metric_deltas(
            v1_runtime,
            v2_runtime,
        ),
    }


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    from architecture_model.runtime_evolution import (
        compare_runtime_architectures,
        get_runtime_evolution_summary,
    )

    # --------------------------------------------------------
    # Execute both real Git versions
    # --------------------------------------------------------

    result = run_version_pair()

    # --------------------------------------------------------
    # Compare runtime architectures
    # --------------------------------------------------------

    comparison = (
        compare_runtime_architectures(
            result["v1_runtime"],
            result["v2_runtime"],
            old_version=result[
                "v1_commit"
            ],
            new_version=result[
                "v2_commit"
            ],
        )
    )

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    print()

    print(
        "=" * 60
    )

    print(
        "DYNAMIC ARCHITECTURE EVOLUTION"
    )

    print(
        "=" * 60
    )

    # --------------------------------------------------------
    # Runtime metrics
    # --------------------------------------------------------

    print()
    print(
        "V1 Runtime:"
    )

    print(
        comparison[
            "old_runtime"
        ]
    )

    print()
    print(
        "V2 Runtime:"
    )

    print(
        comparison[
            "new_runtime"
        ]
    )

    # --------------------------------------------------------
    # Module evolution
    # --------------------------------------------------------

    print()
    print(
        "Modules Added:"
    )

    modules_added = (
        comparison[
            "module_changes"
        ]["added"]
    )

    if modules_added:

        for module in modules_added:
            print(
                f"  + {module}"
            )

    else:

        print(
            "  None"
        )

    print()
    print(
        "Modules Removed:"
    )

    modules_removed = (
        comparison[
            "module_changes"
        ]["removed"]
    )

    if modules_removed:

        for module in modules_removed:
            print(
                f"  - {module}"
            )

    else:

        print(
            "  None"
        )

    # --------------------------------------------------------
    # Relationship evolution
    # --------------------------------------------------------

    print()
    print(
        "Runtime Relationships Added:"
    )

    added_relationships = (
        comparison[
            "relationship_changes"
        ]["added"]
    )

    if added_relationships:

        for relationship in (
            added_relationships
        ):

            print(
                f"  + "
                f"{relationship['source']}"
                f" -> "
                f"{relationship['target']}"
                f" | calls: "
                f"{relationship['call_count']}"
            )

    else:
        print(
            "  None"
        )

    print()
    print(
        "Runtime Relationships Removed:"
    )

    removed_relationships = (
        comparison[
            "relationship_changes"
        ]["removed"]
    )

    if removed_relationships:

        for relationship in (
            removed_relationships
        ):

            print(
                f"  - "
                f"{relationship['source']}"
                f" -> "
                f"{relationship['target']}"
                f" | calls: "
                f"{relationship['call_count']}"
            )

    else:

        print(
            "  None"
        )

    # --------------------------------------------------------
    # Call-count evolution
    # --------------------------------------------------------

    print()
    print(
        "Call Count Changes:"
    )

    call_changes = (
        comparison[
            "relationship_changes"
        ]["call_count_changes"]
    )

    if call_changes:

        for change in call_changes:

            print(
                f"  * "
                f"{change['source']}"
                f" -> "
                f"{change['target']}"
                f" | "
                f"{change['old_call_count']}"
                f" -> "
                f"{change['new_call_count']}"
                f" | difference: "
                f"{change['difference']:+d}"
            )

    else:

        print(
            "  None"
        )

    # --------------------------------------------------------
    # Function evolution
    # --------------------------------------------------------

    print()
    print(
        "Function Changes:"
    )

    function_changes = (
        comparison[
            "relationship_changes"
        ]["function_changes"]
    )

    if function_changes:

        for change in function_changes:

            print(
                f"  * "
                f"{change['source']}"
                f" -> "
                f"{change['target']}"
            )

            if change[
                "added_functions"
            ]:

                print(
                    "      Added functions: "
                    + ", ".join(
                        change[
                            "added_functions"
                        ]
                    )
                )

            if change[
                "removed_functions"
            ]:

                print(
                    "      Removed functions: "
                    + ", ".join(
                        change[
                            "removed_functions"
                        ]
                    )
                )

    else:

        print(
            "  None"
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print(
        "Behavioral Change Summary:"
    )

    print(
        comparison[
            "summary"
        ]
    )

    print()
    print(
        "Human-readable Summary:"
    )

    print(
        get_runtime_evolution_summary(
            comparison
        )
    )

    print()

    print(
        "=" * 60
    )

    print(
        "RUNTIME EVOLUTION ANALYSIS COMPLETED"
    )

    print(
        "=" * 60
    )