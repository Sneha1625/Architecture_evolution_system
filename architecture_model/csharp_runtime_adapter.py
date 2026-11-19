"""C# runtime adapter using Microsoft dotnet-coverage Cobertura reports.

The adapter reports project source files with executed lines. It does not
claim to collect runtime call edges or invocation counts. A selected .csproj
must be a bounded console application; web-host launchers are excluded.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

IGNORED_DIRS = {
    ".git", ".vs", ".idea", "bin", "obj", "packages", "vendor",
    "node_modules", "test", "tests", "coverage", "artifacts",
}
SERVER_MARKERS = (
    "webapplication.createbuilder(", "app.run(", "host.run(",
    "webhost.creatwebhostbuilder(", "useurls(",
)


def discover_csharp_entrypoints(worktree_path):
    """Find bounded console .NET projects with a Program.cs entry point."""
    root = Path(worktree_path).resolve()
    candidates = []
    for project in root.rglob("*.csproj"):
        relative = project.relative_to(root)
        if any(part.lower() in IGNORED_DIRS for part in relative.parts[:-1]):
            continue
        try:
            project_text = project.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "Microsoft.NET.Sdk.Web" in project_text:
            continue
        project_root = project.parent
        program_files = [
            path for path in project_root.rglob("*.cs")
            if not any(part.lower() in IGNORED_DIRS for part in path.relative_to(project_root).parts[:-1])
            and path.name.lower() == "program.cs"
        ]
        if not program_files:
            continue
        try:
            sources = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in program_files)
        except OSError:
            continue
        if any(marker in sources.lower() for marker in SERVER_MARKERS):
            continue
        candidates.append(relative.as_posix())
    return sorted(
        candidates,
        key=lambda value: (
            0 if Path(value).stem.lower() == "runtime_scenario" else
            1 if Path(value).name.lower() == "app.csproj" else 2,
            len(Path(value).parts),
            value.lower(),
        ),
    )


def run_csharp_version(worktree_path, scenario, timeout=600):
    """Execute one .NET console project under dotnet-coverage."""
    root = Path(worktree_path).resolve()
    project = (root / scenario).resolve()
    try:
        project.relative_to(root)
    except ValueError as error:
        raise ValueError("C# project must be inside the selected repository.") from error
    if not project.is_file() or project.suffix.lower() != ".csproj":
        raise FileNotFoundError(f"C# project file not found: {project}")
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise RuntimeError(".NET SDK is required for C# runtime coverage but dotnet was not found on PATH.")

    with tempfile.TemporaryDirectory(prefix="architecture_csharp_runtime_") as temporary:
        temp = Path(temporary)
        coverage_tool = shutil.which("dotnet-coverage")
        if not coverage_tool:
            tool_dir = temp / "tools"
            tool_dir.mkdir()
            install = subprocess.run(
                [dotnet, "tool", "install", "dotnet-coverage", "--tool-path", str(tool_dir)],
                cwd=str(root), capture_output=True, text=True, timeout=timeout,
            )
            if install.returncode != 0:
                details = (install.stderr or install.stdout or "dotnet-coverage installation failed")[-5000:]
                raise RuntimeError(f"Could not install the temporary dotnet-coverage tool:\n{details}")
            coverage_tool = str(tool_dir / ("dotnet-coverage.exe" if __import__("os").name == "nt" else "dotnet-coverage"))

        report = temp / "coverage.cobertura.xml"
        command = f'dotnet run --project "{project}" --no-launch-profile'
        try:
            process = subprocess.run(
                [coverage_tool, "collect", command, "-f", "cobertura", "-o", str(report)],
                cwd=str(root), capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"C# runtime scenario timed out after {timeout} seconds: {scenario}") from error
        if process.returncode != 0:
            details = (process.stderr or process.stdout or "dotnet-coverage failed")[-5000:]
            raise RuntimeError(f"C# runtime scenario failed:\n{details}")
        if not report.is_file():
            raise RuntimeError("dotnet-coverage did not produce a Cobertura report.")

        try:
            report_root = ET.parse(report).getroot()
        except ET.ParseError as error:
            raise RuntimeError("dotnet-coverage produced invalid Cobertura XML.") from error

        from architecture_model.runtime_model import RuntimeArchitecture
        architecture = RuntimeArchitecture(entry_point=scenario)
        for class_node in report_root.findall(".//class"):
            file_name = class_node.attrib.get("filename", "")
            if not file_name:
                continue
            source = Path(file_name)
            if not source.is_absolute():
                source = (root / source).resolve()
            else:
                source = source.resolve()
            try:
                relative = source.relative_to(root).as_posix()
            except (ValueError, OSError, RuntimeError):
                continue
            if any(part.lower() in IGNORED_DIRS for part in Path(relative).parts):
                continue
            if any(int(line.attrib.get("hits", "0")) > 0 for line in class_node.findall(".//line")):
                architecture.modules.add(relative)

        # Keep the explicitly selected project represented even when the
        # report has no line-level entries for its top-level Program.cs file.
        if not architecture.modules:
            program = project.parent / "Program.cs"
            if program.is_file():
                architecture.modules.add(program.relative_to(root).as_posix())
        return architecture
