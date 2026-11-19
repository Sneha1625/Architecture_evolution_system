"""C and C++ runtime adapter using GCC/G++ source-based coverage.

Coverage records which project source files executed. It does not provide
runtime call edges, so this adapter intentionally returns no call relationships.
The adapter compiles dependency-free source files with GCC/G++ and runs one
explicitly selected main() scenario.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from architecture_model.runtime_model import RuntimeArchitecture


C_EXTENSIONS = {".c"}
CPP_EXTENSIONS = {".cc", ".cpp", ".cxx", ".c++"}
SOURCE_EXTENSIONS = C_EXTENSIONS | CPP_EXTENSIONS
IGNORED_DIRS = {
    ".git", ".svn", "build", "dist", "target", "vendor", "third_party",
    "node_modules", "coverage", "cmake-build-debug", "cmake-build-release",
    ".venv", "venv", "test", "tests",
}
SERVER_MARKERS = (
    "listen(", "accept(", "httpserver", "websocketserver",
    "server.run(", "serve_forever(",
)


def _has_main(source):
    return bool(re.search(r"(?m)^\s*(?:int|auto)\s+main\s*\(", source))


def discover_native_entrypoints(worktree_path):
    """Find C/C++ source files declaring main(), excluding tests and servers."""
    root = Path(worktree_path).resolve()
    candidates = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        relative = path.relative_to(root)
        if any(part.lower() in IGNORED_DIRS for part in relative.parts[:-1]):
            continue
        if path.stem.lower().endswith(("test", "tests", "benchmark", "bench")):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not _has_main(source) or any(marker in source.lower() for marker in SERVER_MARKERS):
            continue
        candidates.append(relative.as_posix())
    return sorted(
        candidates,
        key=lambda value: (
            0 if Path(value).stem.lower() == "runtime_scenario" else
            1 if Path(value).stem.lower() == "main" else 2,
            len(Path(value).parts),
            value.lower(),
        ),
    )


def run_native_version(worktree_path, scenario, timeout=300):
    """Compile and run one C/C++ scenario, then map gcov evidence to project files."""
    root = Path(worktree_path).resolve()
    scenario_path = (root / scenario).resolve()
    try:
        scenario_path.relative_to(root)
    except ValueError as error:
        raise ValueError("Runtime scenario must be inside the selected repository.") from error
    if not scenario_path.is_file() or scenario_path.suffix.lower() not in SOURCE_EXTENSIONS:
        raise FileNotFoundError(f"C/C++ runtime scenario not found: {scenario_path}")

    source_text = scenario_path.read_text(encoding="utf-8", errors="ignore")
    if not _has_main(source_text):
        raise ValueError("The selected C/C++ scenario must define main().")

    gcc = shutil.which("gcc")
    gpp = shutil.which("g++")
    gcov = shutil.which("gcov")
    if not gcc or not gpp or not gcov:
        raise RuntimeError("GCC, G++, and gcov are required for C/C++ runtime tracing.")

    all_sources = []
    main_sources = set()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        relative = path.relative_to(root)
        if any(part.lower() in IGNORED_DIRS for part in relative.parts[:-1]):
            continue
        if path.stem.lower().endswith(("test", "tests", "benchmark", "bench")):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        all_sources.append(path.resolve())
        if _has_main(text):
            main_sources.add(path.resolve())

    # Repositories can contain several independent command-line programs.
    # Compile the selected main plus shared source files, not other mains.
    sources = [path for path in all_sources if path == scenario_path or path not in main_sources]
    if scenario_path not in sources:
        sources.append(scenario_path)

    is_cpp = any(path.suffix.lower() in CPP_EXTENSIONS for path in sources)
    linker = gpp if is_cpp else gcc
    architecture = RuntimeArchitecture(entry_point=scenario)
    architecture.modules.add(scenario_path.relative_to(root).as_posix())

    with tempfile.TemporaryDirectory(prefix="architecture_native_runtime_") as temporary:
        temp = Path(temporary)
        objects = temp / "objects"
        objects.mkdir()
        object_files = []
        source_objects = []
        for index, source in enumerate(sorted(sources)):
            compiler = gpp if source.suffix.lower() in CPP_EXTENSIONS else gcc
            obj = objects / f"source_{index}.o"
            compile_result = subprocess.run(
                [compiler, "--coverage", "-O0", "-g", "-fprofile-abs-path",
                 "-c", str(source), "-o", str(obj)],
                cwd=str(root), capture_output=True, text=True, timeout=timeout,
            )
            if compile_result.returncode != 0:
                details = (compile_result.stderr or compile_result.stdout or "compiler failed")[-5000:]
                raise RuntimeError(
                    "C/C++ runtime adapter could not compile the selected repository. "
                    "This adapter currently requires source files whose external "
                    "dependencies are already available to GCC/G++.\n" + details
                )
            object_files.append(obj)
            source_objects.append((source, obj))

        executable = temp / ("runtime.exe" if os.name == "nt" else "runtime")
        link_result = subprocess.run(
            [linker, "--coverage", *map(str, object_files), "-o", str(executable)],
            cwd=str(root), capture_output=True, text=True, timeout=timeout,
        )
        if link_result.returncode != 0:
            details = (link_result.stderr or link_result.stdout or "linker failed")[-5000:]
            raise RuntimeError(f"C/C++ runtime scenario could not be linked:\n{details}")

        try:
            process = subprocess.run(
                [str(executable)], cwd=str(root), capture_output=True,
                text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"C/C++ runtime scenario timed out after {timeout} seconds: {scenario}") from error
        if process.returncode != 0:
            details = (process.stderr or process.stdout or "program exited unsuccessfully")[-5000:]
            raise RuntimeError(f"C/C++ runtime scenario failed ({process.returncode}):\n{details}")

        for index, (source, obj) in enumerate(source_objects):
            gcov_work = temp / f"gcov_{index}"
            gcov_work.mkdir()
            gcov_result = subprocess.run(
                [gcov, "--json-format", "-o", str(obj.with_suffix(".gcno")), str(source)],
                cwd=str(gcov_work), capture_output=True, text=True, timeout=timeout,
            )
            if gcov_result.returncode != 0:
                # A source may be compiled but not instrumented with executable
                # lines. Do not convert missing gcov output into execution evidence.
                continue
            for evidence_file in gcov_work.glob("*.gcov.json.gz"):
                try:
                    with gzip.open(evidence_file, "rt", encoding="utf-8") as stream:
                        evidence = json.load(stream)
                except (OSError, json.JSONDecodeError):
                    continue
                for file_record in evidence.get("files", []):
                    file_name = Path(file_record.get("file", ""))
                    if not file_name.is_absolute():
                        file_name = (root / file_name).resolve()
                    else:
                        file_name = file_name.resolve()
                    try:
                        relative = file_name.relative_to(root).as_posix()
                    except (ValueError, OSError, RuntimeError):
                        continue
                    if any(part.lower() in IGNORED_DIRS for part in Path(relative).parts):
                        continue
                    if any(int(line.get("count", 0)) > 0 for line in file_record.get("lines", [])):
                        architecture.modules.add(relative)

    return architecture
