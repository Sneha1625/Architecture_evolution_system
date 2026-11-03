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
    Build component-level relationships from actual Python imports.

    Example:

        analyzer.py
            imports parser
                ↓
        Analyzer → Parser
    """

    relationships = []

    # --------------------------------------------------
    # Map every parsed file to its component
    # --------------------------------------------------

    file_to_component = {}

    for component in components:
        for file_path in component.files:

            normalized = os.path.normpath(
                file_path
            ).lower()

            file_to_component[normalized] = component.id

            # Also store absolute path
            absolute = os.path.normpath(
                os.path.abspath(file_path)
            ).lower()

            file_to_component[absolute] = component.id

    # --------------------------------------------------
    # Map Python module names to components
    # --------------------------------------------------

    module_to_component = {}

    for component in components:

        for file_path in component.files:

            filename = os.path.basename(file_path)

            if not filename.endswith(".py"):
                continue

            module_name = filename[:-3].lower()

            module_to_component[
                module_name
            ] = component.id

    # --------------------------------------------------
    # Examine imports
    # --------------------------------------------------

    for result in parsed_results:

        source_file = (
            result.get("file")
            or result.get("file_path")
            or result.get("path")
            or ""
        )

        if not source_file:
            continue

        source_normalized = os.path.normpath(
            source_file
        ).lower()

        source_component = file_to_component.get(
            source_normalized
        )

        if not source_component:
            source_component = file_to_component.get(
                os.path.normpath(
                    os.path.abspath(source_file)
                ).lower()
            )

        if not source_component:
            continue

        imports = result.get(
            "imports",
            []
        )

        for imported in imports:

            if not imported:
                continue

            imported = str(imported).strip()

            # Example:
            #
            # from src.parser import parse_file
            #
            # becomes:
            #
            # src.parser
            #
            module_parts = imported.lower().split(".")

            target_component = None

            # Try complete module name first
            for length in range(
                len(module_parts),
                0,
                -1
            ):

                candidate = ".".join(
                    module_parts[:length]
                )

                if candidate in module_to_component:

                    target_component = (
                        module_to_component[candidate]
                    )

                    break

            # Try the final module name
            if not target_component:

                final_module = module_parts[-1]

                target_component = (
                    module_to_component.get(
                        final_module
                    )
                )

            # Ignore external libraries and self-dependencies
            if (
                target_component
                and target_component != source_component
            ):

                relationship = Relationship(
                    source=source_component,
                    target=target_component,
                    type="depends_on"
                )

                key = (
                    relationship.source,
                    relationship.target,
                    relationship.type
                )

                existing = {
                    (
                        r.source,
                        r.target,
                        r.type
                    )
                    for r in relationships
                }

                if key not in existing:

                    relationships.append(
                        relationship
                    )

                    # Update component dependency list
                    for component in components:

                        if component.id == source_component:

                            if (
                                target_component
                                not in component.dependencies
                            ):

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