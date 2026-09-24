from .db import get_connection


def create_tables():

    connection = get_connection()
    cursor = connection.cursor()

    # =========================================================
    # 1. REPOSITORIES
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repositories (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            source TEXT,

            url TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =========================================================
    # 2. ARCHITECTURE SNAPSHOTS
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS architecture_snapshots (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            repository_id INTEGER NOT NULL,

            commit_hash TEXT NOT NULL,

            version TEXT,

            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (repository_id)
                REFERENCES repositories(id)
        )
    """)

    # =========================================================
    # 3. COMPONENTS
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS components (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            snapshot_id INTEGER NOT NULL,

            component_key TEXT NOT NULL,

            name TEXT NOT NULL,

            responsibility TEXT,

            layer TEXT,

            component_type TEXT,

            FOREIGN KEY (snapshot_id)
                REFERENCES architecture_snapshots(id)
        )
    """)

    # =========================================================
    # 4. COMPONENT FILES
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS component_files (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            component_id INTEGER NOT NULL,

            file_path TEXT NOT NULL,

            FOREIGN KEY (component_id)
                REFERENCES components(id)
        )
    """)

    # =========================================================
    # 5. COMPONENT DEPENDENCIES
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS component_dependencies (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            component_id INTEGER NOT NULL,

            dependency_component_key TEXT NOT NULL,

            FOREIGN KEY (component_id)
                REFERENCES components(id)
        )
    """)

    # =========================================================
    # 6. ARCHITECTURE RELATIONSHIPS
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relationships (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            snapshot_id INTEGER NOT NULL,

            source TEXT NOT NULL,

            target TEXT NOT NULL,

            relationship_type TEXT,

            FOREIGN KEY (snapshot_id)
                REFERENCES architecture_snapshots(id)
        )
    """)

    # =========================================================
    # 7. ARCHITECTURE METRICS
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS architecture_metrics (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            snapshot_id INTEGER NOT NULL,

            metric_name TEXT NOT NULL,

            metric_value REAL,

            metric_data TEXT,

            FOREIGN KEY (snapshot_id)
                REFERENCES architecture_snapshots(id)
        )
    """)

    # =========================================================
    # 8. ARCHITECTURE VIOLATIONS
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS architecture_violations (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            snapshot_id INTEGER NOT NULL,

            violation_type TEXT,

            component TEXT,

            severity TEXT,

            description TEXT,

            evidence TEXT,

            FOREIGN KEY (snapshot_id)
                REFERENCES architecture_snapshots(id)
        )
    """)


    # =========================================================
    # 9. RUNTIME EXECUTIONS
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runtime_executions (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            repository_id INTEGER NOT NULL,

            snapshot_id INTEGER,

            version TEXT,

            commit_hash TEXT,

            scenario TEXT,

            entry_point TEXT,

            total_calls INTEGER DEFAULT 0,

            module_count INTEGER DEFAULT 0,

            relationship_count INTEGER DEFAULT 0,

            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (repository_id)
                REFERENCES repositories(id),

            FOREIGN KEY (snapshot_id)
                REFERENCES architecture_snapshots(id)
        )
    """)

    # =========================================================
    # 10. RUNTIME RELATIONSHIPS
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runtime_relationships (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            execution_id INTEGER NOT NULL,

            source TEXT NOT NULL,

            target TEXT NOT NULL,

            call_count INTEGER DEFAULT 0,

            functions TEXT,

            FOREIGN KEY (execution_id)
                REFERENCES runtime_executions(id)
        )
    """)

    connection.commit()
    connection.close()



if __name__ == "__main__":

    create_tables()

    print("Database tables created successfully!")