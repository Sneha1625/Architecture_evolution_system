"""Ruby runtime adapter using TracePoint for executed files and calls."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from architecture_model.runtime_model import RuntimeArchitecture, RuntimeCall


def discover_ruby_entrypoints(worktree_path):
    root = Path(worktree_path).resolve()
    preferred = ("runtime_scenario.rb", "main.rb", "cli.rb", "run.rb", "app.rb")
    ignored = {".git", "vendor", "tmp", "log", "coverage", "node_modules", "test", "tests", "spec"}
    server_markers = ("rails server", "rackup", "webrick::httpserver.new", "tcpserver.new")
    candidates = []
    for path in root.rglob("*.rb"):
        relative = path.relative_to(root)
        if any(part.lower() in ignored for part in relative.parts[:-1]):
            continue
        if path.name.endswith(("_test.rb", "_spec.rb")) or path.name.lower() not in preferred:
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


def run_ruby_version(worktree_path, scenario, timeout=300):
    root = Path(worktree_path).resolve()
    scenario_path = (root / scenario).resolve()
    try:
        scenario_path.relative_to(root)
    except ValueError as error:
        raise ValueError("Runtime scenario must be inside the selected repository.") from error
    if not scenario_path.is_file() or scenario_path.suffix.lower() != ".rb":
        raise FileNotFoundError(f"Ruby runtime scenario not found: {scenario_path}")
    ruby = shutil.which("ruby")
    if not ruby:
        raise RuntimeError("Ruby is required for Ruby runtime tracing but was not found on PATH.")

    tracer = r'''
require "json"
require "pathname"
root = Pathname.new(ARGV[0]).realpath
scenario = Pathname.new(ARGV[1]).realpath
output = ARGV[2]
modules = {}
calls = []
trace = TracePoint.new(:line, :call) do |event|
  begin
    current = Pathname.new(event.path).realpath
    relative = current.relative_path_from(root).to_s
    next if relative.start_with?("..") || relative.split(/[\\\/]/).any? { |part| [".git", "vendor", "tmp", "gems"].include?(part) }
    modules[relative] = true
    if event.event == :call
      caller_location = caller_locations(1, 1)&.first
      if caller_location && caller_location.path
        caller_path = Pathname.new(caller_location.path).realpath rescue nil
        if caller_path
          caller_relative = caller_path.relative_path_from(root).to_s rescue ""
          unless caller_relative.start_with?("..") || caller_relative.empty?
            calls << {
              caller_module: caller_relative,
              caller_function: caller_location.base_label || "(top-level)",
              callee_module: relative,
              callee_function: event.method_id.to_s,
              caller_file: caller_relative,
              callee_file: relative
            }
          end
        end
      end
    end
  rescue StandardError
    next
  end
end
modules[scenario.relative_path_from(root).to_s] = true
begin
  Dir.chdir(root) do
    trace.enable
    load scenario.to_s
    trace.disable
  end
rescue SystemExit => error
  raise unless error.status == 0
ensure
  trace.disable
end
File.write(output, JSON.generate({modules: modules.keys.sort, calls: calls}))
'''
    architecture = RuntimeArchitecture(entry_point=scenario)
    with tempfile.TemporaryDirectory(prefix="architecture_ruby_runtime_") as temp:
        temp_path = Path(temp)
        tracer_path = temp_path / "trace_runtime.rb"
        output_path = temp_path / "trace.json"
        tracer_path.write_text(tracer, encoding="utf-8")
        try:
            process = subprocess.run(
                [ruby, str(tracer_path), str(root), str(scenario_path), str(output_path)],
                cwd=str(root), capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"Ruby runtime scenario timed out after {timeout} seconds: {scenario}") from error
        if process.returncode != 0:
            details = (process.stderr or process.stdout or "Ruby exited unsuccessfully")[-5000:]
            raise RuntimeError(f"Ruby runtime scenario failed ({process.returncode}):\n{details}")
        if not output_path.is_file():
            raise RuntimeError("Ruby runtime tracer did not produce an evidence file.")
        data = json.loads(output_path.read_text(encoding="utf-8"))
        architecture.modules.update(data.get("modules", []))
        for item in data.get("calls", []):
            architecture.add_call(RuntimeCall(**item))
    return architecture
