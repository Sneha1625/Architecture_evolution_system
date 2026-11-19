"""Java runtime adapter using Java Flight Recorder execution samples.

JFR stack samples identify project source files appearing on sampled stacks.
Adjacent project frames are retained as sampled caller/callee evidence; they are
not exact invocation counts. This adapter compiles dependency-free Java source
files with the installed JDK and runs one explicitly selected main class.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from architecture_model.runtime_model import RuntimeArchitecture, RuntimeCall


IGNORED_DIRS = {
    ".git", ".gradle", ".idea", ".mvn", ".venv", "build", "dist",
    "target", "vendor", "node_modules", "test", "tests",
}
SERVER_MARKERS = (
    "springapplication.run(", "httpserver.create(", "server.start(",
    "tomcat.start(", "jetty.server.start(",
)


def _java_main_class(source: str):
    package_match = re.search(r"(?m)^\s*package\s+([\w.]+)\s*;", source)
    class_match = re.search(r"\b(?:public\s+)?(?:final\s+)?class\s+(\w+)", source)
    has_main = re.search(
        r"\bstatic\s+void\s+main\s*\(\s*String\s*(?:\[\s*\]|\.\.\.)",
        source,
    )
    if not class_match or not has_main:
        return None
    class_name = class_match.group(1)
    package = package_match.group(1) if package_match else ""
    return f"{package}.{class_name}" if package else class_name


def discover_java_entrypoints(worktree_path):
    """Find Java files with a conventional static main method."""
    root = Path(worktree_path).resolve()
    candidates = []
    for path in root.rglob("*.java"):
        relative = path.relative_to(root)
        if any(part.lower() in IGNORED_DIRS for part in relative.parts[:-1]):
            continue
        if path.name.endswith(("Test.java", "Tests.java", "IT.java")):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(marker in source.lower() for marker in SERVER_MARKERS):
            continue
        if _java_main_class(source):
            candidates.append(relative.as_posix())
    return sorted(
        candidates,
        key=lambda value: (
            0 if Path(value).name.lower() == "runtime_scenario.java" else
            1 if Path(value).name.lower() == "main.java" else 2,
            len(Path(value).parts),
            value.lower(),
        ),
    )


def _source_for_class(class_name: str, root: Path):
    # JFR class names use slash-separated package names and may include
    # nested-class suffixes such as Outer$Inner.
    top_level = class_name.split("$", 1)[0]
    expected = Path(*top_level.split("/")).with_suffix(".java")
    matches = [
        path for path in root.rglob(expected.name)
        if tuple(path.parts[-len(expected.parts):]) == tuple(expected.parts)
        and not any(part.lower() in IGNORED_DIRS for part in path.relative_to(root).parts)
    ]
    return matches[0].resolve() if len(matches) == 1 else None


def run_java_version(worktree_path, scenario, timeout=300):
    """Compile and execute one Java main class, collecting JFR stack samples."""
    root = Path(worktree_path).resolve()
    scenario_path = (root / scenario).resolve()
    try:
        scenario_path.relative_to(root)
    except ValueError as error:
        raise ValueError("Runtime scenario must be inside the selected repository.") from error
    if not scenario_path.is_file() or scenario_path.suffix.lower() != ".java":
        raise FileNotFoundError(f"Java runtime scenario not found: {scenario_path}")

    javac = shutil.which("javac")
    java = shutil.which("java")
    jfr = shutil.which("jfr")
    if not javac or not java or not jfr:
        raise RuntimeError("A full JDK (javac, java, and jfr) is required for Java runtime tracing.")

    scenario_source = scenario_path.read_text(encoding="utf-8", errors="ignore")
    main_class = _java_main_class(scenario_source)
    if not main_class:
        raise ValueError("The selected Java scenario must declare a class with static void main(String[] args).")

    source_files = []
    for path in root.rglob("*.java"):
        relative = path.relative_to(root)
        if any(part.lower() in IGNORED_DIRS for part in relative.parts[:-1]):
            continue
        if path.name.endswith(("Test.java", "Tests.java", "IT.java")):
            continue
        source_files.append(path.resolve())
    if scenario_path not in source_files:
        source_files.append(scenario_path)

    architecture = RuntimeArchitecture(entry_point=scenario)
    architecture.modules.add(scenario_path.relative_to(root).as_posix())

    with tempfile.TemporaryDirectory(prefix="architecture_java_runtime_") as temporary:
        temp = Path(temporary)
        classes = temp / "classes"
        classes.mkdir()
        argfile = temp / "sources.args"
        def quote_arg(value):
            return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'
        argfile.write_text("\n".join(quote_arg(path) for path in source_files), encoding="utf-8")

        compile_result = subprocess.run(
            [javac, "-proc:none", "-d", str(classes), "@" + str(argfile)],
            cwd=str(root), capture_output=True, text=True, timeout=timeout,
        )
        if compile_result.returncode != 0:
            details = (compile_result.stderr or compile_result.stdout or "javac failed")[-5000:]
            raise RuntimeError(
                "Java runtime adapter could not compile the selected repository. "
                "This adapter currently requires dependency-free Java sources; "
                "Maven/Gradle dependency resolution is not executed automatically.\n"
                + details
            )

        recording = temp / "runtime.jfr"
        command = [
            java,
            f"-XX:StartFlightRecording=filename={recording},settings=profile,dumponexit=true",
            "-cp", str(classes), main_class,
        ]
        try:
            process = subprocess.run(
                command, cwd=str(root), capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"Java runtime scenario timed out after {timeout} seconds: {scenario}") from error
        if process.returncode != 0:
            details = (process.stderr or process.stdout or "Java exited unsuccessfully")[-5000:]
            raise RuntimeError(f"Java runtime scenario failed ({process.returncode}):\n{details}")
        if not recording.is_file():
            raise RuntimeError("Java Flight Recorder did not produce a recording.")

        printed = subprocess.run(
            [jfr, "print", "--json", "--events", "jdk.ExecutionSample", str(recording)],
            cwd=str(root), capture_output=True, text=True, timeout=timeout,
        )
        if printed.returncode != 0:
            details = (printed.stderr or printed.stdout or "jfr print failed")[-5000:]
            raise RuntimeError(f"Could not read Java Flight Recorder samples:\n{details}")
        try:
            recording_data = json.loads(printed.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError("Java Flight Recorder returned invalid JSON.") from error

        events = recording_data.get("recording", {}).get("events", [])
        for event in events:
            frames = event.get("values", {}).get("stackTrace", {}).get("frames", [])
            project_frames = []
            for frame in frames:
                method = frame.get("method", {})
                type_info = method.get("type", {})
                class_name = type_info.get("name", "")
                source_file = _source_for_class(class_name, root) if class_name else None
                if source_file:
                    module = source_file.relative_to(root).as_posix()
                    architecture.modules.add(module)
                    project_frames.append((module, method.get("name") or "(unknown)"))
            # JFR frames are ordered from the sampled leaf outward. Consecutive
            # project frames form sampled call-stack evidence, not exact counts.
            for index in range(len(project_frames) - 1):
                callee_module, callee_function = project_frames[index]
                caller_module, caller_function = project_frames[index + 1]
                architecture.add_call(RuntimeCall(
                    caller_module=caller_module,
                    caller_function=caller_function,
                    callee_module=callee_module,
                    callee_function=callee_function,
                    caller_file=caller_module,
                    callee_file=callee_module,
                ))

    return architecture
