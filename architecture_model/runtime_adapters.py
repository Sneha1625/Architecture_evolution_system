"""
Language-aware runtime tracing adapters.

Python uses sys.setprofile for exact observed Python function calls.
JavaScript uses the Node/V8 CPU profiler; its edges are sampled stack
relationships and MUST be presented as samples, not exact call counts.

Other languages are detected and reported with actionable toolchain/scenario
requirements. They are never silently represented by static imports as runtime
calls.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from architecture_model.runtime_model import RuntimeArchitecture, RuntimeCall

LANGUAGE_BY_SUFFIX = {
    ".py": "python", ".js": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".jsx": "javascript", ".java": "java", ".go": "go", ".rs": "rust",
    ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp",
    ".hpp": "cpp", ".cs": "csharp", ".php": "php", ".rb": "ruby",
}
IGNORED_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", "site-packages",
    "node_modules", "vendor", "target", "build", "dist", ".next", "bin", "obj",
}
PREFERRED_NAMES = (
    "runtime_scenario.py", "runtime_scenario.js", "runtime_scenario.mjs",
    "runtime_scenario.ts", "sample_project.py", "main.py", "main.js",
    "main.mjs", "index.js", "index.mjs", "cli.py", "run.py",
    "Main.java", "main.go", "main.rs", "Program.cs",
)


def language_for_path(path: str | Path) -> Optional[str]:
    return LANGUAGE_BY_SUFFIX.get(Path(path).suffix.lower())


def _is_candidate(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    if any(part.lower() in IGNORED_DIRS for part in relative.parts[:-1]):
        return False
    name = path.name.lower()
    return not (
        name.startswith("test_") or name.endswith("_test.py")
        or name.endswith(".test.js") or name.endswith(".spec.js")
        or name.endswith(".test.ts") or name.endswith(".spec.ts")
    )


def discover_entrypoints(root: str | Path) -> dict[str, list[str]]:
    """Discover plausible executable files, grouped by language."""
    root = Path(root).resolve()
    found: dict[str, list[str]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        language = language_for_path(path)
        if not language or not _is_candidate(path, root):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")[:120_000].lower()
        except OSError:
            continue
        if language == "python" and any(
            marker in source for marker in (
                "streamlit.run(", "uvicorn.run(", "app.run(", "gradio.launch("
            )
        ):
            continue
        found.setdefault(language, []).append(path.relative_to(root).as_posix())
    preferred = {name: i for i, name in enumerate(PREFERRED_NAMES)}
    for values in found.values():
        values.sort(key=lambda value: (
            preferred.get(Path(value).name, len(preferred)),
            len(Path(value).parts), value.lower(),
        ))
    return found


def common_entrypoint(v1: str | Path, v2: str | Path) -> tuple[str, str]:
    """Return (language, relative path) shared by the two selected commits."""
    first, second = discover_entrypoints(v1), discover_entrypoints(v2)
    shared = [
        (language, path)
        for language in first.keys() & second.keys()
        for path in set(first[language]) & set(second[language])
    ]
    if not shared:
        raise FileNotFoundError(
            "No common executable source file was found in the selected commits. "
            "Add a bounded runtime scenario present in both versions, such as "
            "runtime_scenario.py or runtime_scenario.js. Static architecture "
            "comparison remains available."
        )
    order = {name: i for i, name in enumerate(PREFERRED_NAMES)}
    shared.sort(key=lambda item: (
        order.get(Path(item[1]).name, len(order)),
        len(Path(item[1]).parts), item[1].lower(),
    ))
    return shared[0]


NODE_PROFILE_RUNNER = r'''
const inspector = require("inspector");
const path = require("path");
const { pathToFileURL, fileURLToPath } = require("url");
const session = new inspector.Session();
session.connect();

function post(method, params = {}) {
  return new Promise((resolve, reject) => {
    session.post(method, params, (error, result) => error ? reject(error) : resolve(result));
  });
}

(async () => {
  const scenario = path.resolve(process.argv[2]);
  const root = path.resolve(process.argv[3]);
  const output = path.resolve(process.argv[4]);
  try {
    await post("Profiler.enable");
    await post("Profiler.start");
    try {
      if (scenario.endsWith(".mjs") || scenario.endsWith(".ts")) {
        await import(pathToFileURL(scenario).href);
      } else {
        require(scenario);
      }
    } finally {
      const { profile } = await post("Profiler.stop");
      const nodes = new Map(profile.nodes.map(n => [n.id, n]));
      const calls = [];
      function visit(node, parent) {
        const frame = node.callFrame || {};
        const fileUrl = frame.url || "";
        const parentFrame = parent && parent.callFrame || {};
        const parentUrl = parentFrame.url || "";
        const toPath = value => value.startsWith("file://") ? fileURLToPath(value) : value;
        const file = toPath(fileUrl);
        const parentFile = toPath(parentUrl);
        const inProject = value => {
          if (!value || value.startsWith("node:")) return false;
          try { return path.relative(root, value).startsWith("..") === false; }
          catch (_) { return false; }
        };
        if (parent && inProject(parentFile) && inProject(file)) {
          calls.push({
            caller_module: path.relative(root, parentFile).replace(/\\/g, "/"),
            caller_function: parentFrame.functionName || "(anonymous)",
            callee_module: path.relative(root, file).replace(/\\/g, "/"),
            callee_function: frame.functionName || "(anonymous)",
            caller_file: parentFile,
            callee_file: file,
            sample_count: node.hitCount || 0
          });
        }
        for (const childId of node.children || []) {
          const child = nodes.get(childId);
          if (child) visit(child, node);
        }
      }
      const childIds = new Set();
      for (const node of profile.nodes) for (const childId of node.children || []) childIds.add(childId);
      for (const rootNode of profile.nodes.filter(n => !childIds.has(n.id))) visit(rootNode, null);
      require("fs").writeFileSync(output, JSON.stringify({
        calls, entry_point: path.relative(root, scenario),
        trace_kind: "v8_cpu_profile_samples",
        sample_count: profile.samples ? profile.samples.length : 0
      }, null, 2));
    }
  } catch (error) {
    require("fs").writeFileSync(output, JSON.stringify({error: String(error.stack || error)}));
    process.exitCode = 1;
  } finally {
    session.disconnect();
  }
})();
'''


def _run_node(root: Path, scenario: str, timeout: int) -> RuntimeArchitecture:
    node = shutil.which("node")
    if not node:
        raise RuntimeError(
            "This scenario is JavaScript/TypeScript, but Node.js was not found. "
            "Install Node.js and ensure node --version works in the same terminal "
            "used to start Streamlit."
        )
    suffix = Path(scenario).suffix.lower()
    if suffix in {".ts", ".tsx"}:
        version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10)
        try:
            major = int(version.stdout.strip().lstrip("v").split(".")[0])
        except (ValueError, IndexError):
            major = 0
        if major < 22:
            raise RuntimeError(
                "Direct TypeScript runtime tracing requires Node.js 22 or newer "
                "for built-in type stripping. Supply compiled JavaScript or "
                "configure a TypeScript loader for older Node.js releases."
            )
        node_args = ["--experimental-strip-types"]
    elif suffix in {".mjs", ".js", ".cjs"}:
        node_args = []
    else:
        raise RuntimeError("The Node adapter cannot execute this scenario extension: " + suffix + ". JSX/TSX require a project-specific transpiler; provide a compiled .js/.mjs scenario.")

    with tempfile.TemporaryDirectory(prefix="architecture_node_profile_") as temp:
        runner = Path(temp) / "profile_runner.cjs"
        output = Path(temp) / "profile.json"
        runner.write_text(NODE_PROFILE_RUNNER, encoding="utf-8")
        command = [
            node, *node_args, str(runner), str((root / scenario).resolve()),
            str(root), str(output),
        ]
        try:
            process = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Node.js runtime scenario exceeded the " + str(timeout) + " second time limit: " + scenario
            ) from exc
        if not output.exists():
            raise RuntimeError(
                "Node.js did not produce a V8 profile.\nstdout:\n"
                + process.stdout + "\nstderr:\n" + process.stderr
            )
        payload = json.loads(output.read_text(encoding="utf-8"))
        if payload.get("error"):
            raise RuntimeError("Node.js scenario failed:\n" + payload["error"])
        architecture = RuntimeArchitecture(entry_point=scenario)
        for item in payload.get("calls", []):
            architecture.add_call(RuntimeCall(
                caller_module=item["caller_module"],
                caller_function=item["caller_function"],
                callee_module=item["callee_module"],
                callee_function=item["callee_function"],
                caller_file=item["caller_file"],
                callee_file=item["callee_file"],
            ))
        architecture.trace_kind = "sampled"
        architecture.sample_count = payload.get("sample_count", 0)
        return architecture


def execute_scenario(root: str | Path, scenario: str, timeout: int = 300) -> RuntimeArchitecture:
    """Dispatch a scenario to its language-specific runtime adapter."""
    root = Path(root).resolve()
    language = language_for_path(scenario)
    if language in {"javascript", "typescript"}:
        return _run_node(root, scenario, timeout)
    if language == "python":
        from architecture_model.runtime_version_runner import run_version
        return run_version(root, scenario=scenario, timeout=timeout)

    requirements = {
        "java": "JDK with javac and java",
        "go": "Go toolchain",
        "rust": "Rust toolchain (rustc/cargo)",
        "c": "C compiler (gcc or clang)",
        "cpp": "C++ compiler (g++ or clang++)",
        "csharp": ".NET SDK",
        "php": "PHP CLI",
        "ruby": "Ruby interpreter",
    }
    requirement = requirements.get(language, "a supported runtime")
    raise RuntimeError(
        "Detected " + str(language or "unknown") + " scenario " + scenario
        + ", but a verified call-level runtime adapter is not implemented for it. "
        + "Required environment: " + requirement + ". Static import/dependency "
        + "edges will not be misrepresented as runtime calls; static architecture "
        + "comparison remains available."
    )
