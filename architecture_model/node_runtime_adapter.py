"""Node.js runtime adapter using V8 coverage and sampled CPU profiles.

Coverage identifies project files that executed. V8 CPU profiles provide sampled
caller/callee evidence; they are deliberately not presented as exact call counts.
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
from urllib.parse import unquote, urlparse

from architecture_model.runtime_model import RuntimeArchitecture, RuntimeCall


NODE_EXTENSIONS = {".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx"}

# Node.js does not transform JSX. These patterns identify JSX element and
# fragment syntax so frontend component entrypoints are not selected as raw
# Node execution scenarios.
_JSX_OPENING_TAG = re.compile(
    r"<(?:[A-Za-z][A-Za-z0-9_.:-]*)(?:\s[^<>]*?)?\s*/?>|<>",
    re.DOTALL,
)
_JSX_CLOSING_TAG = re.compile(r"</(?:[A-Za-z][A-Za-z0-9_.:-]*|)>")


def _contains_jsx_syntax(source):
    """Return whether source appears to contain JSX that plain Node cannot run."""
    return bool(_JSX_OPENING_TAG.search(source) and _JSX_CLOSING_TAG.search(source)) or "<>" in source


def discover_node_entrypoints(worktree_path):
    """Return conservative, bounded JavaScript entry-point candidates."""
    root = Path(worktree_path).resolve()
    # Prefer explicit CLI/demo scenarios and backend entry points. A generic
    # index.js is frequently a browser bundle entry point, not a Node program.
    preferred = (
        "runtime_scenario.js", "cli.js", "main.js", "sample_project.js", "index.js",
        "runtime_scenario.mjs", "cli.mjs", "main.mjs", "sample_project.mjs", "index.mjs",
        "runtime_scenario.cjs", "cli.cjs", "main.cjs", "sample_project.cjs", "index.cjs",
        "runtime_scenario.ts", "cli.ts", "main.ts", "sample_project.ts", "index.ts",
        "runtime_scenario.mts", "cli.mts", "main.mts", "index.mts",
        "runtime_scenario.cts", "cli.cts", "main.cts", "index.cts",
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
    # Prefer a real test-suite workload over importing a router or app module
    # that registers handlers but never exercises them.
    package_file = root / "package.json"
    if package_file.is_file():
        try:
            package_data = json.loads(package_file.read_text(encoding="utf-8"))
            test_script = package_data.get("scripts", {}).get("test", "")
            if isinstance(test_script, str) and re.search(
                r"\b(?:jest|vitest|mocha|ava|tap|node\s+--test)\b",
                test_script,
                re.IGNORECASE,
            ):
                candidates.append("npm:test")
        except (OSError, json.JSONDecodeError, AttributeError):
            pass

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
        lowered = source.lower()
        if any(marker in lowered for marker in server_markers):
            continue
        # Browser scripts may be valid JavaScript but cannot run in plain Node:
        # DOM globals such as document/window are not defined outside a browser.
        # Exclude them rather than returning misleading zero/failed runtime data.
        browser_only_patterns = (
            r"\bdocument\s*\.",
            r"\bwindow\s*\.",
            r"\bnavigator\s*\.",
            r"\blocalStorage\b",
            r"\bsessionStorage\b",
            r"\bHTMLElement\b",
            r"\bHTMLCanvasElement\b",
            r"\bgetElementById\s*\(",
            r"\bquerySelector(?:All)?\s*\(",
            r"\brequestAnimationFrame\s*\(",
        )
        if any(re.search(pattern, source, re.IGNORECASE) for pattern in browser_only_patterns):
            continue
        # Frontend entrypoints often contain JSX and require a bundler/compiler.
        if _contains_jsx_syntax(source):
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
    if any(part.lower() in {"node_modules", "vendor", ".git", "dist", "build", "test", "tests", "__tests__"} for part in relative.parts):
        return None
    if re.search(r"(?:\.test|\.spec)\.[cm]?[jt]sx?$", path.name, re.IGNORECASE):
        return None
    # 
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
                (
                    item for item in releases
                    if item.get("version", "").startswith("v22.")
                    and platform_name in item.get("files", [])
                ),
                None,
            )
            if release:
                version = release["version"]
                archive_name = f"node-{version}-{platform_name}{archive_suffix}"
                download(
                    f"https://nodejs.org/dist/{version}/{archive_name}",
                    archive,
                    150 * 1024 * 1024,
                )
            else:
                # Some mirrors or index responses omit the platform list. Resolve
                # the official latest-v22.x archive from its published checksums.
                checksums_request = urllib.request.Request(
                    "https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt",
                    headers={"User-Agent": "Architecture-Intelligence-System/1.0"},
                )
                with urllib.request.urlopen(checksums_request, timeout=30) as response:
                    checksums = response.read().decode("utf-8", errors="replace")
                archive_name = next(
                    (
                        line.split()[-1]
                        for line in checksums.splitlines()
                        if line.split()
                        and line.split()[-1].startswith("node-v22.")
                        and line.split()[-1].endswith(f"-{platform_name}{archive_suffix}")
                    ),
                    None,
                )
                if not archive_name:
                    sample_names = [
                        line.split()[-1]
                        for line in checksums.splitlines()
                        if line.split() and line.split()[-1].startswith("node-v22.")
                    ][:8]
                    raise RuntimeError(
                        f"No official Node.js 22 archive was listed for {platform_name}. "
                        f"Available examples: {sample_names}"
                    )
                download(
                    f"https://nodejs.org/dist/latest-v22.x/{archive_name}",
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
                            link_target = (destination.parent / member.linkname).resolve()
                            if not link_target.is_relative_to(extraction.resolve()):
                                raise RuntimeError("The Node.js archive contains an unsafe link.")
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

def _resolve_npm_invocation(node_executable):
    """Locate npm beside Node, on PATH, or in the bundled Node 22 runtime."""
    def locate(node_path):
        node_path = Path(node_path).resolve()
        node_dir = node_path.parent
        candidates = [
            node_dir / "node_modules" / "npm" / "bin" / "npm-cli.js",
            node_dir / "npm" / "node_modules" / "npm" / "bin" / "npm-cli.js",
            node_dir.parent / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js",
        ]
        npm_path = shutil.which("npm") or shutil.which("npm.cmd")
        if npm_path:
            resolved_npm = Path(npm_path).resolve()
            if resolved_npm.is_file() and resolved_npm.suffix.lower() == ".js":
                candidates.insert(0, resolved_npm)
            candidates.extend([
                resolved_npm.parent / "node_modules" / "npm" / "bin" / "npm-cli.js",
                resolved_npm.parent.parent / "node_modules" / "npm" / "bin" / "npm-cli.js",
            ])
        for candidate in candidates:
            if candidate.is_file():
                return str(node_path), str(candidate), None
        if npm_path:
            return str(node_path), None, str(npm_path)
        return None

    found = locate(node_executable)
    if found:
        return found
    # A minimal PATH installation may contain node.exe but not npm. The
    # official cached distribution bundles both, so use it automatically.
    bundled_node = _provision_node_runtime()
    found = locate(bundled_node)
    if found:
        return found
    raise RuntimeError(
        "Node.js is available, but npm could not be located beside it or in the "
        "official cached Node.js distribution. Declared project dependencies "
        "cannot be installed for runtime comparison."
    )


def _run_npm(node_executable, npm_cli, npm_command, arguments, cwd, timeout):
    if npm_cli:
        command = [node_executable, npm_cli, *arguments]
        use_shell = False
    elif os.name == "nt":
        command = subprocess.list2cmdline([npm_command, *arguments])
        use_shell = True
    else:
        command = [npm_command, *arguments]
        use_shell = False
    return subprocess.run(
        command, cwd=str(cwd), capture_output=True, text=True,
        timeout=timeout, shell=use_shell,
    )


def _install_node_dependencies(root: Path, timeout=180, node_executable=None):
    """Install a selected commit's declared npm dependencies inside its isolated worktree.

    Lifecycle scripts are disabled because comparison only needs the dependency
    packages to load and execute the selected scenario. This keeps installation
    bounded and avoids running arbitrary package postinstall commands.
    """
    package_file = root / "package.json"
    if not package_file.is_file():
        return False

    try:
        package_data = json.loads(package_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read Node.js package.json: {error}") from error

    dependency_groups = (
        package_data.get("dependencies"),
        package_data.get("devDependencies"),
        package_data.get("optionalDependencies"),
    )
    if not any(isinstance(group, dict) and group for group in dependency_groups):
        return False

    npm_node, npm_cli, npm_command = _resolve_npm_invocation(
        node_executable or _resolve_node_executable()
    )

    if (root / "package-lock.json").is_file() or (root / "npm-shrinkwrap.json").is_file():
        arguments = ["ci", "--ignore-scripts", "--no-audit", "--no-fund"]
    else:
        arguments = [
            "install", "--ignore-scripts", "--no-audit", "--no-fund",
            "--package-lock=false",
        ]

    try:
        process = _run_npm(
            npm_node, npm_cli, npm_command, arguments, root, timeout
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"Installing Node.js dependencies exceeded {timeout} seconds for this commit."
        ) from error

    if process.returncode != 0:
        details = (process.stderr or process.stdout or "npm exited unsuccessfully")[-5000:]
        raise RuntimeError(
            f"Could not install Node.js dependencies for {root.name} "
            f"(npm exit {process.returncode}):\n{details}"
        )
    return True


def run_node_version(worktree_path, scenario, timeout=300):
    """Execute a JS/TS file or declared npm test workload and collect runtime evidence."""
    root = Path(worktree_path).resolve()
    npm_test = scenario == "npm:test"
    scenario_path = None if npm_test else (root / scenario).resolve()

    if npm_test:
        package_file = root / "package.json"
        try:
            package_data = json.loads(package_file.read_text(encoding="utf-8"))
            test_script = package_data.get("scripts", {}).get("test")
        except (OSError, json.JSONDecodeError, AttributeError) as error:
            raise FileNotFoundError(
                "The selected commit does not contain a readable package.json test script."
            ) from error
        if not isinstance(test_script, str) or not test_script.strip():
            raise FileNotFoundError("The selected commit does not declare an npm test script.")
    else:
        try:
            scenario_path.relative_to(root)
        except ValueError as error:
            raise ValueError("Runtime scenario must be inside the selected repository.") from error
        if not scenario_path.is_file() or scenario_path.suffix.lower() not in NODE_EXTENSIONS:
            raise FileNotFoundError(f"JavaScript runtime scenario not found: {scenario_path}")
        source = scenario_path.read_text(encoding="utf-8", errors="ignore")
        if _contains_jsx_syntax(source):
            raise RuntimeError(
                f"Selected scenario {scenario!r} contains JSX. Plain Node.js cannot execute JSX directly. "
                "Use a declared test script with its configured frontend toolchain, or select a "
                "bounded Node.js backend/CLI entry point."
            )

    node = _resolve_node_executable()
    _install_node_dependencies(root, timeout=min(timeout, 180), node_executable=node)

    architecture = RuntimeArchitecture(entry_point=scenario)
    if scenario_path is not None:
        architecture.modules.add(scenario_path.relative_to(root).as_posix())

    with tempfile.TemporaryDirectory(prefix="architecture_node_runtime_") as temp:
        temp_path = Path(temp)
        coverage_dir = temp_path / "coverage"
        profile_dir = temp_path / "profiles"
        coverage_dir.mkdir()
        profile_dir.mkdir()
        env = os.environ.copy()
        env["NODE_V8_COVERAGE"] = str(coverage_dir)
        env["CI"] = "1"
        env["FORCE_COLOR"] = "0"
        profile_options = [
            "--cpu-prof", "--cpu-prof-interval=100",
            f"--cpu-prof-dir={profile_dir}",
        ]

        if npm_test:
            npm_node, npm_cli, npm_command = _resolve_npm_invocation(node)
            # Child Node processes spawned by Jest/Vitest inherit profiler and
            # coverage settings, so test workers are included as well.
            env["NODE_OPTIONS"] = " ".join(
                item for item in (env.get("NODE_OPTIONS", ""), *profile_options) if item
            )
            if npm_cli:
                command = [npm_node, *profile_options, npm_cli, "test"]
                use_shell = False
            elif os.name == "nt":
                command = subprocess.list2cmdline([npm_command, "test"])
                use_shell = True
            else:
                command = [npm_command, "test"]
                use_shell = False
        else:
            command = [node]
            if scenario_path.suffix.lower() in {".ts", ".mts", ".cts"}:
                # tsx honors tsconfig and resolves TypeScript imports ending in
                # .js to their .ts source files.
                if (root / "node_modules" / "tsx" / "package.json").is_file():
                    command.extend(["--import", "tsx"])
                else:
                    command.append("--experimental-strip-types")
            command.extend([*profile_options, str(scenario_path)])
            use_shell = False

        try:
            process = subprocess.run(
                command, cwd=str(root), env=env, capture_output=True,
                text=True, timeout=timeout, shell=use_shell,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                f"Node.js runtime workload timed out after {timeout} seconds: {scenario}"
            ) from error
        if process.returncode != 0:
            details = (process.stderr or process.stdout or "Node.js exited unsuccessfully")[-5000:]
            label = "npm test workload" if npm_test else "Node.js runtime scenario"
            raise RuntimeError(f"{label} failed ({process.returncode}):\n{details}")

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
