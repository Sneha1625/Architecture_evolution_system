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

from architecture_model.history_manager import (
    create_architecture_snapshot,
    get_architecture_snapshot,
    get_architecture_history,
    get_latest_architecture,
    get_previous_architecture,
    compare_architecture_history,
    compare_with_previous_version,
    get_architecture_evolution,
    build_history_summary,
    has_architecture_history,
    has_architecture_evolution,
)


# ============================================================
# TEST IMPORTS ONLY
# ============================================================

def test_history_manager_imports():

    print("=" * 60)
    print("HISTORY MANAGER TEST")
    print("=" * 60)

    print("\n✓ history_manager imported successfully")

    print("\nAvailable functions:")

    functions = [
        create_architecture_snapshot,
        get_architecture_snapshot,
        get_architecture_history,
        get_latest_architecture,
        get_previous_architecture,
        compare_architecture_history,
        compare_with_previous_version,
        get_architecture_evolution,
        build_history_summary,
        has_architecture_history,
        has_architecture_evolution,
    ]

    for function in functions:
        print(f"  ✓ {function.__name__}")

    print("\n" + "=" * 60)
    print("HISTORY MANAGER IMPORT TEST PASSED ✓")
    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        test_history_manager_imports()

    except Exception as error:

        print("\n" + "=" * 60)
        print("TEST FAILED ✗")
        print("=" * 60)

        print("\nError:")
        print(error)

        raise