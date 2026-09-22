import sys
from pathlib import Path


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# IMPORT
# ============================================================

from architecture_model.history_manager import (
    create_architecture_snapshot,
)


# ============================================================
# TEST
# ============================================================

def test_real_architecture_recovery():

    print("=" * 60)
    print("REAL ARCHITECTURE RECOVERY TEST")
    print("=" * 60)

    # --------------------------------------------------------
    # Small artificial parsed-result input
    # --------------------------------------------------------

    parsed_results = [

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

        {
            "file": "src/database.py",
            "imports": [],
        },

    ]

    # --------------------------------------------------------
    # Create architecture snapshot
    # --------------------------------------------------------

    snapshot = create_architecture_snapshot(
        parsed_results=parsed_results,
        commit_hash="test_commit_001",
    )

    # --------------------------------------------------------
    # Verify snapshot
    # --------------------------------------------------------

    assert snapshot is not None

    assert snapshot.commit_hash == "test_commit_001"

    assert len(snapshot.components) == 3

    assert len(snapshot.relationships) == 1

    # --------------------------------------------------------
    # Print architecture
    # --------------------------------------------------------

    print("\n✓ Architecture snapshot created")

    print(
        "\nCommit:",
        snapshot.commit_hash
    )

    print(
        "Version:",
        snapshot.version
    )

    print(
        "Components:",
        len(snapshot.components)
    )

    print(
        "Relationships:",
        len(snapshot.relationships)
    )

    print("\nComponents:")

    for component in snapshot.components:

        print(
            f"  - {component.name}"
            f" | layer={component.layer}"
            f" | files={component.files}"
        )

    print("\nRelationships:")

    for relationship in snapshot.relationships:

        print(
            f"  - {relationship.source}"
            f" → {relationship.target}"
            f" ({relationship.type})"
        )

    print("\n" + "=" * 60)
    print("REAL ARCHITECTURE RECOVERY TEST PASSED ✓")
    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        test_real_architecture_recovery()

    except Exception as error:

        print("\n" + "=" * 60)
        print("TEST FAILED ✗")
        print("=" * 60)

        print("\nError:")
        print(error)

        raise