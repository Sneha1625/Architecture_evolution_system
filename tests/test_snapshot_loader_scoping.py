import sqlite3

from architecture_model.snapshot_loader import load_snapshot
from architecture_model.architecture_comparison import compare_snapshots


def _database(path):
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE architecture_snapshots (
            id INTEGER PRIMARY KEY, repository_id INTEGER, commit_hash TEXT,
            version TEXT, timestamp TEXT
        );
        CREATE TABLE components (
            id INTEGER PRIMARY KEY, snapshot_id INTEGER, name TEXT,
            component_type TEXT, component_key TEXT, responsibility TEXT, layer TEXT
        );
        CREATE TABLE component_files (
            id INTEGER PRIMARY KEY, component_id INTEGER, file_path TEXT
        );
        CREATE TABLE component_dependencies (
            id INTEGER PRIMARY KEY, component_id INTEGER,
            dependency_component_key TEXT
        );
        CREATE TABLE relationships (
            id INTEGER PRIMARY KEY, snapshot_id INTEGER, source TEXT,
            target TEXT, relationship_type TEXT
        );
        CREATE TABLE architecture_metrics (
            id INTEGER PRIMARY KEY, snapshot_id INTEGER, metric_name TEXT,
            metric_value REAL, metric_data TEXT
        );
        INSERT INTO architecture_snapshots VALUES
            (1, 1, 'commit-one', 'one', '2026-01-01'),
            (2, 1, 'commit-two', 'two', '2026-01-02');
        INSERT INTO components VALUES
            (1, 1, 'A', 'module', 'A', '', 'service'),
            (2, 1, 'B', 'module', 'B', '', 'data'),
            (3, 2, 'A', 'module', 'A', '', 'service'),
            (4, 2, 'C', 'module', 'C', '', 'api');
        INSERT INTO component_dependencies VALUES
            (1, 1, 'B'), (2, 3, 'C');
        INSERT INTO relationships VALUES
            (1, 1, 'A', 'B', 'depends_on'),
            (2, 2, 'A', 'C', 'depends_on');
    """)
    connection.commit()
    connection.close()


def test_snapshot_loader_scopes_components_and_relationships(tmp_path):
    database = tmp_path / "history.sqlite"
    _database(database)

    first = load_snapshot(1, database)
    second = load_snapshot(2, database)

    assert {component.id for component in first.components} == {"A", "B"}
    assert {component.id for component in second.components} == {"A", "C"}
    assert {(edge.source, edge.target) for edge in first.relationships} == {("A", "B")}
    assert {(edge.source, edge.target) for edge in second.relationships} == {("A", "C")}

    comparison = compare_snapshots(first, second)
    assert comparison["summary"]["components_added"] == 1
    assert comparison["summary"]["components_removed"] == 1
    assert comparison["summary"]["relationships_added"] == 1
    assert comparison["summary"]["relationships_removed"] == 1


def test_snapshot_loader_rebuilds_missing_edges_from_scoped_dependencies(tmp_path):
    database = tmp_path / "history.sqlite"
    _database(database)
    connection = sqlite3.connect(database)
    connection.execute("DELETE FROM relationships")
    connection.commit()
    connection.close()

    first = load_snapshot(1, database)
    second = load_snapshot(2, database)

    assert {(edge.source, edge.target, edge.type) for edge in first.relationships} == {
        ("A", "B", "depends_on")
    }
    assert {(edge.source, edge.target, edge.type) for edge in second.relationships} == {
        ("A", "C", "depends_on")
    }
