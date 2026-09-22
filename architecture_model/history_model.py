"""
history_manager.py
------------------

Integration layer for the Persistent Architecture Digital Twin.

Responsibilities:

    Parsed Source Code
            ↓
    Architecture Recovery
            ↓
    ArchitectureSnapshot
            ↓
    SQLite Persistence
            ↓
    Architecture History

This module connects the existing:

    - architecture recovery
    - snapshot model
    - snapshot persistence
    - snapshot loading
    - architecture comparison

without modifying the existing analysis modules.
"""

from typing import Any, Dict, List, Optional

from architecture_model.model import ArchitectureSnapshot

from architecture_model.architecture_recovery import (
    recover_architecture,
)

from architecture_model.snapshot_loader import (
    load_snapshot,
    load_repository_snapshots,
    load_latest_snapshot,
    load_previous_snapshot,
)

# ------------------------------------------------------------
# IMPORTANT
# ------------------------------------------------------------
#
# Your existing save_architecture_snapshot() function may be
# located in a different module.
#
# The import below assumes that the persistence function is
# inside:
#
#     database/snapshot_repository.py
#
# If your function is located somewhere else, change ONLY
# this import.
#
# ------------------------------------------------------------

from database.snapshot_repository import (
    save_architecture_snapshot,
)

from architecture_model.architecture_comparison import (
    compare_snapshots,
)


# ============================================================
# 1. CREATE SNAPSHOT
# ============================================================

def create_architecture_snapshot(
    parsed_results: List[Dict[str, Any]],
    commit_hash: str = "unknown",
) -> ArchitectureSnapshot:
    """
    Recover the architecture from parsed source-code results.

    Parameters
    ----------
    parsed_results:
        Output produced by the existing source-code parser.

    commit_hash:
        Git commit associated with this architecture version.

    Returns
    -------
    ArchitectureSnapshot
        Recovered architecture snapshot.
    """

    snapshot = recover_architecture(
        parsed_results=parsed_results,
        commit_hash=commit_hash,
    )

    return snapshot


# ============================================================
# 2. SAVE SNAPSHOT
# ============================================================

def save_architecture_history(
    repository_id: int,
    parsed_results: List[Dict[str, Any]],
    commit_hash: str = "unknown",
) -> int:
    """
    Recover and persist one architecture snapshot.

    Pipeline:

        parsed_results
              ↓
        recover_architecture()
              ↓
        ArchitectureSnapshot
              ↓
        save_architecture_snapshot()
              ↓
        SQLite

    Returns
    -------
    int
        Database snapshot ID.
    """

    snapshot = create_architecture_snapshot(
        parsed_results=parsed_results,
        commit_hash=commit_hash,
    )

    snapshot_id = save_architecture_snapshot(
        repository_id,
        snapshot,
    )

    return snapshot_id


# ============================================================
# 3. GET SNAPSHOT
# ============================================================

def get_architecture_snapshot(
    snapshot_id: int,
) -> Optional[ArchitectureSnapshot]:
    """
    Load one architecture snapshot from the database.
    """

    return load_snapshot(
        snapshot_id
    )


# ============================================================
# 4. GET COMPLETE HISTORY
# ============================================================

def get_architecture_history(
    repository_id: int,
) -> List[ArchitectureSnapshot]:
    """
    Load all architecture snapshots for a repository.

    Snapshots are returned in chronological order.
    """

    return load_repository_snapshots(
        repository_id
    )


# ============================================================
# 5. GET LATEST SNAPSHOT
# ============================================================

def get_latest_architecture(
    repository_id: int,
) -> Optional[ArchitectureSnapshot]:
    """
    Return the most recent architecture snapshot.
    """

    return load_latest_snapshot(
        repository_id
    )


# ============================================================
# 6. GET PREVIOUS SNAPSHOT
# ============================================================

def get_previous_architecture(
    repository_id: int,
    current_snapshot_id: int,
) -> Optional[ArchitectureSnapshot]:
    """
    Return the architecture snapshot immediately before
    the specified snapshot.
    """

    return load_previous_snapshot(
        repository_id,
        current_snapshot_id,
    )


# ============================================================
# 7. COMPARE TWO SNAPSHOTS
# ============================================================

def compare_architecture_history(
    old_snapshot_id: int,
    new_snapshot_id: int,
) -> Optional[Dict[str, Any]]:
    """
    Compare two persisted architecture snapshots.

    Pipeline:

        Database
            ↓
        load old snapshot
            ↓
        load new snapshot
            ↓
        compare_snapshots()
            ↓
        architecture evolution result
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

    comparison = compare_snapshots(
        old_snapshot,
        new_snapshot,
    )

    return comparison


# ============================================================
# 8. COMPARE WITH PREVIOUS VERSION
# ============================================================

def compare_with_previous_version(
    repository_id: int,
    current_snapshot_id: int,
) -> Optional[Dict[str, Any]]:
    """
    Compare a snapshot with the immediately previous
    architecture version.

    This is useful for automatic Architecture Time Machine
    analysis.
    """

    current_snapshot = load_snapshot(
        current_snapshot_id
    )

    if current_snapshot is None:
        return None

    previous_snapshot = load_previous_snapshot(
        repository_id,
        current_snapshot_id,
    )

    if previous_snapshot is None:
        return None

    return compare_snapshots(
        previous_snapshot,
        current_snapshot,
    )


# ============================================================
# 9. GET ARCHITECTURE EVOLUTION
# ============================================================

def get_architecture_evolution(
    repository_id: int,
) -> List[Dict[str, Any]]:
    """
    Compare every consecutive architecture snapshot.

    Example:

        Version 1 → Version 2
        Version 2 → Version 3
        Version 3 → Version 4

    Returns
    -------
    List[Dict[str, Any]]
        One comparison object for every consecutive pair.
    """

    snapshots = load_repository_snapshots(
        repository_id
    )

    evolution = []

    if len(snapshots) < 2:
        return evolution

    for index in range(
        1,
        len(snapshots),
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

        evolution.append(
            comparison
        )

    return evolution


# ============================================================
# 10. BUILD HISTORY SUMMARY
# ============================================================

def build_history_summary(
    repository_id: int,
) -> Dict[str, Any]:
    """
    Build a compact summary of architecture history.

    This is intended for:

        - Streamlit UI
        - reports
        - Architecture Time Machine
        - future RAG
        - architecture governance
    """

    snapshots = load_repository_snapshots(
        repository_id
    )

    if not snapshots:

        return {
            "repository_id": repository_id,
            "total_snapshots": 0,
            "first_version": None,
            "latest_version": None,
            "first_commit": None,
            "latest_commit": None,
            "total_evolution_steps": 0,
        }

    first_snapshot = snapshots[0]

    latest_snapshot = snapshots[-1]

    return {
        "repository_id": repository_id,

        "total_snapshots": len(
            snapshots
        ),

        "first_version": (
            first_snapshot.version
        ),

        "latest_version": (
            latest_snapshot.version
        ),

        "first_commit": (
            first_snapshot.commit_hash
        ),

        "latest_commit": (
            latest_snapshot.commit_hash
        ),

        "total_evolution_steps": max(
            0,
            len(snapshots) - 1,
        ),
    }


# ============================================================
# 11. GET LATEST EVOLUTION CHANGE
# ============================================================

def get_latest_architecture_change(
    repository_id: int,
) -> Optional[Dict[str, Any]]:
    """
    Compare the latest architecture snapshot with
    the previous version.

    Returns None when there is only one snapshot.
    """

    snapshots = load_repository_snapshots(
        repository_id
    )

    if len(snapshots) < 2:
        return None

    previous_snapshot = snapshots[
        -2
    ]

    latest_snapshot = snapshots[
        -1
    ]

    return compare_snapshots(
        previous_snapshot,
        latest_snapshot,
    )


# ============================================================
# 12. CHECK WHETHER HISTORY EXISTS
# ============================================================

def has_architecture_history(
    repository_id: int,
) -> bool:
    """
    Return True when the repository has at least
    one architecture snapshot.
    """

    snapshots = load_repository_snapshots(
        repository_id
    )

    return len(snapshots) > 0


# ============================================================
# 13. CHECK WHETHER EVOLUTION EXISTS
# ============================================================

def has_architecture_evolution(
    repository_id: int,
) -> bool:
    """
    Return True when at least two architecture snapshots
    exist and therefore an evolution comparison is possible.
    """

    snapshots = load_repository_snapshots(
        repository_id
    )

    return len(snapshots) >= 2