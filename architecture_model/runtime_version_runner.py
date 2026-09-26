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
import subprocess
import sys
import tempfile
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

DEFAULT_SCENARIO = "test_architecture_recovery.py"


# ============================================================
# CHILD-PROCESS TRACER
# ============================================================

TRACER_SCRIPT = r'''
import json
import os
import runpy
import sys
from pathlib import Path
from functools import lru_cache

worktree = Path(sys.argv[1]).resolve()
scenario = sys.argv[2]
output_file = Path(sys.argv[3]).resolve()

sys.path.insert(0, str(worktree))

calls = []
total_python_calls = 0

TRACE_PREFIXES = (
    "src.",
    "architecture_model.",
    "features.",
    "database.",
)

@lru_cache(maxsize=8192)
def is_project_file(filename):
    """Cache file membership checks to avoid repeated path resolution."""
    if not filename:
        return False

    try:
        Path(filename).resolve().relative_to(worktree)
        return True
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

def is_architecture_module(module):
    return bool(module) and module.startswith(TRACE_PREFIXES)

def profiler(frame, event, arg):
    global total_python_calls

    if event != "call":
        return profiler

    caller = frame.f_back
    if caller is None:
        return profiler

    caller_module = module_name(caller)
    callee_module = module_name(frame)

    # Filter module names before doing filesystem checks.
    if not is_architecture_module(caller_module):
        return profiler

    if not is_architecture_module(callee_module):
        return profiler

    if caller_module == callee_module:
        return profiler

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


# ============================================================
# RECONSTRUCT RUNTIME ARCHITECTURE
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


# ============================================================
# RUN ONE VERSION
# ============================================================

def run_version(
    worktree_path,
    scenario: str = DEFAULT_SCENARIO,
    timeout: int = 600,
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

        tracer_file.write_text(
            TRACER_SCRIPT,
            encoding="utf-8",
        )

        try:

            process = subprocess.run(
                [
                    sys.executable,
                    str(tracer_file),
                    str(worktree_path),
                    scenario,
                    str(output_file),
                ],
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        except subprocess.TimeoutExpired as error:

            raise RuntimeError(
                "\nRuntime execution timed out.\n"
                f"Worktree: {worktree_path}\n"
                f"Scenario: {scenario}\n"
                f"Timeout: {timeout} seconds\n"
            ) from error

        if not output_file.exists():

            raise RuntimeError(
                "Runtime trace was not generated."
                "\n\n"
                f"STDOUT:\n"
                f"{process.stdout}"
                "\n\n"
                f"STDERR:\n"
                f"{process.stderr}"
            )

        trace_data = json.loads(
            output_file.read_text(
                encoding="utf-8"
            )
        )

        execution_error = (
            trace_data.get(
                "error"
            )
        )

        if execution_error:

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

def run_version_pair(
    v1_path=DEFAULT_V1_PATH,
    v2_path=DEFAULT_V2_PATH,
    scenario: str = DEFAULT_SCENARIO,
    timeout: int = 300,
):
    """
    Execute exactly the same scenario against V1 and V2.

    Returns a dictionary containing both RuntimeArchitecture
    objects and their Git commit hashes.
    """

    v1_path = Path(
        v1_path
    ).resolve()

    v2_path = Path(
        v2_path
    ).resolve()

    v1_commit = get_commit_hash(
        v1_path
    )

    v2_commit = get_commit_hash(
        v2_path
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