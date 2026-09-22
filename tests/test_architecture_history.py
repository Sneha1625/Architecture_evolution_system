"""
test_architecture_history.py
----------------------------

Tests the Persistent Architecture Digital Twin history pipeline.

Pipeline:

    ArchitectureSnapshot
            ↓
    SQLite Database
            ↓
    snapshot_loader.py
            ↓
    architecture_comparison.py
            ↓
    Architecture History
"""

import sys
from pathlib import Path
import tempfile
import sqlite3


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# IMPORTS
# ============================================================

from architecture_model.model import (
    Component,
    Relationship,
    ArchitectureSnapshot,
)

from architecture_model.snapshot_loader import (
    load_snapshot,
)

from architecture_model.architecture_comparison import (
    compare_snapshots,
)


# ============================================================
# CREATE TEST DATABASE
# ============================================================

def create_test_database(database_path):

    connection = sqlite3.connect(database_path)
    cursor = connection.cursor()

    # --------------------------------------------------------
    # Repository
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            source TEXT,
            url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --------------------------------------------------------
    # Snapshots
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE architecture_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repository_id INTEGER NOT NULL,
            commit_hash TEXT NOT NULL,
            version INTEGER,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --------------------------------------------------------
    # Components
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            component_key TEXT,
            name TEXT NOT NULL,
            responsibility TEXT,
            layer TEXT,
            component_type TEXT
        )
    """)

    # --------------------------------------------------------
    # Component Files
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE component_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component_id INTEGER NOT NULL,
            file_path TEXT NOT NULL
        )
    """)

    # --------------------------------------------------------
    # Component Dependencies
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE component_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component_id INTEGER NOT NULL,
            dependency_component_key TEXT NOT NULL
        )
    """)

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            relationship_type TEXT
        )
    """)

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE architecture_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL,
            metric_data TEXT
        )
    """)

    connection.commit()
    connection.close()


# ============================================================
# CREATE TEST REPOSITORY
# ============================================================

def create_test_repository(database_path):

    connection = sqlite3.connect(database_path)
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO repositories
        (name, source, url)
        VALUES (?, ?, ?)
        """,
        (
            "Test Architecture Repository",
            "test",
            None,
        ),
    )

    repository_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return repository_id


# ============================================================
# SAVE TEST SNAPSHOT
# ============================================================

def save_test_snapshot(
    database_path,
    repository_id,
    snapshot,
):

    connection = sqlite3.connect(database_path)
    cursor = connection.cursor()

    # --------------------------------------------------------
    # Snapshot
    # --------------------------------------------------------

    cursor.execute(
        """
        INSERT INTO architecture_snapshots
        (
            repository_id,
            commit_hash,
            version,
            timestamp
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            repository_id,
            snapshot.commit_hash,
            snapshot.version,
            snapshot.timestamp,
        ),
    )

    snapshot_id = cursor.lastrowid

    # --------------------------------------------------------
    # Components
    # --------------------------------------------------------

    for component in snapshot.components:

        cursor.execute(
            """
            INSERT INTO components
            (
                snapshot_id,
                component_key,
                name,
                responsibility,
                layer,
                component_type
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                component.id,
                component.name,
                component.responsibility,
                component.layer,
                "module",
            ),
        )

        component_id = cursor.lastrowid

        # ----------------------------------------------------
        # Files
        # ----------------------------------------------------

        for file_path in component.files:

            cursor.execute(
                """
                INSERT INTO component_files
                (
                    component_id,
                    file_path
                )
                VALUES (?, ?)
                """,
                (
                    component_id,
                    file_path,
                ),
            )

        # ----------------------------------------------------
        # Dependencies
        # ----------------------------------------------------

        for dependency in component.dependencies:

            cursor.execute(
                """
                INSERT INTO component_dependencies
                (
                    component_id,
                    dependency_component_key
                )
                VALUES (?, ?)
                """,
                (
                    component_id,
                    dependency,
                ),
            )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    for relationship in snapshot.relationships:

        cursor.execute(
            """
            INSERT INTO relationships
            (
                snapshot_id,
                source,
                target,
                relationship_type
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                snapshot_id,
                relationship.source,
                relationship.target,
                relationship.type,
            ),
        )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    for metric_name, metric_value in snapshot.metrics.items():

        if isinstance(metric_value, (int, float)):

            cursor.execute(
                """
                INSERT INTO architecture_metrics
                (
                    snapshot_id,
                    metric_name,
                    metric_value
                )
                VALUES (?, ?, ?)
                """,
                (
                    snapshot_id,
                    metric_name,
                    float(metric_value),
                ),
            )

        else:

            cursor.execute(
                """
                INSERT INTO architecture_metrics
                (
                    snapshot_id,
                    metric_name,
                    metric_data
                )
                VALUES (?, ?, ?)
                """,
                (
                    snapshot_id,
                    metric_name,
                    str(metric_value),
                ),
            )

    connection.commit()
    connection.close()

    return snapshot_id


# ============================================================
# VERSION 1
# ============================================================

def create_version_1():

    parser = Component(
        id="component_parser",
        name="Parser",
        responsibility="Parses source code",
        layer="core",
        files=["src/parser.py"],
        dependencies=[],
    )

    analyzer = Component(
        id="component_analyzer",
        name="Analyzer",
        responsibility="Analyzes parsed source code",
        layer="service",
        files=["src/analyzer.py"],
        dependencies=[
            "component_parser"
        ],
    )

    relationship = Relationship(
        source="component_analyzer",
        target="component_parser",
        type="depends_on",
    )

    return ArchitectureSnapshot(
        version="1",
        commit_hash="commit_v1",
        components=[
            parser,
            analyzer,
        ],
        relationships=[
            relationship,
        ],
        metrics={
            "total_components": 2,
            "total_relationships": 1,
            "total_files": 2,
        },
        violations=[],
    )


# ============================================================
# VERSION 2
# ============================================================

def create_version_2():

    analyzer = Component(
        id="component_analyzer",
        name="Analyzer",
        responsibility="Analyzes parsed source code",
        layer="service",
        files=["src/analyzer.py"],
        dependencies=[
            "component_database"
        ],
    )

    database = Component(
        id="component_database",
        name="Database",
        responsibility="Stores architecture information",
        layer="data",
        files=["src/database.py"],
        dependencies=[],
    )

    relationship = Relationship(
        source="component_analyzer",
        target="component_database",
        type="depends_on",
    )

    return ArchitectureSnapshot(
        version="2",
        commit_hash="commit_v2",
        components=[
            analyzer,
            database,
        ],
        relationships=[
            relationship,
        ],
        metrics={
            "total_components": 2,
            "total_relationships": 1,
            "total_files": 2,
        },
        violations=[],
    )


# ============================================================
# TEST 1
# ============================================================

def test_database_persistence():

    print("\nTEST 1: Database persistence")

    with tempfile.TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "test_architecture.db"
        )

        create_test_database(database_path)

        repository_id = create_test_repository(
            database_path
        )

        snapshot = create_version_1()

        snapshot_id = save_test_snapshot(
            database_path,
            repository_id,
            snapshot,
        )

        assert snapshot_id > 0

        connection = sqlite3.connect(
            database_path
        )

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM architecture_snapshots
            """
        )

        count = cursor.fetchone()[0]

        connection.close()

        assert count == 1

        print("✓ Snapshot successfully stored")


# ============================================================
# TEST 2
# ============================================================

def test_snapshot_loading():

    print("\nTEST 2: Snapshot loading")

    with tempfile.TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "test_architecture.db"
        )

        create_test_database(database_path)

        repository_id = create_test_repository(
            database_path
        )

        original_snapshot = create_version_1()

        snapshot_id = save_test_snapshot(
            database_path,
            repository_id,
            original_snapshot,
        )

        # IMPORTANT:
        # Pass database_path to loader.

        loaded_snapshot = load_snapshot(
            snapshot_id,
            database_path=database_path,
        )

        assert loaded_snapshot is not None

        assert (
            loaded_snapshot.commit_hash
            == "commit_v1"
        )

        assert len(
            loaded_snapshot.components
        ) == 2

        assert len(
            loaded_snapshot.relationships
        ) == 1

        print("✓ Snapshot successfully loaded")

        print(
            f"  Components: "
            f"{len(loaded_snapshot.components)}"
        )

        print(
            f"  Relationships: "
            f"{len(loaded_snapshot.relationships)}"
        )


# ============================================================
# TEST 3
# ============================================================

def test_architecture_comparison():

    print("\nTEST 3: Architecture comparison")

    with tempfile.TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "test_architecture.db"
        )

        create_test_database(database_path)

        repository_id = create_test_repository(
            database_path
        )

        # Version 1

        snapshot_v1 = create_version_1()

        snapshot_id_v1 = save_test_snapshot(
            database_path,
            repository_id,
            snapshot_v1,
        )

        # Version 2

        snapshot_v2 = create_version_2()

        snapshot_id_v2 = save_test_snapshot(
            database_path,
            repository_id,
            snapshot_v2,
        )

        # Load both snapshots

        loaded_v1 = load_snapshot(
            snapshot_id_v1,
            database_path=database_path,
        )

        loaded_v2 = load_snapshot(
            snapshot_id_v2,
            database_path=database_path,
        )

        assert loaded_v1 is not None
        assert loaded_v2 is not None

        # Compare

        comparison = compare_snapshots(
            loaded_v1,
            loaded_v2,
        )

        assert comparison is not None

        print(
            "✓ Snapshots successfully compared"
        )

        print("\nComparison result:")

        print(comparison)


# ============================================================
# TEST 4
# ============================================================

def test_complete_history_pipeline():

    print(
        "\nTEST 4: Complete architecture history pipeline"
    )

    with tempfile.TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "test_architecture.db"
        )

        create_test_database(database_path)

        repository_id = create_test_repository(
            database_path
        )

        # ----------------------------------------------------
        # Create history
        # ----------------------------------------------------

        snapshots = [
            create_version_1(),
            create_version_2(),
        ]

        snapshot_ids = []

        for snapshot in snapshots:

            snapshot_id = save_test_snapshot(
                database_path,
                repository_id,
                snapshot,
            )

            snapshot_ids.append(snapshot_id)

        # ----------------------------------------------------
        # Verify database
        # ----------------------------------------------------

        connection = sqlite3.connect(
            database_path
        )

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM architecture_snapshots
            """
        )

        count = cursor.fetchone()[0]

        connection.close()

        assert count == 2

        # ----------------------------------------------------
        # Load history
        # ----------------------------------------------------

        loaded_snapshots = []

        for snapshot_id in snapshot_ids:

            loaded = load_snapshot(
                snapshot_id,
                database_path=database_path,
            )

            assert loaded is not None

            loaded_snapshots.append(loaded)

        assert len(loaded_snapshots) == 2

        # ----------------------------------------------------
        # Compare versions
        # ----------------------------------------------------

        comparison = compare_snapshots(
            loaded_snapshots[0],
            loaded_snapshots[1],
        )

        assert comparison is not None

        print(
            "✓ Complete Digital Twin history "
            "pipeline works"
        )

        print("\nArchitecture evolution:")

        print(
            "  Version 1 → Version 2"
        )

        print(
            "  Commit:",
            loaded_snapshots[0].commit_hash,
            "→",
            loaded_snapshots[1].commit_hash,
        )

        print(
            "  Components:",
            len(loaded_snapshots[0].components),
            "→",
            len(loaded_snapshots[1].components),
        )

        print(
            "  Relationships:",
            len(loaded_snapshots[0].relationships),
            "→",
            len(loaded_snapshots[1].relationships),
        )

        print("\nComparison:")

        print(comparison)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("=" * 60)

    print(
        "ARCHITECTURE DIGITAL TWIN "
        "HISTORY TEST"
    )

    print("=" * 60)

    try:

        test_database_persistence()

        test_snapshot_loading()

        test_architecture_comparison()

        test_complete_history_pipeline()

        print("\n" + "=" * 60)

        print(
            "ALL TESTS PASSED ✓"
        )

        print("=" * 60)

    except Exception as error:

        print("\n" + "=" * 60)

        print(
            "TEST FAILED ✗"
        )

        print("=" * 60)

        print("\nError:")

        print(error)

        raise