"""
Runtime Architecture Evolution.

Compares runtime architectures captured from two different
software versions/executions.

This is the dynamic equivalent of static architecture
snapshot comparison.

Example:

    Runtime V1  ->  Runtime V2

Detects:
    - added runtime modules
    - removed runtime modules
    - common runtime modules
    - added runtime relationships
    - removed runtime relationships
    - common runtime relationships
    - relationship call-count changes
    - function-level runtime changes
    - overall runtime evolution summary
"""

from typing import Any, Dict, List, Tuple

from architecture_model.runtime_model import RuntimeArchitecture


def _relationship_map(
    architecture: RuntimeArchitecture,
) -> Dict[Tuple[str, str], Any]:
    """
    Convert runtime relationships into a dictionary indexed
    by (source, target).
    """

    result = {}

    for relationship in architecture.get_relationships():
        key = (
            relationship.source,
            relationship.target,
        )

        result[key] = relationship

    return result


def compare_runtime_modules(
    old_architecture: RuntimeArchitecture,
    new_architecture: RuntimeArchitecture,
) -> Dict[str, List[str]]:
    """
    Compare modules observed during two runtime executions.
    """

    old_modules = set(old_architecture.modules)
    new_modules = set(new_architecture.modules)

    return {
        "added": sorted(new_modules - old_modules),
        "removed": sorted(old_modules - new_modules),
        "common": sorted(old_modules & new_modules),
    }


def compare_runtime_relationships(
    old_architecture: RuntimeArchitecture,
    new_architecture: RuntimeArchitecture,
) -> Dict[str, Any]:
    """
    Compare module-to-module runtime relationships.
    """

    old_map = _relationship_map(old_architecture)
    new_map = _relationship_map(new_architecture)

    old_keys = set(old_map.keys())
    new_keys = set(new_map.keys())

    added_keys = new_keys - old_keys
    removed_keys = old_keys - new_keys
    common_keys = old_keys & new_keys

    added = []
    removed = []
    common = []
    call_count_changes = []
    function_changes = []

    # ---------------------------------------------------------
    # Added relationships
    # ---------------------------------------------------------

    for key in sorted(added_keys):
        relationship = new_map[key]

        added.append(
            {
                "source": relationship.source,
                "target": relationship.target,
                "call_count": relationship.call_count,
                "functions": sorted(relationship.functions),
            }
        )

    # ---------------------------------------------------------
    # Removed relationships
    # ---------------------------------------------------------

    for key in sorted(removed_keys):
        relationship = old_map[key]

        removed.append(
            {
                "source": relationship.source,
                "target": relationship.target,
                "call_count": relationship.call_count,
                "functions": sorted(relationship.functions),
            }
        )

    # ---------------------------------------------------------
    # Common relationships
    # ---------------------------------------------------------

    for key in sorted(common_keys):
        old_relationship = old_map[key]
        new_relationship = new_map[key]

        old_functions = set(old_relationship.functions)
        new_functions = set(new_relationship.functions)

        common.append(
            {
                "source": key[0],
                "target": key[1],
                "old_call_count": old_relationship.call_count,
                "new_call_count": new_relationship.call_count,
            }
        )

        # -----------------------------------------------------
        # Call count change
        # -----------------------------------------------------

        if (
            old_relationship.call_count
            != new_relationship.call_count
        ):
            call_count_changes.append(
                {
                    "source": key[0],
                    "target": key[1],
                    "old_call_count": old_relationship.call_count,
                    "new_call_count": new_relationship.call_count,
                    "difference": (
                        new_relationship.call_count
                        - old_relationship.call_count
                    ),
                }
            )

        # -----------------------------------------------------
        # Function change
        # -----------------------------------------------------

        added_functions = sorted(
            new_functions - old_functions
        )

        removed_functions = sorted(
            old_functions - new_functions
        )

        if added_functions or removed_functions:
            function_changes.append(
                {
                    "source": key[0],
                    "target": key[1],
                    "added_functions": added_functions,
                    "removed_functions": removed_functions,
                }
            )

    return {
        "added": added,
        "removed": removed,
        "common": common,
        "call_count_changes": call_count_changes,
        "function_changes": function_changes,
    }


def compare_runtime_architectures(
    old_architecture: RuntimeArchitecture,
    new_architecture: RuntimeArchitecture,
    old_version: str = "V1",
    new_version: str = "V2",
) -> Dict[str, Any]:
    """
    Perform complete dynamic architecture evolution analysis.

    Parameters
    ----------
    old_architecture:
        Runtime architecture observed for the older version.

    new_architecture:
        Runtime architecture observed for the newer version.

    old_version:
        Label for the older software version.

    new_version:
        Label for the newer software version.

    Returns
    -------
    dict
        Complete runtime evolution information.
    """

    module_changes = compare_runtime_modules(
        old_architecture,
        new_architecture,
    )

    relationship_changes = compare_runtime_relationships(
        old_architecture,
        new_architecture,
    )

    old_relationship_count = (
        old_architecture.get_relationship_count()
    )

    new_relationship_count = (
        new_architecture.get_relationship_count()
    )

    old_module_count = old_architecture.get_module_count()
    new_module_count = new_architecture.get_module_count()

    old_total_calls = old_architecture.total_calls
    new_total_calls = new_architecture.total_calls

    summary = {
        "modules_added": len(module_changes["added"]),
        "modules_removed": len(module_changes["removed"]),
        "relationships_added": len(
            relationship_changes["added"]
        ),
        "relationships_removed": len(
            relationship_changes["removed"]
        ),
        "call_count_changes": len(
            relationship_changes["call_count_changes"]
        ),
        "function_changes": len(
            relationship_changes["function_changes"]
        ),
    }

    summary["total_behavioral_changes"] = (
        summary["modules_added"]
        + summary["modules_removed"]
        + summary["relationships_added"]
        + summary["relationships_removed"]
        + summary["call_count_changes"]
        + summary["function_changes"]
    )

    return {
        "old_version": old_version,
        "new_version": new_version,

        "entry_points": {
            "old": old_architecture.entry_point,
            "new": new_architecture.entry_point,
        },

        "old_runtime": {
            "modules": old_module_count,
            "relationships": old_relationship_count,
            "total_calls": old_total_calls,
        },

        "new_runtime": {
            "modules": new_module_count,
            "relationships": new_relationship_count,
            "total_calls": new_total_calls,
        },

        "module_changes": module_changes,

        "relationship_changes": relationship_changes,

        "call_difference": (
            new_total_calls - old_total_calls
        ),

        "summary": summary,
    }


def has_runtime_architecture_changed(
    comparison: Dict[str, Any],
) -> bool:
    """
    Return True when runtime behavior changed between versions.
    """

    return (
        comparison.get(
            "summary",
            {}
        ).get(
            "total_behavioral_changes",
            0,
        )
        > 0
    )


def get_runtime_evolution_summary(
    comparison: Dict[str, Any],
) -> str:
    """
    Generate a human-readable runtime evolution summary.
    """

    old_version = comparison.get(
        "old_version",
        "V1",
    )

    new_version = comparison.get(
        "new_version",
        "V2",
    )

    summary = comparison.get(
        "summary",
        {},
    )

    total_changes = summary.get(
        "total_behavioral_changes",
        0,
    )

    if total_changes == 0:
        return (
            f"No runtime architecture changes were observed "
            f"between {old_version} and {new_version} "
            f"for the selected execution scenario."
        )

    return (
        f"{total_changes} runtime architecture changes were "
        f"observed between {old_version} and {new_version}. "
        f"{summary.get('modules_added', 0)} modules were added, "
        f"{summary.get('modules_removed', 0)} modules were removed, "
        f"{summary.get('relationships_added', 0)} runtime "
        f"relationships were added, and "
        f"{summary.get('relationships_removed', 0)} runtime "
        f"relationships were removed."
    )