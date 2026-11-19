"""Java runtime adapter using Java Flight Recorder execution samples.

JFR stack samples identify project source files appearing on sampled stacks.
Adjacent project frames are retained as sampled caller/callee evidence; they are
not exact invocation counts. This adapter compiles dependency-free Java source
files with the installed JDK and runs one explicitly selected main class.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import tarfile
import urllib.error
import urllib.request
import zipfile
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


def _find_jdk_binaries(root: Path):
    """Find the executable JDK tools from a JDK bin directory.

    Some JDK distributions also contain an internal, non-executable file
    named lib/jfr. Searching the whole tree and taking the first match can
    select that file instead of the command-line bin/jfr launcher.
    """
    root = Path(root)
    names = ("java.exe", "javac.exe", "jfr.exe") if os.name == "nt" else ("java", "javac", "jfr")
    bin_directories = []
    direct_bin = root / "bin"
    if direct_bin.is_dir():
        bin_directories.append(direct_bin)
    bin_directories.extend(
        path for path in root.rglob("bin")
        if path.is_dir() and path not in bin_directories
    )

    matches = {}
    for name in names:
        candidates = [directory / name for directory in bin_directories]
        executable = next(
            (
                candidate for candidate in candidates
                if candidate.is_file() and (os.name == "nt" or os.access(candidate, os.X_OK))
            ),
            None,
        )
        if executable is None:
            return None
        matches[name] = executable
    return matches


def _provision_temurin_jdk():
    """Download and cache Temurin 21 on demand when no full JDK is installed.

    The download is performed once per user profile. Set
    ARCHITECTURE_AUTO_INSTALL_JDK=0 to disable automatic provisioning.
    """
    if os.environ.get("ARCHITECTURE_AUTO_INSTALL_JDK", "1").strip().lower() in {"0", "false", "no"}:
        raise RuntimeError(
            "Java runtime tracing needs a full JDK (java, javac and jfr). "
            "Automatic JDK setup is disabled by ARCHITECTURE_AUTO_INSTALL_JDK=0."
        )

    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        from_java_home = _find_jdk_binaries(Path(java_home))
        if from_java_home:
            return from_java_home

    local_app_data = os.environ.get("LOCALAPPDATA")
    cache_base = Path(local_app_data) if local_app_data else Path.home() / ".cache"
    cache_root = cache_base / "ArchitectureIntelligence" / "toolchains" / "temurin-21"
    jdk_home = cache_root / "jdk"
    cached = _find_jdk_binaries(jdk_home) if jdk_home.is_dir() else None
    if cached:
        return cached

    cache_root.mkdir(parents=True, exist_ok=True)
    system_name = "windows" if os.name == "nt" else (
        "mac" if os.uname().sysname == "Darwin" else "linux"
    )
    machine = os.environ.get("PROCESSOR_ARCHITECTURE", "") if os.name == "nt" else os.uname().machine
    architecture = "aarch64" if machine.lower() in {"arm64", "aarch64"} else "x64"
    archive_suffix = ".zip" if system_name == "windows" else ".tar.gz"
    asset_prefix = f"OpenJDK21U-jdk_{architecture}_{system_name}_hotspot_"

    def download_from(url, destination):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Architecture-Intelligence-System/1.0"},
        )
        with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as output:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > 600 * 1024 * 1024:
                    raise RuntimeError("The JDK download exceeded the 600 MB safety limit.")
                output.write(chunk)

    with tempfile.TemporaryDirectory(prefix="architecture_jdk_setup_") as temporary:
        temporary_path = Path(temporary)
        archive = temporary_path / ("temurin-jdk.zip" if archive_suffix == ".zip" else "temurin-jdk.tar.gz")
        download_errors = []
        # Try Adoptium's binary endpoint first. Some networks/proxies return 403
        # for this endpoint even though GitHub release downloads are permitted.
        adoptium_url = (
            f"https://api.adoptium.net/v3/binary/latest/21/ga/{system_name}/"
            f"{architecture}/jdk/hotspot/normal/eclipse"
        )
        try:
            download_from(adoptium_url, archive)
        except (OSError, urllib.error.URLError) as error:
            download_errors.append(f"Adoptium binary endpoint: {error}")
            # Resolve the current Temurin 21 release asset through GitHub's public
            # releases API, then download the matching platform archive.
            try:
                api_request = urllib.request.Request(
                    "https://api.github.com/repos/adoptium/temurin21-binaries/releases/latest",
                    headers={
                        "Accept": "application/vnd.github+json",
                        "User-Agent": "Architecture-Intelligence-System/1.0",
                    },
                )
                with urllib.request.urlopen(api_request, timeout=30) as response:
                    release = json.loads(response.read().decode("utf-8"))
                matching_assets = [
                    asset for asset in release.get("assets", [])
                    if asset.get("name", "").startswith(asset_prefix)
                    and asset.get("name", "").endswith(archive_suffix)
                ]
                if not matching_assets:
                    raise RuntimeError(
                        f"No Temurin 21 archive found for {system_name}/{architecture}."
                    )
                asset = matching_assets[0]
                download_from(asset["browser_download_url"], archive)
            except (OSError, urllib.error.URLError, ValueError, KeyError, RuntimeError) as error:
                download_errors.append(f"GitHub Temurin release fallback: {error}")
                raise RuntimeError(
                    "Could not download the Java JDK automatically. The Adoptium download "
                    "endpoint and GitHub release fallback both failed. Check internet access "
                    "to api.adoptium.net and github.com, then retry. You can also install "
                    "a JDK 21 manually. Details: " + " | ".join(download_errors)
                ) from error

        if not archive.is_file() or archive.stat().st_size == 0:
            raise RuntimeError("The Java JDK download returned an empty archive.")

        extraction = temporary_path / "extracted"
        extraction.mkdir()
        try:
            if zipfile.is_zipfile(archive):
                with zipfile.ZipFile(archive) as bundle:
                    for member in bundle.infolist():
                        destination = (extraction / member.filename).resolve()
                        if not destination.is_relative_to(extraction.resolve()):
                            raise RuntimeError("The downloaded JDK archive contains an unsafe path.")
                    bundle.extractall(extraction)
            else:
                with tarfile.open(archive, "r:*") as bundle:
                    for member in bundle.getmembers():
                        destination = (extraction / member.name).resolve()
                        if not destination.is_relative_to(extraction.resolve()):
                            raise RuntimeError("The downloaded JDK archive contains an unsafe path.")
                        if member.issym() or member.islnk():
                            raise RuntimeError("The downloaded JDK archive contains an unsupported link.")
                    bundle.extractall(extraction)
        except (OSError, zipfile.BadZipFile, tarfile.TarError) as error:
            raise RuntimeError("The downloaded Java JDK archive could not be extracted.") from error

        binaries = _find_jdk_binaries(extraction)
        if not binaries:
            raise RuntimeError("The downloaded archive did not contain java, javac and jfr.")
        extracted_home = next(path.parent.parent for path in binaries.values())
        if jdk_home.exists():
            shutil.rmtree(jdk_home, ignore_errors=True)
        shutil.move(str(extracted_home), str(jdk_home))

    installed = _find_jdk_binaries(jdk_home)
    if not installed:
        raise RuntimeError("Java JDK setup finished, but the required JDK tools were not found.")
    return installed


def _resolve_java_tools():
    """Use a system JDK when available, otherwise provision cached Temurin 21."""
    names = ("java.exe", "javac.exe", "jfr.exe") if os.name == "nt" else ("java", "javac", "jfr")
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        found = _find_jdk_binaries(Path(java_home))
        if found:
            return found
    found = {name: shutil.which(name[:-4] if name.endswith(".exe") else name) for name in names}
    if all(found.values()):
        return found
    return _provision_temurin_jdk()


def run_java_version(worktree_path, scenario, timeout=300):
    """Compile and execute one Java main class, provisioning a JDK if needed."""
    root = Path(worktree_path).resolve()
    scenario_path = (root / scenario).resolve()
    try:
        scenario_path.relative_to(root)
    except ValueError as error:
        raise ValueError("Runtime scenario must be inside the selected repository.") from error
    if not scenario_path.is_file() or scenario_path.suffix.lower() != ".java":
        raise FileNotFoundError(f"Java runtime scenario not found: {scenario_path}")

    java_tools = _resolve_java_tools()
    java = str(java_tools["java.exe" if os.name == "nt" else "java"])
    javac = str(java_tools["javac.exe" if os.name == "nt" else "javac"])
    jfr = str(java_tools["jfr.exe" if os.name == "nt" else "jfr"])

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
            "-XX:-Inline",
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
