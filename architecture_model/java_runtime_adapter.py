"""Spring Boot Java runtime tracing using JDK Flight Recorder samples.

This adapter builds and starts each selected Git worktree independently, records
JFR execution samples during application startup, and derives sampled adjacent
stack-frame edges. These are statistical observations, never exact call counts.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from architecture_model.runtime_model import RuntimeArchitecture, RuntimeCall

BUILD_TIMEOUT = 240
STARTUP_TIMEOUT = 90
SAMPLE_WINDOW_SECONDS = 12


def discover_spring_boot_entrypoint(root: str | Path) -> str | None:
    """Find a source file annotated as the Spring Boot application class."""
    root = Path(root).resolve()
    candidates = []
    for source in root.rglob("*.java"):
        rel = source.relative_to(root)
        if any(part.lower() in {"target", "build", ".git", ".gradle", "test"} for part in rel.parts[:-1]):
            continue
        try:
            text = source.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if re.search(r"@SpringBootApplication\b", text) and re.search(r"\bstatic\s+void\s+main\s*\(", text):
            candidates.append(rel.as_posix())
    candidates.sort(key=lambda value: (len(Path(value).parts), value.lower()))
    return candidates[0] if candidates else None


def _tool(root: Path, names: tuple[str, ...]) -> str | None:
    for name in names:
        local = root / name
        if local.is_file():
            return str(local)
        found = shutil.which(name)
        if found:
            return found
    return None


def _run_build(root: Path, timeout: int) -> Path:
    mvnw = _tool(root, ("mvnw.cmd", "mvnw")) if (root / "pom.xml").exists() else None
    mvn = mvnw or shutil.which("mvn")
    gradlew = _tool(root, ("gradlew.bat", "gradlew")) if (root / "settings.gradle").exists() or (root / "build.gradle").exists() or (root / "settings.gradle.kts").exists() or (root / "build.gradle.kts").exists() else None
    gradle = gradlew or shutil.which("gradle")

    if (root / "pom.xml").exists() and mvn:
        command = [mvn, "-q", "-DskipTests", "package"]
    elif any((root / name).exists() for name in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")) and gradle:
        command = [gradle, "--no-daemon", "-q", "bootJar"]
    elif (root / "pom.xml").exists():
        raise RuntimeError("Maven project detected, but Maven is unavailable. Install Maven or include the Maven Wrapper (mvnw/mvnw.cmd).")
    elif any((root / name).exists() for name in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")):
        raise RuntimeError("Gradle project detected, but Gradle is unavailable. Install Gradle or include the Gradle Wrapper.")
    else:
        raise RuntimeError("No Maven pom.xml or Gradle build file was found; this Java runtime adapter currently targets buildable Spring Boot projects.")

    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Java project build exceeded {timeout} seconds.") from exc
    if result.returncode:
        tail = (result.stdout + "\n" + result.stderr)[-9000:]
        raise RuntimeError("Spring Boot build failed. Check the selected commit's dependencies and build configuration.\n" + tail)

    jars = list((root / "target").glob("*.jar")) if (root / "target").exists() else []
    jars += list((root / "build" / "libs").glob("*.jar")) if (root / "build" / "libs").exists() else []
    jars = [p for p in jars if p.is_file() and not p.name.endswith(("-plain.jar", "-sources.jar", "-javadoc.jar"))]
    if not jars:
        raise RuntimeError("Build completed but no executable Spring Boot JAR was found in target/ or build/libs/.")
    jars.sort(key=lambda p: (0 if "boot" in p.name.lower() else 1, -p.stat().st_mtime))
    return jars[0]


def _parse_jfr_json(payload: dict, root: Path) -> list[dict]:
    """Convert JFR execution-sample stacks into sampled project call edges."""
    events = payload.get("recording", {}).get("events", [])
    if not events and isinstance(payload.get("recording"), list):
        events = payload["recording"]
    project_packages = set()
    for java_source in root.rglob("*.java"):
        if any(part.lower() in {"target", "build", ".git", ".gradle"} for part in java_source.relative_to(root).parts[:-1]):
            continue
        try:
            source_text = java_source.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        package_match = re.search(r"^\\s*package\\s+([\\w.]+)\\s*;", source_text, re.MULTILINE)
        if package_match:
            project_packages.add(package_match.group(1))

    edges: dict[tuple[str, str, str, str], int] = {}
    for event in events:
        values = event.get("values", event)
        stack = values.get("stackTrace") or values.get("stacktrace") or {}
        frames = stack.get("frames", []) if isinstance(stack, dict) else []
        project_frames = []
        for frame in frames:
            method = frame.get("method", {})
            if not isinstance(method, dict):
                continue
            typ = method.get("type", {})
            class_name = typ.get("name", "") if isinstance(typ, dict) else str(typ or "")
            method_name = method.get("name", "")
            if not class_name or not method_name:
                continue
            if project_packages and not any(class_name == package or class_name.startswith(package + ".") for package in project_packages):
                continue
            if "$" in class_name:
                class_name = class_name.split("$", 1)[0]
            project_frames.append((class_name, method_name))
        # JFR frames are ordered from sampled leaf outward to callers.
        for index in range(len(project_frames) - 1):
            callee, caller = project_frames[index], project_frames[index + 1]
            if caller[0] != callee[0]:
                key = (caller[0], caller[1], callee[0], callee[1])
                edges[key] = edges.get(key, 0) + 1
    return [
        {"caller_module": a, "caller_function": b, "callee_module": c, "callee_function": d, "samples": n}
        for (a, b, c, d), n in edges.items()
    ]


def _run_jfr_print(jfr: str, recording: Path, root: Path) -> list[dict]:
    result = subprocess.run(
        [jfr, "print", "--json", "--events", "jdk.ExecutionSample", str(recording)],
        cwd=root, capture_output=True, text=True, timeout=45,
    )
    if result.returncode:
        raise RuntimeError("Could not read Java Flight Recorder output.\n" + result.stderr[-4000:])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The installed JDK's jfr tool returned an unsupported JSON format.") from exc
    return _parse_jfr_json(payload, root)


def execute_java_scenario(root: str | Path, scenario: str, timeout: int = BUILD_TIMEOUT) -> RuntimeArchitecture:
    """Build and profile the Spring Boot application in one isolated worktree."""
    root = Path(root).resolve()
    source = root / scenario
    if not source.is_file():
        raise FileNotFoundError(f"Spring Boot entry-point source not found: {source}")
    if not (root / "pom.xml").exists() and not any((root / n).exists() for n in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")):
        raise RuntimeError("The selected Java project has no Maven or Gradle build descriptor.")

    java = shutil.which("java")
    jcmd = shutil.which("jcmd")
    jfr = shutil.which("jfr")
    if not java or not jcmd or not jfr:
        raise RuntimeError("Java runtime tracing requires a full JDK (java, jcmd, and jfr on PATH). Install a JDK 11+ and restart the terminal/Streamlit.")
    version = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=10)
    version_text = version.stderr + version.stdout
    match = re.search(r'version "?(\d+)', version_text)
    if not match or int(match.group(1)) < 11:
        raise RuntimeError("Spring Boot JFR tracing requires JDK 11 or newer.")

    jar = _run_build(root, timeout)
    recording = root / ".architecture-runtime.jfr"
    log_path = root / ".architecture-runtime.log"
    recording.unlink(missing_ok=True)
    log_path.unlink(missing_ok=True)
    log_file = log_path.open("w", encoding="utf-8", errors="replace")
    process = None
    try:
        command = [
            java, "-XX:StartFlightRecording=filename=" + str(recording) + ",settings=profile,dumponexit=true",
            "-jar", str(jar), "--server.port=0",
        ]
        process = subprocess.Popen(command, cwd=root, stdout=log_file, stderr=subprocess.STDOUT)
        started = False
        deadline = time.monotonic() + min(STARTUP_TIMEOUT, max(20, timeout))
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                log_file.flush()
                log_text = log_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                log_text = ""
            if re.search(r"Started\s+\w+\s+in\s+[\d.]+\s+seconds", log_text) or "Started " in log_text:
                started = True
                break
            time.sleep(0.5)
        if not started:
            try:
                log_file.flush()
                log_text = log_path.read_text(encoding="utf-8", errors="ignore")[-7000:]
            except OSError:
                log_text = ""
            if process.poll() is not None:
                raise RuntimeError("Spring Boot application exited before startup completed.\n" + log_text)
            raise RuntimeError("Spring Boot did not report successful startup within the startup limit.\n" + log_text)

        time.sleep(SAMPLE_WINDOW_SECONDS)
        dump = subprocess.run([jcmd, str(process.pid), "JFR.dump", "filename=" + str(recording)], cwd=root, capture_output=True, text=True, timeout=30)
        if dump.returncode or not recording.exists():
            raise RuntimeError("Could not dump the running application's JFR recording.\n" + dump.stdout + dump.stderr)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        log_file.close()

    try:
        calls = _run_jfr_print(jfr, recording, root)
    finally:
        recording.unlink(missing_ok=True)
        log_path.unlink(missing_ok=True)

    architecture = RuntimeArchitecture(entry_point=scenario)
    for item in calls:
        architecture.add_call(RuntimeCall(
            caller_module=item["caller_module"],
            caller_function=item["caller_function"],
            callee_module=item["callee_module"],
            callee_function=item["callee_function"],
            caller_file="",
            callee_file="",
        ))
    architecture.trace_kind = "sampled"
    architecture.sample_count = sum(item["samples"] for item in calls)
    architecture.execution_mode = "spring_boot_startup"
    if not architecture.calls:
        raise RuntimeError("Spring Boot started, but JFR captured no project-to-project execution samples. This can happen when the app is idle during startup; add a bounded request/scenario hook before comparing runtime behavior.")
    return architecture
