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
    """
    Determine the architecture component from a file path.

    Files directly under src/ become individual components.
    Files inside a subdirectory are grouped by that subdirectory.
    Files at the project root belong to the main system component.
    """

    normalized = file_path.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]

    if not parts:
        return "Unknown"

    filename = parts[-1]
    filename_without_ext = os.path.splitext(filename)[0]

    # Find the src directory.
    src_index = None

    for i, part in enumerate(parts):
        if part.lower() == "src":
            src_index = i
            break

    # Files directly inside src/
    #
    # Example:
    # src/parser.py -> Parser
    # src/analyzer.py -> Analyzer
    if src_index is not None:
        items_after_src = parts[src_index + 1:]

        if len(items_after_src) == 1:
            return filename_without_ext.replace("_", " ").title()

        # Files inside a subdirectory of src/
        #
        # Example:
        # src/database/models.py -> Database
        directory = items_after_src[0]

        return directory.replace("_", " ").title()

    # Files inside architecture_model/
    if "architecture_model" in [p.lower() for p in parts]:
        return "Architecture Model"

    # Files inside features/
    if "features" in [p.lower() for p in parts]:
        return "Features"

    # Files directly in the project root
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
def build_relationships(
    components: List[Component],
    parsed_results: List[Dict[str, Any]]
) -> List[Relationship]:
    """
    Build component-level relationships from Python,
    JavaScript, and TypeScript imports.
    """

    relationships = []
    existing = set()

    file_to_component = {}

    for component in components:
        for file_path in component.files:
            normalized = os.path.normcase(
                os.path.normpath(file_path)
            )
            file_to_component[normalized] = component.id

    def get_component(file_path):
        normalized = os.path.normcase(
            os.path.normpath(file_path)
        )
        return file_to_component.get(normalized)

    # Index project files for resolving relative imports.
    project_files = []

    for result in parsed_results:
        path = (
            result.get("file")
            or result.get("file_path")
            or result.get("path")
            or ""
        )

        if path:
            project_files.append(path)

    def resolve_relative_import(source_file, imported):
        import re

        match = re.search(
            r"""from\s+['"]([^'"]+)['"]|import\s+['"]([^'"]+)['"]""",
            imported
        )

        if not match:
            return None

        import_path = match.group(1) or match.group(2)

        if not import_path.startswith("."):
            return None

        source_directory = os.path.dirname(source_file)

        target_base = os.path.normpath(
            os.path.join(source_directory, import_path)
        )

        extensions = [
            "",
            ".js", ".jsx", ".mjs", ".cjs",
            ".ts", ".tsx"
        ]

        candidates = []

        for extension in extensions:
            candidates.append(target_base + extension)

        for extension in [".js", ".jsx", ".ts", ".tsx"]:
            candidates.append(
                os.path.join(target_base, "index" + extension)
            )

        normalized_project_files = {
            os.path.normcase(os.path.normpath(path)): path
            for path in project_files
        }

        for candidate in candidates:
            key = os.path.normcase(
                os.path.normpath(candidate)
            )

            if key in normalized_project_files:
                return normalized_project_files[key]

        return None

    # Index Python module names.
    module_to_component = {}

    for component in components:
        for file_path in component.files:
            filename = os.path.basename(file_path)

            if filename.endswith(".py"):
                module_to_component[
                    filename[:-3].lower()
                ] = component.id

    for result in parsed_results:
        source_file = (
            result.get("file")
            or result.get("file_path")
            or result.get("path")
            or ""
        )

        if not source_file:
            continue

        source_component = get_component(source_file)

        if not source_component:
            continue

        language = (
    result.get("language")
    or ("python" if source_file.lower().endswith(".py") else "")
).lower()

        for imported in result.get("imports", []):
            if not imported:
                continue

            imported = str(imported).strip()
            target_component = None

            if language in ("javascript", "typescript", "tsx"):
                target_file = resolve_relative_import(
                    source_file,
                    imported
                )

                if target_file:
                    target_component = get_component(target_file)

            elif language == "python":
                module_parts = imported.lower().split(".")

                for length in range(len(module_parts), 0, -1):
                    candidate = ".".join(module_parts[:length])

                    if candidate in module_to_component:
                        target_component = module_to_component[candidate]
                        break

                if not target_component:
                    target_component = module_to_component.get(
                        module_parts[-1]
                    )

            if (
                target_component
                and target_component != source_component
            ):
                key = (
                    source_component,
                    target_component,
                    "depends_on"
                )

                if key not in existing:
                    relationships.append(
                        Relationship(
                            source=source_component,
                            target=target_component,
                            type="depends_on"
                        )
                    )

                    existing.add(key)

                    for component in components:
                        if component.id == source_component:
                            if target_component not in component.dependencies:
                                component.dependencies.append(
                                    target_component
                                )

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

