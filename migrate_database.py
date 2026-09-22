import sqlite3
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "architecture.db"


# ============================================================
# DATABASE MIGRATION
# ============================================================

def column_exists(connection, table_name, column_name):

    columns = connection.execute(
        f"PRAGMA table_info([{table_name}])"
    ).fetchall()

    return any(
        column[1] == column_name
        for column in columns
    )


def table_exists(connection, table_name):

    result = connection.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table'
        AND name = ?
        """,
        (table_name,),
    ).fetchone()[0]

    return result > 0


def add_column_if_missing(
    connection,
    table_name,
    column_name,
    column_definition,
):

    if not column_exists(
        connection,
        table_name,
        column_name,
    ):

        print(
            f"Adding column: "
            f"{table_name}.{column_name}"
        )

        connection.execute(
            f"""
            ALTER TABLE [{table_name}]
            ADD COLUMN [{column_name}]
            {column_definition}
            """
        )

    else:

        print(
            f"Already exists: "
            f"{table_name}.{column_name}"
        )


def migrate():

    print("=" * 60)
    print("ARCHITECTURE DATABASE MIGRATION")
    print("=" * 60)

    print()
    print("Database:")
    print(DATABASE_PATH)

    if not DATABASE_PATH.exists():

        print()
        print("ERROR: Database does not exist.")

        return False

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    try:

        # ====================================================
        # VERIFY DATABASE
        # ====================================================

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        print()
        print(
            "Integrity check:",
            integrity,
        )

        if integrity != "ok":

            print(
                "ERROR: Database integrity check failed."
            )

            connection.rollback()

            return False

        # ====================================================
        # VERIFY REQUIRED OLD TABLES
        # ====================================================

        required_tables = [
            "repositories",
            "architecture_snapshots",
            "components",
            "relationships",
        ]

        print()
        print("Checking required tables...")

        for table in required_tables:

            if not table_exists(
                connection,
                table,
            ):

                print(
                    f"ERROR: Missing table: {table}"
                )

                connection.rollback()

                return False

            print(
                f"OK: {table}"
            )

        # ====================================================
        # COMPONENTS
        # ====================================================

        print()
        print("-" * 60)
        print("UPGRADING COMPONENTS")
        print("-" * 60)

        add_column_if_missing(
            connection,
            "components",
            "component_key",
            "TEXT",
        )

        add_column_if_missing(
            connection,
            "components",
            "responsibility",
            "TEXT",
        )

        add_column_if_missing(
            connection,
            "components",
            "layer",
            "TEXT",
        )

        # ====================================================
        # COMPONENT FILES
        # ====================================================

        print()
        print("-" * 60)
        print("CREATING COMPONENT FILES")
        print("-" * 60)

        if not table_exists(
            connection,
            "component_files",
        ):

            connection.execute(
                """
                CREATE TABLE component_files
                (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    component_id INTEGER NOT NULL,

                    file_path TEXT NOT NULL,

                    FOREIGN KEY(component_id)
                        REFERENCES components(id)
                )
                """
            )

            print(
                "Created: component_files"
            )

        else:

            print(
                "Already exists: component_files"
            )

        # ====================================================
        # COMPONENT DEPENDENCIES
        # ====================================================

        print()
        print("-" * 60)
        print("CREATING COMPONENT DEPENDENCIES")
        print("-" * 60)

        if not table_exists(
            connection,
            "component_dependencies",
        ):

            connection.execute(
                """
                CREATE TABLE component_dependencies
                (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    component_id INTEGER NOT NULL,

                    dependency_component_key TEXT NOT NULL,

                    FOREIGN KEY(component_id)
                        REFERENCES components(id)
                )
                """
            )

            print(
                "Created: component_dependencies"
            )

        else:

            print(
                "Already exists: component_dependencies"
            )

        # ====================================================
        # ARCHITECTURE METRICS
        # ====================================================

        print()
        print("-" * 60)
        print("CREATING ARCHITECTURE METRICS")
        print("-" * 60)

        if not table_exists(
            connection,
            "architecture_metrics",
        ):

            connection.execute(
                """
                CREATE TABLE architecture_metrics
                (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    snapshot_id INTEGER NOT NULL,

                    metric_name TEXT NOT NULL,

                    metric_value REAL,

                    metric_data TEXT,

                    FOREIGN KEY(snapshot_id)
                        REFERENCES architecture_snapshots(id)
                )
                """
            )

            print(
                "Created: architecture_metrics"
            )

        else:

            print(
                "Already exists: architecture_metrics"
            )

        # ====================================================
        # BACKFILL COMPONENT KEYS
        # ====================================================

        print()
        print("-" * 60)
        print("BACKFILLING COMPONENT KEYS")
        print("-" * 60)

        connection.execute(
            """
            UPDATE components
            SET component_key =
                LOWER(
                    REPLACE(
                        TRIM(name),
                        ' ',
                        '_'
                    )
                )
            WHERE component_key IS NULL
            """
        )

        print(
            "Existing component keys populated."
        )

        # ====================================================
        # COMMIT
        # ====================================================

        connection.commit()

        print()
        print("=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)

        return True

    except Exception as error:

        print()
        print(
            "MIGRATION ERROR:",
            repr(error),
        )

        connection.rollback()

        return False

    finally:

        connection.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    success = migrate()

    if success:

        print()
        print(
            "Database is ready for the richer architecture model."
        )

    else:

        print()
        print(
            "Database migration failed."
        )