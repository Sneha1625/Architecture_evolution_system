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
import tarfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from architecture_model.runtime_model import RuntimeArchitecture, RuntimeCall


NODE_EXTENSIONS = {".js", ".mjs", ".cjs", ".ts", ".mts", ".cts"}


def discover_node_entrypoints(worktree_path):
    """Return conservative, bounded JavaScript entry-point candidates."""
    root = Path(worktree_path).resolve()
    preferred = (
        "runtime_scenario.js", "main.js", "cli.js",
        "index.js", "sample_project.js",
        "runtime_scenario.mjs", "main.mjs", "index.mjs",
        "runtime_scenario.cjs", "main.cjs", "index.cjs",
        "runtime_scenario.ts", "main.ts", "index.ts",
        "runtime_scenario.mts", "main.mts", "index.mts",
        "runtime_scenario.cts", "main.cts", "index.cts",
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



def _find_node_binary(root: Path):
    """Find a Node.js executable in a cached toolchain directory."""
    name = "node.exe" if os.name == "nt" else "node"
    matches = list(Path(root).rglob(name))
    return matches[0] if matches else None


def _provision_node_runtime():
    """Download and cache the Node.js 22 LTS runtime on demand."""
    if os.environ.get("ARCHITECTURE_AUTO_INSTALL_NODE", "1").strip().lower() in {"0", "false", "no"}:
        raise RuntimeError(
            "JavaScript runtime tracing needs Node.js 22 or newer. "
            "Automatic setup is disabled by ARCHITECTURE_AUTO_INSTALL_NODE=0."
        )

    local_app_data = os.environ.get("LOCALAPPDATA")
    cache_base = Path(local_app_data) if local_app_data else Path.home() / ".cache"
    cache_root = cache_base / "ArchitectureIntelligence" / "toolchains" / "node-22"
    node_home = cache_root / "runtime"
    cached = _find_node_binary(node_home) if node_home.is_dir() else None
    if cached:
        return str(cached)

    if os.name == "nt":
        machine = os.environ.get("PROCESSOR_ARCHITECTURE", "AMD64").lower()
        platform_name = "win-arm64" if machine in {"arm64", "aarch64"} else "win-x64"
        archive_suffix = ".zip"
    elif __import__("platform").system() == "Darwin":
        machine = __import__("platform").machine().lower()
        platform_name = "darwin-arm64" if machine in {"arm64", "aarch64"} else "darwin-x64"
        archive_suffix = ".tar.xz"
    else:
        machine = __import__("platform").machine().lower()
        platform_name = "linux-arm64" if machine in {"arm64", "aarch64"} else "linux-x64"
        archive_suffix = ".tar.xz"

    cache_root.mkdir(parents=True, exist_ok=True)

    def download(url, destination, limit):
        request = urllib.request.Request(
            url, headers={"User-Agent": "Architecture-Intelligence-System/1.0"}
        )
        with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as output:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise RuntimeError("The Node.js download exceeded the safety limit.")
                output.write(chunk)

    with tempfile.TemporaryDirectory(prefix="architecture_node_setup_") as temporary:
        temporary_path = Path(temporary)
        archive = temporary_path / ("node-runtime" + archive_suffix)
        try:
            # The official distribution index identifies the current Node 22 LTS
            # release and avoids hard-coding a patch version.
            index_request = urllib.request.Request(
                "https://nodejs.org/dist/index.json",
                headers={"User-Agent": "Architecture-Intelligence-System/1.0"},
            )
            with urllib.request.urlopen(index_request, timeout=30) as response:
                releases = json.loads(response.read().decode("utf-8"))
            release = next(
                item for item in releases
                if item.get("version", "").startswith("v22.")
                and platform_name in item.get("files", [])
            )
            version = release["version"]
            archive_name = f"node-{version}-{platform_name}{archive_suffix}"
            download(
                f"https://nodejs.org/dist/{version}/{archive_name}",
                archive,
                150 * 1024 * 1024,
            )
        except (OSError, urllib.error.URLError, ValueError, KeyError, StopIteration, RuntimeError) as error:
            raise RuntimeError(
                "Could not download Node.js 22 automatically. Check internet access to "
                "nodejs.org and retry. You can also install Node.js 22 or newer manually. "
                f"Details: {error}"
            ) from error

        if not archive.is_file() or archive.stat().st_size == 0:
            raise RuntimeError("The Node.js download returned an empty archive.")

        extraction = temporary_path / "extracted"
        extraction.mkdir()
        try:
            if archive_suffix == ".zip":
                with zipfile.ZipFile(archive) as bundle:
                    for member in bundle.infolist():
                        destination = (extraction / member.filename).resolve()
                        if not destination.is_relative_to(extraction.resolve()):
                            raise RuntimeError("The Node.js archive contains an unsafe path.")
                    bundle.extractall(extraction)
            else:
                with tarfile.open(archive, "r:xz") as bundle:
                    for member in bundle.getmembers():
                        destination = (extraction / member.name).resolve()
                        if not destination.is_relative_to(extraction.resolve()):
                            raise RuntimeError("The Node.js archive contains an unsafe path.")
                        if member.issym() or member.islnk():
                            raise RuntimeError("The Node.js archive contains an unsupported link.")
                    bundle.extractall(extraction)
        except (OSError, zipfile.BadZipFile, tarfile.TarError) as error:
            raise RuntimeError("The downloaded Node.js archive could not be extracted.") from error

        binary = _find_node_binary(extraction)
        if not binary:
            raise RuntimeError("The downloaded archive did not contain the Node.js executable.")
        extracted_home = binary.parent.parent if binary.parent.name == "bin" else binary.parent
        if node_home.exists():
            shutil.rmtree(node_home, ignore_errors=True)
        shutil.move(str(extracted_home), str(node_home))

    installed = _find_node_binary(node_home)
    if not installed:
        raise RuntimeError("Node.js setup finished, but the executable was not found.")
    return str(installed)


def _resolve_node_executable():
    """Use Node.js from PATH or provision a cached Node 22 LTS runtime."""
    node = shutil.which("node")
    if node:
        return node
    return _provision_node_runtime()

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
    node = _resolve_node_executable()

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
        command = [node]
        if scenario_path.suffix.lower() in {".ts", ".mts", ".cts"}:
            # Node 22+ can strip erasable TypeScript syntax without a build step.
            # Projects requiring tsconfig transforms or custom loaders must use
            # their own compiled JavaScript entry point instead.
            command.append("--experimental-strip-types")
        command.extend([
            "--cpu-prof", "--cpu-prof-interval=100",
            f"--cpu-prof-dir={profile_dir}", str(scenario_path),
        ])
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
