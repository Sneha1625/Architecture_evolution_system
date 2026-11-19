import shutil

import pytest

from architecture_model.csharp_runtime_adapter import (
    discover_csharp_entrypoints,
    run_csharp_version,
)


pytestmark = pytest.mark.skipif(
    shutil.which("dotnet") is None,
    reason=".NET SDK is not installed in this test environment",
)


def test_csharp_runtime_adapter_reports_covered_project_files(tmp_path):
    project = tmp_path / "Sample"
    project.mkdir()
    (project / "Sample.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>'
        '<OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework>'
        '<ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable>'
        '</PropertyGroup></Project>',
        encoding="utf-8",
    )
    (project / "Program.cs").write_text(
        "using Sample;\nConsole.WriteLine(Helper.Calculate());\n",
        encoding="utf-8",
    )
    (project / "Helper.cs").write_text(
        "namespace Sample; public static class Helper { "
        "public static int Calculate() { var total = 0; "
        "for (var i = 0; i < 10000; i++) total += i; return total; } }\n",
        encoding="utf-8",
    )

    architecture = run_csharp_version(tmp_path, "Sample/Sample.csproj", timeout=180)

    assert any(path.endswith("Program.cs") for path in architecture.modules)
    assert any(path.endswith("Helper.cs") for path in architecture.modules)
    assert architecture.total_calls == 0


def test_csharp_discovery_skips_web_projects(tmp_path):
    console = tmp_path / "Console"
    web = tmp_path / "Web"
    console.mkdir()
    web.mkdir()
    (console / "Console.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk"></Project>', encoding="utf-8"
    )
    (console / "Program.cs").write_text(
        "Console.WriteLine(\"ok\");", encoding="utf-8"
    )
    (web / "Web.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>', encoding="utf-8"
    )
    (web / "Program.cs").write_text(
        "var app = WebApplication.CreateBuilder(args).Build(); app.Run();",
        encoding="utf-8",
    )

    candidates = discover_csharp_entrypoints(tmp_path)

    assert "Console/Console.csproj" in candidates
    assert "Web/Web.csproj" not in candidates
