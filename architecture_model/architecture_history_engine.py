"""
architecture_history_engine.py
------------------------------

High-level engine for analyzing architecture evolution.

Pipeline:

    Git History
         ↓
    Architecture Snapshots
         ↓
    Snapshot Comparison
         ↓
    Architecture Evolution
         ↓
    History Summary

This module connects:

    git_history.py
    snapshot_loader.py
    architecture_comparison.py
    history_manager.py

It provides a single high-level interface for obtaining
architecture evolution information.
"""

from typing import Any, Dict, List, Optional

from architecture_model.snapshot_loader import (
    load_snapshot,
    load_repository_snapshots,
)

from architecture_model.architecture_comparison import (
    compare_snapshots,
)


# ============================================================
# COMPARE TWO SNAPSHOTS
# ============================================================

def analyze_snapshot_evolution(
    old_snapshot_id: int,
    new_snapshot_id: int,
) -> Optional[Dict[str, Any]]:
    """
    Compare two architecture snapshots stored in the database.

    Parameters
    ----------
    old_snapshot_id : int
        ID of the older architecture snapshot.

    new_snapshot_id : int
        ID of the newer architecture snapshot.

    Returns
    -------
    dict | None
        Detailed architecture evolution information.

        Returns None if either snapshot does not exist.
    """

    old_snapshot = load_snapshot(
        old_snapshot_id
    )

    new_snapshot = load_snapshot(
        new_snapshot_id
    )

    if old_snapshot is None:
        return None

    if new_snapshot is None:
        return None

    return compare_snapshots(
        old_snapshot,
        new_snapshot,
    )


# ============================================================
# ANALYZE COMPLETE REPOSITORY HISTORY
# ============================================================

def analyze_repository_history(
    repository_id: int,
) -> List[Dict[str, Any]]:
    """
    Analyze architecture evolution across all snapshots
    belonging to a repository.

    Snapshots are processed chronologically.

    Example:

        V1 → V2 → V3 → V4

    Produces:

        V1 → V2
        V2 → V3
        V3 → V4

    Parameters
    ----------
    repository_id : int
        Repository ID.

    Returns
    -------
    list
        List of architecture evolution comparisons.
    """

    snapshots = load_repository_snapshots(
        repository_id
    )

    if len(snapshots) < 2:
        return []

    evolution = []

    for index in range(
        1,
        len(snapshots)
    ):

        old_snapshot = snapshots[
            index - 1
        ]

        new_snapshot = snapshots[
            index
        ]

        comparison = compare_snapshots(
            old_snapshot,
            new_snapshot,
        )

        if comparison is not None:

            evolution.append(
                comparison
            )

    return evolution


# ============================================================
# GET LATEST ARCHITECTURE CHANGE
# ============================================================

def get_latest_architecture_change(
    repository_id: int,
) -> Optional[Dict[str, Any]]:
    """
    Return the most recent architecture change
    for a repository.

    Example:

        V2 → V3

    If the repository contains only one snapshot,
    returns None.
    """

    evolution = analyze_repository_history(
        repository_id
    )

    if not evolution:
        return None

    return evolution[-1]


# ============================================================
# COUNT ARCHITECTURE CHANGES
# ============================================================

def count_architecture_changes(
    repository_id: int,
) -> int:
    """
    Count the number of architecture transitions
    recorded for a repository.

    Example:

        V1 → V2 → V3 → V4

    Number of transitions = 3
    """

    evolution = analyze_repository_history(
        repository_id
    )

    return len(evolution)


# ============================================================
# SUMMARIZE ARCHITECTURE EVOLUTION
# ============================================================

def summarize_architecture_evolution(
    repository_id: int,
) -> Dict[str, Any]:
    """
    Produce a high-level summary of architecture evolution.

    The summary aggregates changes across all recorded
    snapshot transitions.
    """

    evolution = analyze_repository_history(
        repository_id
    )

    summary = {
        "repository_id": repository_id,
        "total_transitions": len(evolution),
        "components_added": 0,
        "components_removed": 0,
        "components_modified": 0,
        "relationships_added": 0,
        "relationships_removed": 0,
        "metrics_changed": 0,
        "total_changes": 0,
    }

    for comparison in evolution:

        comparison_summary = comparison.get(
            "summary",
            {}
        )

        summary[
            "components_added"
        ] += comparison_summary.get(
            "components_added",
            0
        )

        summary[
            "components_removed"
        ] += comparison_summary.get(
            "components_removed",
            0
        )

        summary[
            "components_modified"
        ] += comparison_summary.get(
            "components_modified",
            0
        )

        summary[
            "relationships_added"
        ] += comparison_summary.get(
            "relationships_added",
            0
        )

        summary[
            "relationships_removed"
        ] += comparison_summary.get(
            "relationships_removed",
            0
        )

        summary[
            "metrics_changed"
        ] += comparison_summary.get(
            "metrics_changed",
            0
        )

        summary[
            "total_changes"
        ] += comparison_summary.get(
            "total_changes",
            0
        )

    return summary


# ============================================================
# BUILD ARCHITECTURE TIMELINE
# ============================================================

def build_architecture_timeline(
    repository_id: int,
) -> List[Dict[str, Any]]:
    """
    Build a chronological architecture timeline.

    Each entry represents one architecture snapshot.

    Example:

        [
            {
                "version": "1",
                "commit": "...",
                "components": 5,
                "relationships": 4
            },
            {
                "version": "2",
                "commit": "...",
                "components": 6,
                "relationships": 7
            }
        ]
    """

    snapshots = load_repository_snapshots(
        repository_id
    )

    timeline = []

    for snapshot in snapshots:

        timeline.append(
            {
                "version": snapshot.version,

                "commit_hash": (
                    snapshot.commit_hash
                ),

                "timestamp": (
                    getattr(
                        snapshot,
                        "timestamp",
                        ""
                    )
                ),

                "components": len(
                    snapshot.components
                ),

                "relationships": len(
                    snapshot.relationships
                ),

                "files": sum(
                    len(component.files)
                    for component in snapshot.components
                ),

                "metrics": dict(
                    snapshot.metrics
                ),
            }
        )

    return timeline


# ============================================================
# DETECT MAJOR ARCHITECTURE CHANGES
# ============================================================

def detect_major_changes(
    repository_id: int,
    threshold: int = 3,
) -> List[Dict[str, Any]]:
    """
    Detect architecture transitions containing a large number
    of changes.

    Parameters
    ----------
    repository_id : int
        Repository ID.

    threshold : int
        Minimum number of changes required for a transition
        to be considered major.

    Returns
    -------
    list
        Major architecture changes.
    """

    evolution = analyze_repository_history(
        repository_id
    )

    major_changes = []

    for comparison in evolution:

        summary = comparison.get(
            "summary",
            {}
        )

        total_changes = summary.get(
            "total_changes",
            0
        )

        if total_changes >= threshold:

            major_changes.append(
                comparison
            )

    return major_changes


# ============================================================
# GET COMPONENT EVOLUTION
# ============================================================

def get_component_evolution(
    repository_id: int,
    component_id: str,
) -> List[Dict[str, Any]]:
    """
    Track changes involving one component across
    architecture history.

    This is useful for the Architecture Digital Twin
    and future component-level history visualization.
    """

    evolution = analyze_repository_history(
        repository_id
    )

    component_history = []

    for comparison in evolution:

        components = comparison.get(
            "components",
            {}
        )

        # -----------------------------------------------
        # Added
        # -----------------------------------------------

        for component in components.get(
            "added",
            []
        ):

            if component.get(
                "id"
            ) == component_id:

                component_history.append(
                    {
                        "change": "added",
                        "version": comparison.get(
                            "new_version"
                        ),
                        "commit": comparison.get(
                            "new_commit"
                        ),
                        "component": component,
                    }
                )

        # -----------------------------------------------
        # Removed
        # -----------------------------------------------

        for component in components.get(
            "removed",
            []
        ):

            if component.get(
                "id"
            ) == component_id:

                component_history.append(
                    {
                        "change": "removed",
                        "version": comparison.get(
                            "new_version"
                        ),
                        "commit": comparison.get(
                            "new_commit"
                        ),
                        "component": component,
                    }
                )

        # -----------------------------------------------
        # Modified
        # -----------------------------------------------

        for component in components.get(
            "modified",
            []
        ):

            if component.get(
                "id"
            ) == component_id:

                component_history.append(
                    {
                        "change": "modified",
                        "version": comparison.get(
                            "new_version"
                        ),
                        "commit": comparison.get(
                            "new_commit"
                        ),
                        "component": component,
                    }
                )

    return component_history


# ============================================================
# ARCHITECTURE HEALTH TREND
# ============================================================

def get_architecture_size_trend(
    repository_id: int,
) -> List[Dict[str, Any]]:
    """
    Return the growth of the architecture over time.

    Tracks:

        components
        relationships
        files
    """

    timeline = build_architecture_timeline(
        repository_id
    )

    trend = []

    for entry in timeline:

        trend.append(
            {
                "version": entry[
                    "version"
                ],

                "commit_hash": entry[
                    "commit_hash"
                ],

                "components": entry[
                    "components"
                ],

                "relationships": entry[
                    "relationships"
                ],

                "files": entry[
                    "files"
                ],
            }
        )

    return trend


# ============================================================
# COMPLETE ARCHITECTURE HISTORY REPORT
# ============================================================

def generate_architecture_history_report(
    repository_id: int,
) -> Dict[str, Any]:
    """
    Generate one complete architecture history report.

    This function is intended to become the main backend
    interface for the future Architecture Time Machine UI.
    """

    timeline = build_architecture_timeline(
        repository_id
    )

    evolution = analyze_repository_history(
        repository_id
    )

    summary = summarize_architecture_evolution(
        repository_id
    )

    major_changes = detect_major_changes(
        repository_id
    )

    return {
        "repository_id": repository_id,

        "timeline": timeline,

        "evolution": evolution,

        "summary": summary,

        "major_changes": major_changes,

        "snapshot_count": len(
            timeline
        ),

        "transition_count": len(
            evolution
        ),
    }


# ============================================================
# MODULE TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print(
        "ARCHITECTURE HISTORY ENGINE"
    )
    print("=" * 60)

    print(
        "\nModule imported successfully."
    )

    print(
        "\nAvailable functions:"
    )

    functions = [
        "analyze_snapshot_evolution",
        "analyze_repository_history",
        "get_latest_architecture_change",
        "count_architecture_changes",
        "summarize_architecture_evolution",
        "build_architecture_timeline",
        "detect_major_changes",
        "get_component_evolution",
        "get_architecture_size_trend",
        "generate_architecture_history_report",
    ]

    for function in functions:

        print(
            f"  ✓ {function}"
        )

    print(
        "\nArchitecture History Engine "
        "ready ✓"
    )