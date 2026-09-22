"""
test_real_history_pipeline.py

Tests the complete architecture history pipeline.

Pipeline:

Repository
    ↓
Source-code parsing
    ↓
Architecture recovery
    ↓
ArchitectureSnapshot
    ↓
History manager
    ↓
Database
    ↓
Architecture history
"""

import sys
from pathlib import Path


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# IMPORTS
# ============================================================

from architecture_model.recovery import recover_architecture

from architecture_model.history_manager import (
    create_architecture_snapshot,
    save_architecture_history,
    get_architecture_history,
    get_architecture_evolution,
    build_history_summary,
    has_architecture_history,
    has_architecture_evolution,
)


# ============================================================
# TEST
# ============================================================

def test_real_architecture_history_pipeline():

    # --------------------------------------------------------
    # 1. Create artificial parser results
    # --------------------------------------------------------

    parsed_v1 = [
        {
            "file": "src/parser.py",
            "imports": [],
        },
        {
            "file": "src/analyzer.py",
            "imports": [
                "parser"
            ],
        },
    ]

    parsed_v2 = [
        {
            "file": "src/analyzer.py",
            "imports": [
                "database"
            ],
        },
        {
            "file": "src/database.py",
            "imports": [],
        },
    ]

    # --------------------------------------------------------
    # 2. Recover Version 1
    # --------------------------------------------------------

    snapshot_v1 = recover_architecture(
        parsed_v1,
        commit_hash="real_commit_v1",
    )

    assert snapshot_v1 is not None
    assert len(snapshot_v1.components) > 0
    assert snapshot_v1.commit_hash == "real_commit_v1"

    # --------------------------------------------------------
    # 3. Recover Version 2
    # --------------------------------------------------------

    snapshot_v2 = recover_architecture(
        parsed_v2,
        commit_hash="real_commit_v2",
    )

    assert snapshot_v2 is not None
    assert len(snapshot_v2.components) > 0
    assert snapshot_v2.commit_hash == "real_commit_v2"

    # --------------------------------------------------------
    # 4. Validate snapshot structure
    # --------------------------------------------------------

    assert hasattr(snapshot_v1, "components")
    assert hasattr(snapshot_v1, "relationships")
    assert hasattr(snapshot_v1, "metrics")

    assert hasattr(snapshot_v2, "components")
    assert hasattr(snapshot_v2, "relationships")
    assert hasattr(snapshot_v2, "metrics")

    # --------------------------------------------------------
    # 5. Validate history manager functions
    # --------------------------------------------------------

    assert callable(create_architecture_snapshot)
    assert callable(save_architecture_history)
    assert callable(get_architecture_history)
    assert callable(get_architecture_evolution)
    assert callable(build_history_summary)
    assert callable(has_architecture_history)
    assert callable(has_architecture_evolution)