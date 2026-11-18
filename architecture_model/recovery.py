"""Language-neutral architecture recovery from normalized parser output."""

import os
import re
from pathlib import PurePosixPath
from typing import List, Dict, Any

from architecture_model.model import Component, Relationship, ArchitectureSnapshot


SOURCE_ROOTS = {"src", "source", "lib", "pkg", "packages"}
SOURCE_ROOT_SEQUENCES = (("src", "main", "java"), ("src", "main", "kotlin"), ("src", "test", "java"), ("src", "test", "kotlin"), ("src", "main", "scala"), ("src", "test", "scala"))
IGNORED_PATH_PARTS = {
    ".git", ".venv", "venv", "node_modules", "vendor", "build", "dist",
    "target", "coverage", "__pycache__", "site-packages",
}
EXTENSIONS = (
    ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".java",
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx",
    ".cs", ".go", ".rs", ".php", ".rb",
)


def _path(value: str) -> str:
    return str(value or "").replace("\\", "/").strip("./")


def _file_of(result: Dict[str, Any]) -> str:
    return _path(result.get("file") or result.get("file_path") or result.get("path") or "")


def _relative_files(parsed_results: List[Dict[str, Any]]) -> Dict[str, str]:
    """Map original paths to stable paths relative to their shared repository root."""
    files = [_file_of(item) for item in parsed_results if _file_of(item)]
    if not files:
        return {}
    # A common path of files is their shared directory. For paths such as
    # src/a.py and src/pkg/b.py this intentionally removes the src prefix.
    try:
        common = os.path.commonpath([p.replace("/", os.sep) for p in files]).replace("\\", "/")
    except ValueError:
        common = ""
    if common in files:
        common = _path(os.path.dirname(common))
    common = common.rstrip("/")
    output = {}
    for original in files:
        relative = original
        if common and (original == common or original.startswith(common + "/")):
            relative = original[len(common):].lstrip("/")
        output[original] = relative or PurePosixPath(original).name
    return output


def detect_layer(file_path: str) -> str:
    """Infer a conventional layer when folder/file names provide evidence."""
    normalized = _path(file_path).lower()
    parts = normalized.split("/")
    stem = PurePosixPath(parts[-1]).stem if parts else ""
    directories = set(parts[:-1])

    if stem.startswith("test_") or stem.endswith("_test") or directories.intersection({"test", "tests", "__tests__"}):
        return "test"
    if any(token in stem for token in ("controller", "route", "endpoint", "view", "api")) or directories.intersection({"controller", "controllers", "routes", "views", "api", "presentation"}):
        return "presentation"
    if any(token in stem for token in ("service", "usecase", "business")) or directories.intersection({"service", "services", "usecase", "usecases", "business"}):
        return "service"
    if any(token in stem for token in ("repository", "dao", "database")) or directories.intersection({"repository", "repositories", "dao", "database", "persistence"}):
        return "data"
    if stem in {"model", "models", "entity", "entities"} or directories.intersection({"model", "models", "entities", "domain"}):
        return "model"
    if directories.intersection(SOURCE_ROOTS):
        return "core"
    return "module"


def _component_key(relative_path: str) -> str:
    parts = [part for part in relative_path.split("/") if part]
    if not parts:
        return "unknown"
    # Strip conventional source-root prefixes used by Python, JS, Java,
    # Kotlin and Scala repositories before choosing the package boundary.
    lowered = tuple(part.lower() for part in parts)
    for prefix in SOURCE_ROOT_SEQUENCES:
        if lowered[:len(prefix)] == prefix:
            parts = parts[len(prefix):]
            break
    else:
        if len(parts) > 1 and parts[0].lower() in SOURCE_ROOTS:
            parts = parts[1:]
    if len(parts) > 1:
        name = parts[0]
    else:
        name = PurePosixPath(parts[-1]).stem or "module"
    return name


def _display_name(value: str) -> str:
    return re.sub(r"[_-]+", " ", value).strip().title() or "Module"


def build_components(parsed_results: List[Dict[str, Any]]) -> List[Component]:
    """Group source files by their first meaningful package/module directory."""
    relative = _relative_files(parsed_results)
    grouped: Dict[str, Dict[str, Any]] = {}

    for result in parsed_results:
        original = _file_of(result)
        if not original:
            continue
        rel = relative.get(original, original)
        if any(part.lower() in IGNORED_PATH_PARTS for part in rel.split("/")):
            continue

        name_key = _component_key(rel)
        component_id = "component_" + re.sub(r"[^a-z0-9]+", "_", name_key.lower()).strip("_")
        if component_id == "component_":
            component_id = "component_module"

        item = grouped.setdefault(component_id, {
            "name": _display_name(name_key), "files": [], "layers": [],
        })
        item["files"].append(original)
        item["layers"].append(detect_layer(rel))

    components = []
    for component_id, data in grouped.items():
        non_test = [layer for layer in data["layers"] if layer != "test"]
        layers = non_test or data["layers"]
        layer = max(set(layers), key=layers.count) if layers else "module"
        components.append(Component(
            id=component_id,
            name=data["name"],
            responsibility=f"{data['name']} module/package functionality",
            layer=layer,
            files=sorted(set(data["files"])),
            dependencies=[],
        ))
    return components


def _import_targets(imported: str, language: str) -> List[str]:
    """Normalize parser import text into candidate module/path identifiers."""
    raw = str(imported or "").strip()
    if not raw:
        return []
    candidates = []

    def add(value: str):
        value = value.strip().strip(";").strip()
        value = value.strip("\\\"'() ")
        if value and value not in candidates:
            candidates.append(value)

    # Quoted paths cover JS/TS imports, C/C++ includes, PHP/Ruby requires,
    # and Go import declarations.
    for match in re.findall(r"""['"]([^'"]+)['"]""", raw):
        add(match)

    lang = (language or "").lower()
    if lang == "python":
        match = re.search(r"^\\s*from\\s+([\\w.]+)\\s+import", raw)
        if match:
            add(match.group(1))
        else:
            match = re.search(r"^\\s*import\\s+([\\w.]+)", raw)
            add(match.group(1) if match else raw)
    elif lang in {"javascript", "typescript", "tsx"}:
        if not candidates:
            match = re.search(r"""(?:from\\s*|import\\s*)['"]([^'"]+)['"]|require\\(\\s*['"]([^'"]+)['"]""", raw)
            if match:
                add(match.group(1) or match.group(2))
    elif lang in {"java", "csharp"}:
        match = re.search(r"(?:import|using)\\s+(?:static\\s+)?([\\w.]+)", raw)
        if match:
            add(match.group(1))
    elif lang in {"c", "cpp"}:
        match = re.search(r"""#\\s*include\\s*[<"]([^>"]+)""", raw)
        if match:
            # System headers will not resolve unless the repository contains
            # a matching project file, so both quote and angle forms are safe.
            add(match.group(1))
    elif lang == "go":
        if not candidates:
            value = raw.strip().strip("()").strip().strip('"')
            if value and not value.startswith("import"):
                add(value)
    elif lang == "rust":
        match = re.search(r"\\b(?:use|mod)\\s+([\\w:]+)", raw)
        if match:
            rust_path = match.group(1)
            add(rust_path)
            # In "use crate::module::Type", the source file belongs to
            # module.rs/mod.rs rather than a file named after the type.
            pieces = rust_path.split("::")
            if len(pieces) > 1:
                add(".".join(pieces[:-1]))
    elif lang == "php":
        match = re.search(r"\\b(?:use|require(?:_once)?|include(?:_once)?)\\s+([\\w\\\\./-]+)", raw, re.I)
        if match:
            add(match.group(1))
    elif lang == "ruby":
        match = re.search(r"""\\brequire(?:_relative)?\\s*\\(?\\s*['"]([^'"]+)""", raw)
        if match:
            add(match.group(1))
    if not candidates:
        add(raw)
    return candidates


def build_relationships(components: List[Component], parsed_results: List[Dict[str, Any]]) -> List[Relationship]:
    """Resolve internal imports across the eleven supported language families."""
    relationships = []
    seen = set()
    file_to_component = {}
    component_by_id = {component.id: component for component in components}
    all_files = []

    for component in components:
        for file_path in component.files:
            normalized = _path(os.path.normpath(file_path))
            file_to_component[normalized] = component.id
            all_files.append(normalized)

    def component_for_file(path: str):
        return file_to_component.get(_path(os.path.normpath(path)))

    # Index exact relative paths, module-qualified paths and unique basenames.
    path_index = {}
    stem_index: Dict[str, List[str]] = {}
    module_index = {}
    relative = _relative_files(parsed_results)
    for original in all_files:
        rel = relative.get(original, original)
        no_ext = rel
        for extension in EXTENSIONS:
            if no_ext.lower().endswith(extension):
                no_ext = no_ext[:-len(extension)]
                break
        normalized = no_ext.replace("\\", "/").strip("/")
        path_index[normalized.lower()] = original
        dotted = normalized.replace("/", ".").lower()
        module_index[dotted] = original
        stem = PurePosixPath(normalized).name.lower()
        stem_index.setdefault(stem, []).append(original)

    def resolve(source_file: str, imported: str, language: str):
        for token in _import_targets(imported, language):
            token = token.strip()
            if not token:
                continue
            source_rel = relative.get(source_file, source_file)
            # Resolve relative filesystem imports against the importing file.
            if token.startswith((".", "/")) or "/" in token or "\\\\" in token:
                base = os.path.normpath(os.path.join(os.path.dirname(source_rel), token)).replace("\\", "/")
                base = base.lstrip("./")
                for suffix in ("",) + EXTENSIONS:
                    key = (base + suffix).lower()
                    if key in path_index:
                        return path_index[key]
                for index_suffix in ("/index", "/__init__"):
                    for extension in EXTENSIONS:
                        key = (base + index_suffix + extension).lower()
                        if key in path_index:
                            return path_index[key]
            # Qualified module paths (Python, Java, C#, Go, Rust namespaces).
            dotted = token.replace("::", ".").replace("\\\\", ".").replace("/", ".").strip(".").lower()
            dotted = re.sub(r"\\.(py|js|jsx|mjs|cjs|ts|tsx|java|c|h|cc|cpp|cxx|hpp|hh|hxx|cs|go|rs|php|rb)$", "", dotted)
            for candidate in (dotted, dotted.replace(".", "/")):
                if candidate in module_index or candidate in path_index:
                    return module_index.get(candidate) or path_index.get(candidate)
            # Go module paths and Rust crate-qualified paths commonly include
            # a repository/module prefix absent from the local source path.
            suffix_matches = [
                original for key, original in module_index.items()
                if key.endswith("." + dotted) or dotted.endswith("." + key)
            ]
            if len(set(suffix_matches)) == 1:
                return suffix_matches[0]
            # A class/module import may identify a source file by its final segment.
            final = re.split(r"[./:]+", token)[-1].lower()
            final = re.sub(r"\\.(py|js|jsx|mjs|cjs|ts|tsx|java|c|h|cc|cpp|cxx|hpp|hh|hxx|cs|go|rs|php|rb)$", "", final)
            matches = stem_index.get(final, [])
            if len(matches) == 1:
                return matches[0]
        return None

    for result in parsed_results:
        source_file = _file_of(result)
        source_component = component_for_file(source_file)
        if not source_component:
            continue
        language = (result.get("language") or "").lower()
        if not language:
            extension = PurePosixPath(source_file).suffix.lower()
            language = {
                ".py": "python", ".js": "javascript", ".jsx": "javascript",
                ".mjs": "javascript", ".cjs": "javascript", ".ts": "typescript",
                ".tsx": "tsx", ".java": "java", ".c": "c", ".h": "c",
                ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp",
                ".hh": "cpp", ".hxx": "cpp", ".cs": "csharp", ".go": "go",
                ".rs": "rust", ".php": "php", ".rb": "ruby",
            }.get(extension, "")
        for imported in result.get("imports", []) or []:
            target_file = resolve(source_file, str(imported), language)
            target_component = component_for_file(target_file) if target_file else None
            if not target_component or target_component == source_component:
                continue
            key = (source_component, target_component, "depends_on")
            if key in seen:
                continue
            seen.add(key)
            relationships.append(Relationship(source=source_component, target=target_component, type="depends_on"))
            component_by_id[source_component].dependencies.append(target_component)

    return relationships


def recover_architecture(parsed_results: List[Dict[str, Any]], commit_hash: str = "unknown") -> ArchitectureSnapshot:
    """Convert normalized parser results into an architecture snapshot."""
    components = build_components(parsed_results)
    relationships = build_relationships(components, parsed_results)
    metrics = {
        "total_components": len(components),
        "total_relationships": len(relationships),
        "total_files": sum(len(component.files) for component in components),
    }
    version_label = f"commit-{str(commit_hash)[:7]}" if commit_hash and commit_hash != "unknown" else "local"
    return ArchitectureSnapshot(
        version=version_label,
        commit_hash=commit_hash,
        components=components,
        relationships=relationships,
        metrics=metrics,
        violations=[],
    )
