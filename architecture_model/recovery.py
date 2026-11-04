import os
from typing import List, Dict, Any

from architecture_model.model import (
    Component,
    Relationship,
    ArchitectureSnapshot
)

def detect_layer(file_path: str) -> str:
    """
    Infer an architectural layer from directory and filename structure.
    """

    normalized = file_path.replace("\\", "/").lower()
    parts = normalized.split("/")

    filename = parts[-1] if parts else ""
    filename_without_ext = filename.rsplit(".", 1)[0]

    directories = set(parts[:-1])

    # Test files
    if (
        filename_without_ext.startswith("test_")
        or filename_without_ext.endswith("_test")
        or "tests" in directories
        or "test" in directories
    ):
        return "test"

    # Presentation layer
    if (
        "controller" in filename_without_ext
        or "route" in filename_without_ext
        or "api" in filename_without_ext
        or "view" in filename_without_ext
        or "controllers" in directories
        or "routes" in directories
        or "api" in directories
        or "views" in directories
    ):
        return "presentation"

    # Service layer
    if (
        "service" in filename_without_ext
        or "business" in filename_without_ext
        or "usecase" in filename_without_ext
        or "services" in directories
        or "business" in directories
        or "usecases" in directories
    ):
        return "service"

    # Data layer
    if (
        "repository" in filename_without_ext
        or "dao" in filename_without_ext
        or "database" in filename_without_ext
        or filename_without_ext in {"db", "database"}
        or "repositories" in directories
        or "database" in directories
        or "dao" in directories
    ):
        return "data"

    # Model layer
    if (
        filename_without_ext in {"model", "models"}
        or "models" in directories
    ):
        return "model"

    # Core/system layer
    if (
        "src" in directories
        or "architecture_model" in directories
    ):
        return "core"

    return "module"


def component_name_from_path(file_path: str) -> str:
    """Infer a useful component name from source layout, including Java packages."""
    normalized = file_path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if not parts:
        return "Unknown"
    lower_parts = [part.lower() for part in parts]
    # Maven/Gradle Java layout: do not collapse all source beneath the leading "com".
    for marker in (("src", "main", "java"), ("src", "test", "java")):
        for index in range(len(lower_parts) - 2):
            if tuple(lower_parts[index:index + 3]) == marker:
                package_parts = parts[index + 3:-1]
                if package_parts:
                    meaningful = [p for p in package_parts if p.lower() not in {"com", "org", "net", "io", "jakarta"}]
                    chosen = meaningful[-1] if meaningful else package_parts[-1]
                    return chosen.replace("_", " ").replace("-", " ").title()
                return os.path.splitext(parts[-1])[0].replace("_", " ").title()
    if "src" in lower_parts:
        src_index = lower_parts.index("src")
        after_src = parts[src_index + 1:]
        if len(after_src) == 1:
            return os.path.splitext(after_src[0])[0].replace("_", " ").title()
        if after_src:
            return after_src[0].replace("_", " ").title()
    if "architecture_model" in lower_parts:
        return "Architecture Model"
    if "features" in lower_parts:
        return "Features"
    return "Architecture Modeling System"

def build_components(parsed_results: List[Dict[str, Any]]) -> List[Component]:
    """
    Convert parser results into high-level architecture components.

    Files are grouped into components based on their location:
    - src/parser.py       -> Parser
    - src/analyzer.py     -> Analyzer
    - src/architect.py    -> Architect
    - architecture_model/ -> Architecture Model
    - features/           -> Features
    - root-level files    -> Architecture Modeling System

    Test files do not make the entire component a "test" layer.
    """

    grouped = {}

    for result in parsed_results:

        file_path = (
            result.get("file")
            or result.get("file_path")
            or result.get("path")
            or ""
        )

        if not file_path:
            continue

        # ---------------------------------------------
        # Determine component
        # ---------------------------------------------

        component_name = component_name_from_path(file_path)

        component_id = (
            "component_"
            + component_name.lower().replace(" ", "_")
        )

        if component_id not in grouped:
            grouped[component_id] = {
                "name": component_name,
                "files": [],
                "dependencies": set(),
                "layers": []
            }

        grouped[component_id]["files"].append(file_path)

        # ---------------------------------------------
        # Determine layer
        # ---------------------------------------------

        layer = detect_layer(file_path)

        grouped[component_id]["layers"].append(layer)

    # ---------------------------------------------
    # Create Component objects
    # ---------------------------------------------

    components = []

    for component_id, data in grouped.items():

        layers = data["layers"]

        # ---------------------------------------------
        # Ignore test files when determining the
        # architecture layer of a component.
        # ---------------------------------------------

        non_test_layers = [
            layer
            for layer in layers
            if layer != "test"
        ]

        if non_test_layers:

            layer = max(
                set(non_test_layers),
                key=non_test_layers.count
            )

        elif layers:

            # If the component contains only test files,
            # classify it as test.
            layer = "test"

        else:

            layer = "module"

        # ---------------------------------------------
        # Create component
        # ---------------------------------------------

        component = Component(
            id=component_id,
            name=data["name"],
            responsibility=(
                f"{data['name']} related functionality"
            ),
            layer=layer,
            files=data["files"],
            dependencies=list(data["dependencies"])
        )

        components.append(component)

    return components
def build_relationships(components: List[Component], parsed_results: List[Dict[str, Any]]) -> List[Relationship]:
    """Build component dependencies from Python, JS/TS, and Java project imports."""
    import re
    relationships = []
    existing = set()
    file_to_component = {}
    for component in components:
        for file_path in component.files:
            file_to_component[os.path.normcase(os.path.normpath(file_path))] = component.id

    def get_component(file_path):
        return file_to_component.get(os.path.normcase(os.path.normpath(file_path)))

    module_to_component = {}
    java_type_to_component = {}
    java_package_to_components = {}
    for item in parsed_results:
        path = item.get("file") or item.get("file_path") or item.get("path") or ""
        component_id = get_component(path)
        if not path or not component_id:
            continue
        language = (item.get("language") or ("python" if path.lower().endswith(".py") else "")).lower()
        if language == "python":
            module_to_component[os.path.basename(path)[:-3].lower()] = component_id
        elif language == "java":
            # Commit snapshots store repository-relative paths and the extracted
            # worktree is already gone here. Resolve package names from the standard
            # Maven/Gradle source layout instead of trying to reopen deleted files.
            normalized_parts = path.replace("\\", "/").split("/")
            lower_parts = [part.lower() for part in normalized_parts]
            package_parts = []
            for marker in (("src", "main", "java"), ("src", "test", "java")):
                for index in range(len(lower_parts) - 2):
                    if tuple(lower_parts[index:index + 3]) == marker:
                        package_parts = normalized_parts[index + 3:-1]
                        break
                if package_parts:
                    break
            package = ".".join(package_parts)
            class_name = os.path.splitext(os.path.basename(path))[0]
            qualified = f"{package}.{class_name}" if package else class_name
            java_type_to_component[qualified] = component_id
            if package:
                java_package_to_components.setdefault(package, set()).add(component_id)

    def resolve_js_import(source_file, imported):
        match = re.search(r"""(?:from\s+|import\s*)['"]([^'"]+)['"]""", imported)
        if not match:
            return None
        import_path = match.group(1)
        if not import_path.startswith("."):
            return None
        base = os.path.normpath(os.path.join(os.path.dirname(source_file), import_path))
        candidates = [base + ext for ext in ("", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".py")]
        candidates += [os.path.join(base, "index" + ext) for ext in (".js", ".jsx", ".ts", ".tsx", ".py", ".java")]
        for candidate in candidates:
            for item in parsed_results:
                path = item.get("file") or item.get("file_path") or item.get("path") or ""
                if os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(candidate)):
                    return path
        return None

    def resolve_java_import(imported):
        statement = re.sub(r"^\s*import\s+", "", imported.strip())
        statement = statement.removesuffix(";").strip()
        statement = re.sub(r"^static\s+", "", statement)
        if statement.endswith(".*"):
            targets = java_package_to_components.get(statement[:-2], set())
            return next(iter(targets)) if len(targets) == 1 else None
        return java_type_to_component.get(statement)

    for item in parsed_results:
        source_file = item.get("file") or item.get("file_path") or item.get("path") or ""
        source_component = get_component(source_file)
        if not source_file or not source_component:
            continue
        language = (item.get("language") or ("python" if source_file.lower().endswith(".py") else "")).lower()
        for imported in item.get("imports", []):
            if not imported:
                continue
            imported = str(imported).strip()
            target_component = None
            if language in ("javascript", "typescript", "tsx"):
                target_file = resolve_js_import(source_file, imported)
                target_component = get_component(target_file) if target_file else None
            elif language == "python":
                module_parts = imported.lower().split(".")
                for length in range(len(module_parts), 0, -1):
                    target_component = module_to_component.get(".".join(module_parts[:length]))
                    if target_component:
                        break
                if not target_component:
                    target_component = module_to_component.get(module_parts[-1])
            elif language == "java":
                target_component = resolve_java_import(imported)
            if target_component and target_component != source_component:
                key = (source_component, target_component, "depends_on")
                if key not in existing:
                    relationships.append(Relationship(source=source_component, target=target_component, type="depends_on"))
                    existing.add(key)
                    source = next((component for component in components if component.id == source_component), None)
                    if source is not None and target_component not in source.dependencies:
                        source.dependencies.append(target_component)
    return relationships

def recover_architecture(
    parsed_results: List[Dict[str, Any]],
    commit_hash: str = "unknown"
) -> ArchitectureSnapshot:
    """
    Main architecture recovery function.

    Converts parser output into a persistent ArchitectureSnapshot.
    """

    components = build_components(parsed_results)

    relationships = build_relationships(
        components,
        parsed_results
    )

    metrics = {
        "total_components": len(components),
        "total_relationships": len(relationships),
        "total_files": sum(
            len(component.files)
            for component in components
        )
    }

    snapshot = ArchitectureSnapshot(
        version="1.0",
        commit_hash=commit_hash,
        components=components,
        relationships=relationships,
        metrics=metrics,
        violations=[]
    )

    return snapshot

