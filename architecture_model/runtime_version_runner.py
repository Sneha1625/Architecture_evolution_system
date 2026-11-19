"""
Runtime Version Runner

Executes the same Python scenario against two Git worktrees and
captures runtime module-to-module interactions.

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
        "sample_project.py": 6,
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
        if path.name.startswith("test_") or path.name.endswith("_test.py"):
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

        lowered = source.lower()
        # Never start a long-running development server as an automated
        # comparison scenario. Framework modules remain part of static analysis.
        if any(marker in lowered for marker in server_markers):
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
        source_path.relative_to(worktree)
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
# sys.setprofile emits function-call events, not module-execution events, so
# explicitly include the selected project entry point in the observed modules.
try:
    relative_entrypoint = scenario_path.resolve().relative_to(worktree)
    entrypoint_module = ".".join(relative_entrypoint.with_suffix("").parts) or "__main__"
except (ValueError, OSError, RuntimeError):
    entrypoint_module = "__main__"
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
    subprocess.run(
        [str(base_python), "-m", "venv", str(environment_path)],
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
                "If this scenario expects keyboard input, create "
                "'architecture_runtime_input.txt' in the selected repository root "
                "with one response per line. The same contents are supplied to V1 and V2. "
                "Interactive input is closed after the supplied text to prevent indefinite waits.\n"
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

            if "EOFError" in execution_error and not runtime_input.strip():
                raise RuntimeError(
                    "This Python scenario requests keyboard input, but no input was supplied. "
                    "To keep the Runtime Input field hidden, create a UTF-8 text file named "
                    "'architecture_runtime_input.txt' in the selected repository's root folder. "
                    "Put one response per line in the order requested by the program. "
                    "The same file content is supplied to V1 and V2. "
                    "For example, a program asking for two numbers could use two lines in that file. "
                    "No input values are guessed automatically. "
                    f"Scenario: {scenario}; version: {get_commit_hash(worktree_path)}."
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


def _common_python_entrypoint(v1_path: Path, v2_path: Path) -> str:
    """Choose a Python entry point present in both selected commit snapshots."""
    v1_candidates = set(discover_python_entrypoints(v1_path))
    v2_candidates = set(discover_python_entrypoints(v2_path))
    common = v1_candidates & v2_candidates
    if not common:
        raise FileNotFoundError(
            "The selected commits have no common non-interactive Python entry point. "
            "Streamlit/Flask/FastAPI/Gradio launchers are excluded because they keep "
            "running and cannot be traced as bounded scenarios. Add a short Python "
            "scenario or CLI script that exercises the application logic, then retry. "
            "Static architecture comparison remains available for these commits."
        )
    preferred = ("runtime_scenario.py", "sample_project.py", "main.py", "run.py", "cli.py", "__main__.py")
    preferred_order = {name: index for index, name in enumerate(preferred)}
    return sorted(common, key=lambda value: (preferred_order.get(Path(value).name, len(preferred)), len(Path(value).parts), value.lower()))[0]


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
    scenario: str = DEFAULT_SCENARIO,
    timeout: int = 300,
    runtime_input: str | None = None,
):
    """
    Execute the same Python entry point at two user-selected commits.
    Each commit is checked out into an isolated temporary Git worktree.
    """
    repository = Path(repository_path).resolve()
    if not repository.is_dir():
        raise FileNotFoundError(f"Selected GitHub repository path does not exist: {repository}")
    if not (repository / ".git").exists():
        raise ValueError(f"Selected repository is not a Git checkout: {repository}")

    # Interactive Python scenarios can receive deterministic input without
    # exposing a Streamlit text field. Read it once from the selected checkout
    # and pass the identical payload to both commit worktrees.
    if runtime_input is None:
        input_file = repository / "architecture_runtime_input.txt"
        try:
            runtime_input = input_file.read_text(encoding="utf-8") if input_file.is_file() else ""
        except OSError as error:
            raise RuntimeError(
                f"Could not read runtime input file {input_file}: {error}"
            ) from error
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
        v1_path = temp_root / "version_1"
        v2_path = temp_root / "version_2"
        added = []
        try:
            for path, commit in ((v1_path, v1_commit), (v2_path, v2_commit)):
                subprocess.run(
                    ["git", "-C", str(repository), "worktree", "add", "--detach", str(path), commit],
                    capture_output=True, text=True, check=True, timeout=120,
                )
                added.append(path)

            if not scenario:
                scenario = _common_python_entrypoint(v1_path, v2_path)
            validate_worktree(v1_path, scenario)
            validate_worktree(v2_path, scenario)

            # Resolve once from the combined V1/V2 requirements so both
            # snapshots run under the same Python version.
            pair_python = _select_python_for_pair(v1_path, v2_path, scenario)

            if Path(scenario).suffix.lower() in {".js", ".mjs", ".cjs", ".ts", ".mts", ".cts"}:
                from architecture_model.node_runtime_adapter import run_node_version
                v1_runtime = run_node_version(v1_path, scenario=scenario, timeout=timeout)
                v2_runtime = run_node_version(v2_path, scenario=scenario, timeout=timeout)
            elif Path(scenario).suffix.lower() == ".rb":
                from architecture_model.ruby_runtime_adapter import run_ruby_version
                v1_runtime = run_ruby_version(v1_path, scenario=scenario, timeout=timeout)
                v2_runtime = run_ruby_version(v2_path, scenario=scenario, timeout=timeout)
            elif Path(scenario).suffix.lower() == ".go":
                from architecture_model.go_runtime_adapter import run_go_version
                v1_runtime = run_go_version(v1_path, scenario=scenario, timeout=timeout)
                v2_runtime = run_go_version(v2_path, scenario=scenario, timeout=timeout)
            elif Path(scenario).suffix.lower() == ".java":
                from architecture_model.java_runtime_adapter import run_java_version
                v1_runtime = run_java_version(v1_path, scenario=scenario, timeout=timeout)
                v2_runtime = run_java_version(v2_path, scenario=scenario, timeout=timeout)
            elif Path(scenario).suffix.lower() in {".c", ".cc", ".cpp", ".cxx", ".c++"}:
                from architecture_model.native_runtime_adapter import run_native_version
                v1_runtime = run_native_version(v1_path, scenario=scenario, timeout=timeout)
                v2_runtime = run_native_version(v2_path, scenario=scenario, timeout=timeout)
            elif Path(scenario).suffix.lower() == ".csproj":
                from architecture_model.csharp_runtime_adapter import run_csharp_version
                v1_runtime = run_csharp_version(v1_path, scenario=scenario, timeout=timeout)
                v2_runtime = run_csharp_version(v2_path, scenario=scenario, timeout=timeout)
            elif Path(scenario).name.lower() == "cargo.toml":
                from architecture_model.rust_runtime_adapter import run_rust_version
                v1_runtime = run_rust_version(v1_path, scenario=scenario, timeout=timeout)
                v2_runtime = run_rust_version(v2_path, scenario=scenario, timeout=timeout)
            elif Path(scenario).suffix.lower() == ".php":
                from architecture_model.php_runtime_adapter import run_php_version
                v1_runtime = run_php_version(v1_path, scenario=scenario, timeout=timeout)
                v2_runtime = run_php_version(v2_path, scenario=scenario, timeout=timeout)
            else:
                v1_runtime = run_version(
                    v1_path, scenario=scenario, timeout=timeout,
                    runtime_input=runtime_input, python_executable=pair_python,
                )
                v2_runtime = run_version(
                    v2_path, scenario=scenario, timeout=timeout,
                    runtime_input=runtime_input, python_executable=pair_python,
                )
            return {
                "v1_commit": get_commit_hash(v1_path),
                "v2_commit": get_commit_hash(v2_path),
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