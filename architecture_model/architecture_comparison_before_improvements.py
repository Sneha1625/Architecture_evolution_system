"""
architecture_comparison.py
--------------------------

Architecture Snapshot Comparison Engine.

This module compares two ArchitectureSnapshot objects and
identifies structural and metric changes between them.

It does NOT use AI.

The comparison is deterministic and evidence-based.

Main capabilities:
    1. Added components
    2. Removed components
    3. Modified components
    4. Added relationships
    5. Removed relationships
    6. Changed dependencies
    7. Changed metrics
    8. Overall architecture change summary
"""

from typing import Dict, List, Any


# ============================================================
# COMPONENT HELPERS
# ============================================================

def _component_map(snapshot):
    """
    Create a dictionary:

        component_id -> Component

    This makes component comparison efficient.
    """

    return {
        component.id: component
        for component in snapshot.components
    }


def _component_signature(component):
    """
    Return the important architectural information
    used to determine whether a component changed.
    """

    return {
        "name": component.name,
        "responsibility": component.responsibility,
        "layer": component.layer,
        "files": sorted(component.files),
        "dependencies": sorted(component.dependencies),
    }


# ============================================================
# RELATIONSHIP HELPERS
# ============================================================

def _relationship_set(snapshot):
    """
    Convert relationships into a set so that added and
    removed relationships can easily be detected.
    """

    return {
        (
            relationship.source,
            relationship.target,
            relationship.type,
        )
        for relationship in snapshot.relationships
    }


# ============================================================
# COMPONENT COMPARISON
# ============================================================

def find_added_components(old_snapshot, new_snapshot):
    """
    Find components that exist in the new architecture
    but did not exist in the old architecture.
    """

    old_components = _component_map(old_snapshot)
    new_components = _component_map(new_snapshot)

    added_ids = set(new_components) - set(old_components)

    return [
        {
            "id": component_id,
            "name": new_components[component_id].name,
            "layer": new_components[component_id].layer,
            "files": list(new_components[component_id].files),
        }
        for component_id in sorted(added_ids)
    ]


def find_removed_components(old_snapshot, new_snapshot):
    """
    Find components that existed in the old architecture
    but no longer exist in the new architecture.
    """

    old_components = _component_map(old_snapshot)
    new_components = _component_map(new_snapshot)

    removed_ids = set(old_components) - set(new_components)

    return [
        {
            "id": component_id,
            "name": old_components[component_id].name,
            "layer": old_components[component_id].layer,
            "files": list(old_components[component_id].files),
        }
        for component_id in sorted(removed_ids)
    ]


def find_modified_components(old_snapshot, new_snapshot):
    """
    Find components that exist in both snapshots but whose
    architectural information has changed.
    """

    old_components = _component_map(old_snapshot)
    new_components = _component_map(new_snapshot)

    common_ids = (
        set(old_components)
        & set(new_components)
    )

    modified = []

    for component_id in sorted(common_ids):

        old_component = old_components[component_id]
        new_component = new_components[component_id]

        old_signature = _component_signature(
            old_component
        )

        new_signature = _component_signature(
            new_component
        )

        if old_signature != new_signature:

            changes = {}

            # ---------------------------------------------
            # Responsibility
            # ---------------------------------------------

            if (
                old_component.responsibility
                != new_component.responsibility
            ):
                changes["responsibility"] = {
                    "old": old_component.responsibility,
                    "new": new_component.responsibility,
                }

            # ---------------------------------------------
            # Layer
            # ---------------------------------------------

            if (
                old_component.layer
                != new_component.layer
            ):
                changes["layer"] = {
                    "old": old_component.layer,
                    "new": new_component.layer,
                }

            # ---------------------------------------------
            # Files
            # ---------------------------------------------

            old_files = set(
                old_component.files
            )

            new_files = set(
                new_component.files
            )

            added_files = sorted(
                new_files - old_files
            )

            removed_files = sorted(
                old_files - new_files
            )

            if added_files or removed_files:

                changes["files"] = {
                    "added": added_files,
                    "removed": removed_files,
                }

            # ---------------------------------------------
            # Dependencies
            # ---------------------------------------------

            old_dependencies = set(
                old_component.dependencies
            )

            new_dependencies = set(
                new_component.dependencies
            )

            added_dependencies = sorted(
                new_dependencies - old_dependencies
            )

            removed_dependencies = sorted(
                old_dependencies - new_dependencies
            )

            if (
                added_dependencies
                or removed_dependencies
            ):

                changes["dependencies"] = {
                    "added": added_dependencies,
                    "removed": removed_dependencies,
                }

            modified.append(
                {
                    "id": component_id,
                    "name": new_component.name,
                    "changes": changes,
                }
            )

    return modified


# ============================================================
# RELATIONSHIP COMPARISON
# ============================================================

def find_added_relationships(
    old_snapshot,
    new_snapshot
):
    """
    Find relationships that were introduced
    in the new architecture.
    """

    old_relationships = _relationship_set(
        old_snapshot
    )

    new_relationships = _relationship_set(
        new_snapshot
    )

    added = new_relationships - old_relationships

    return [
        {
            "source": source,
            "target": target,
            "type": relationship_type,
        }
        for source, target, relationship_type
        in sorted(added)
    ]


def find_removed_relationships(
    old_snapshot,
    new_snapshot
):
    """
    Find relationships that existed previously
    but disappeared from the new architecture.
    """

    old_relationships = _relationship_set(
        old_snapshot
    )

    new_relationships = _relationship_set(
        new_snapshot
    )

    removed = old_relationships - new_relationships

    return [
        {
            "source": source,
            "target": target,
            "type": relationship_type,
        }
        for source, target, relationship_type
        in sorted(removed)
    ]


# ============================================================
# METRIC COMPARISON
# ============================================================

def compare_metrics(
    old_snapshot,
    new_snapshot
):
    """
    Compare architecture metrics stored inside
    both snapshots.
    """

    old_metrics = old_snapshot.metrics or {}
    new_metrics = new_snapshot.metrics or {}

    metric_names = (
        set(old_metrics)
        | set(new_metrics)
    )

    changes = []

    for metric_name in sorted(metric_names):

        old_value = old_metrics.get(
            metric_name
        )

        new_value = new_metrics.get(
            metric_name
        )

        if old_value == new_value:
            continue

        change = None

        # Numeric difference
        if (
            isinstance(old_value, (int, float))
            and isinstance(new_value, (int, float))
        ):
            change = new_value - old_value

        changes.append(
            {
                "metric": metric_name,
                "old": old_value,
                "new": new_value,
                "change": change,
            }
        )

    return changes


# ============================================================
# ARCHITECTURE SIZE COMPARISON
# ============================================================

def compare_architecture_size(
    old_snapshot,
    new_snapshot
):
    """
    Compare basic architecture size between versions.
    """

    old_components = len(
        old_snapshot.components
    )

    new_components = len(
        new_snapshot.components
    )

    old_relationships = len(
        old_snapshot.relationships
    )

    new_relationships = len(
        new_snapshot.relationships
    )

    return {
        "components": {
            "old": old_components,
            "new": new_components,
            "change": (
                new_components
                - old_components
            ),
        },

        "relationships": {
            "old": old_relationships,
            "new": new_relationships,
            "change": (
                new_relationships
                - old_relationships
            ),
        },
    }


# ============================================================
# COMPLETE SNAPSHOT COMPARISON
# ============================================================

def compare_snapshots(
    old_snapshot,
    new_snapshot
) -> Dict[str, Any]:
    """
    Compare two complete architecture snapshots.

    Returns one machine-readable architecture
    evolution report.
    """

    added_components = find_added_components(
        old_snapshot,
        new_snapshot
    )

    removed_components = find_removed_components(
        old_snapshot,
        new_snapshot
    )

    modified_components = find_modified_components(
        old_snapshot,
        new_snapshot
    )

    added_relationships = find_added_relationships(
        old_snapshot,
        new_snapshot
    )

    removed_relationships = find_removed_relationships(
        old_snapshot,
        new_snapshot
    )

    metric_changes = compare_metrics(
        old_snapshot,
        new_snapshot
    )

    architecture_size = compare_architecture_size(
        old_snapshot,
        new_snapshot
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_changes = (
        len(added_components)
        + len(removed_components)
        + len(modified_components)
        + len(added_relationships)
        + len(removed_relationships)
        + len(metric_changes)
    )

    return {
        "old_version": old_snapshot.version,
        "new_version": new_snapshot.version,

        "old_commit": old_snapshot.commit_hash,
        "new_commit": new_snapshot.commit_hash,

        "summary": {
            "total_changes": total_changes,

            "components_added":
                len(added_components),

            "components_removed":
                len(removed_components),

            "components_modified":
                len(modified_components),

            "relationships_added":
                len(added_relationships),

            "relationships_removed":
                len(removed_relationships),

            "metrics_changed":
                len(metric_changes),
        },

        "components": {
            "added": added_components,
            "removed": removed_components,
            "modified": modified_components,
        },

        "relationships": {
            "added": added_relationships,
            "removed": removed_relationships,
        },

        "metrics": metric_changes,

        "architecture_size":
            architecture_size,
    }


# ============================================================
# HUMAN-READABLE SUMMARY
# ============================================================

def generate_comparison_summary(
    comparison: Dict[str, Any]
) -> str:
    """
    Convert the machine-readable comparison result
    into a simple human-readable report.
    """

    summary = comparison["summary"]

    lines = []

    lines.append(
        "ARCHITECTURE COMPARISON"
    )

    lines.append(
        "-" * 40
    )

    lines.append(
        f"Old version: {comparison['old_version']}"
    )

    lines.append(
        f"New version: {comparison['new_version']}"
    )

    lines.append("")

    # --------------------------------------------------------
    # Components
    # --------------------------------------------------------

    lines.append(
        f"Components added: "
        f"{summary['components_added']}"
    )

    lines.append(
        f"Components removed: "
        f"{summary['components_removed']}"
    )

    lines.append(
        f"Components modified: "
        f"{summary['components_modified']}"
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    lines.append(
        f"Relationships added: "
        f"{summary['relationships_added']}"
    )

    lines.append(
        f"Relationships removed: "
        f"{summary['relationships_removed']}"
    )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    lines.append(
        f"Metrics changed: "
        f"{summary['metrics_changed']}"
    )

    lines.append("")

    # --------------------------------------------------------
    # Added components
    # --------------------------------------------------------

    if comparison["components"]["added"]:

        lines.append("ADDED COMPONENTS")

        for component in (
            comparison["components"]["added"]
        ):

            lines.append(
                f"+ {component['name']}"
            )

    # --------------------------------------------------------
    # Removed components
    # --------------------------------------------------------

    if comparison["components"]["removed"]:

        lines.append("")

        lines.append("REMOVED COMPONENTS")

        for component in (
            comparison["components"]["removed"]
        ):

            lines.append(
                f"- {component['name']}"
            )

    # --------------------------------------------------------
    # Modified components
    # --------------------------------------------------------

    if comparison["components"]["modified"]:

        lines.append("")

        lines.append("MODIFIED COMPONENTS")

        for component in (
            comparison["components"]["modified"]
        ):

            lines.append(
                f"* {component['name']}"
            )

            for change_name in component[
                "changes"
            ]:

                lines.append(
                    f"    changed: {change_name}"
                )

    # --------------------------------------------------------
    # Added relationships
    # --------------------------------------------------------

    if comparison["relationships"]["added"]:

        lines.append("")

        lines.append("NEW RELATIONSHIPS")

        for relationship in (
            comparison["relationships"]["added"]
        ):

            lines.append(
                f"+ {relationship['source']} "
                f"-> {relationship['target']} "
                f"({relationship['type']})"
            )

    # --------------------------------------------------------
    # Removed relationships
    # --------------------------------------------------------

    if comparison["relationships"]["removed"]:

        lines.append("")

        lines.append("REMOVED RELATIONSHIPS")

        for relationship in (
            comparison["relationships"]["removed"]
        ):

            lines.append(
                f"- {relationship['source']} "
                f"-> {relationship['target']} "
                f"({relationship['type']})"
            )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    if comparison["metrics"]:

        lines.append("")

        lines.append("METRIC CHANGES")

        for metric in comparison["metrics"]:

            lines.append(
                f"* {metric['metric']}: "
                f"{metric['old']} -> "
                f"{metric['new']}"
            )

    # --------------------------------------------------------
    # No changes
    # --------------------------------------------------------

    if summary["total_changes"] == 0:

        lines.append("")

        lines.append(
            "No architectural changes detected."
        )

    return "\n".join(lines)