from typing import Optional
import sqlite3

from database.db import get_connection

from architecture_model.model import (
    Component,
    Relationship,
    ArchitectureSnapshot,
)


# ============================================================
# CONNECTION HELPER
# ============================================================

def _get_connection(database_path=None):
    """
    Return a database connection.

    If database_path is provided:
        use that database.

    Otherwise:
        use the project's normal architecture.db.
    """

    if database_path is None:
        connection = get_connection()
    else:
        connection = sqlite3.connect(database_path)

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# TABLE COLUMN HELPER
# ============================================================

def _get_table_columns(cursor, table_name):
    """
    Return the list of columns available in a SQLite table.

    This allows the history loader to work with the
    project's existing database schema.
    """

    cursor.execute(f"PRAGMA table_info({table_name})")

    rows = cursor.fetchall()

    return [row["name"] for row in rows]


# ============================================================
# LOAD ONE SNAPSHOT
# ============================================================

def load_snapshot(
    snapshot_id: int,
    database_path=None
) -> Optional[ArchitectureSnapshot]:
    """
    Load one complete ArchitectureSnapshot from SQLite.

    Parameters
    ----------
    snapshot_id : int
        ID of the architecture snapshot.

    database_path : optional
        Path to SQLite database.

        If omitted, the project's normal architecture.db
        is used.

    Returns
    -------
    ArchitectureSnapshot | None
    """

    connection = _get_connection(database_path)
    cursor = connection.cursor()

    try:

        # ====================================================
        # 1. LOAD SNAPSHOT
        # ====================================================

        cursor.execute(
            """
            SELECT
                id,
                repository_id,
                commit_hash,
                version,
                timestamp
            FROM architecture_snapshots
            WHERE id = ?
            """,
            (snapshot_id,),
        )

        snapshot_row = cursor.fetchone()

        if snapshot_row is None:
            return None

        # ====================================================
        # 2. DETECT COMPONENT TABLE SCHEMA
        # ====================================================

        component_columns = _get_table_columns(
            cursor,
            "components"
        )

        # ----------------------------------------------------
        # Find component identifier column
        # ----------------------------------------------------

        if "component_key" in component_columns:
            component_id_column = "component_key"

        elif "key" in component_columns:
            component_id_column = "key"

        elif "name" in component_columns:
            component_id_column = "name"

        else:
            component_id_column = "id"

        # ----------------------------------------------------
        # Check optional columns
        # ----------------------------------------------------

        has_snapshot_id = "snapshot_id" in component_columns
        has_responsibility = "responsibility" in component_columns
        has_layer = "layer" in component_columns
        has_component_type = "component_type" in component_columns

        # ====================================================
        # 3. LOAD COMPONENTS
        # ====================================================

        select_columns = [
            "id",
            f"{component_id_column} AS component_identifier",
        ]

        if "name" in component_columns:
            select_columns.append("name")
        else:
            select_columns.append(
                f"{component_id_column} AS name"
            )

        if has_responsibility:
            select_columns.append("responsibility")
        else:
            select_columns.append("NULL AS responsibility")

        if has_layer:
            select_columns.append("layer")
        else:
            select_columns.append("NULL AS layer")

        if has_component_type:
            select_columns.append("component_type")
        else:
            select_columns.append("NULL AS component_type")

        component_query = f"""
            SELECT
                {", ".join(select_columns)}
            FROM components
        """

        # ----------------------------------------------------
        # Filter by snapshot if the column exists
        # ----------------------------------------------------

        if has_snapshot_id:
            component_query += """
                WHERE snapshot_id = ?
                ORDER BY id
            """

            cursor.execute(
                component_query,
                (snapshot_id,),
            )

        else:
            # ------------------------------------------------
            # Some older architecture databases may not store
            # snapshot_id directly in components.
            #
            # In that case we load all components.
            # ------------------------------------------------

            component_query += """
                ORDER BY id
            """

            cursor.execute(component_query)

        component_rows = cursor.fetchall()

        components = []

        # ====================================================
        # 4. RECONSTRUCT COMPONENTS
        # ====================================================

        for row in component_rows:

            component_id = row["component_identifier"]

            # ------------------------------------------------
            # Load component files
            # ------------------------------------------------

            files = []

            component_file_columns = _get_table_columns(
                cursor,
                "component_files"
            )

            if (
                "component_id" in component_file_columns
                and "file_path" in component_file_columns
            ):

                cursor.execute(
                    """
                    SELECT file_path
                    FROM component_files
                    WHERE component_id = ?
                    ORDER BY id
                    """,
                    (row["id"],),
                )

                file_rows = cursor.fetchall()

                files = [
                    file_row["file_path"]
                    for file_row in file_rows
                    if file_row["file_path"] is not None
                ]

            # ------------------------------------------------
            # Load component dependencies
            # ------------------------------------------------

            dependencies = []

            dependency_columns = _get_table_columns(
                cursor,
                "component_dependencies"
            )

            if "component_id" in dependency_columns:

                # --------------------------------------------
                # New schema
                # --------------------------------------------

                if "dependency_component_key" in dependency_columns:

                    cursor.execute(
                        """
                        SELECT dependency_component_key
                        FROM component_dependencies
                        WHERE component_id = ?
                        ORDER BY id
                        """,
                        (row["id"],),
                    )

                    dependency_rows = cursor.fetchall()

                    dependencies = [
                        dependency_row[
                            "dependency_component_key"
                        ]
                        for dependency_row in dependency_rows
                        if dependency_row[
                            "dependency_component_key"
                        ] is not None
                    ]

                # --------------------------------------------
                # Alternative schema
                # --------------------------------------------

                elif "dependency_id" in dependency_columns:

                    cursor.execute(
                        """
                        SELECT dependency_id
                        FROM component_dependencies
                        WHERE component_id = ?
                        ORDER BY id
                        """,
                        (row["id"],),
                    )

                    dependency_rows = cursor.fetchall()

                    dependencies = [
                        dependency_row["dependency_id"]
                        for dependency_row in dependency_rows
                        if dependency_row["dependency_id"] is not None
                    ]

            # ------------------------------------------------
            # Reconstruct Component
            # ------------------------------------------------

            component = Component(
                id=component_id,

                name=(
                    row["name"]
                    if row["name"] is not None
                    else str(component_id)
                ),

                responsibility=(
                    row["responsibility"]
                    if row["responsibility"] is not None
                    else ""
                ),

                layer=(
                    row["layer"]
                    if row["layer"] is not None
                    else ""
                ),

                files=files,

                dependencies=dependencies,
            )

            components.append(component)

        # ====================================================
        # 5. LOAD RELATIONSHIPS
        # ====================================================

        relationships = []

        relationship_columns = _get_table_columns(
            cursor,
            "relationships"
        )

        required_relationship_columns = {
            "source",
            "target",
        }

        if required_relationship_columns.issubset(
            set(relationship_columns)
        ):

            has_relationship_snapshot = (
                "snapshot_id" in relationship_columns
            )

            has_relationship_type = (
                "relationship_type" in relationship_columns
            )

            if has_relationship_snapshot:

                relationship_select = """
                    source,
                    target
                """

                if has_relationship_type:
                    relationship_select += ", relationship_type"
                else:
                    relationship_select += (
                        ", NULL AS relationship_type"
                    )

                cursor.execute(
                    f"""
                    SELECT
                        {relationship_select}
                    FROM relationships
                    WHERE snapshot_id = ?
                    ORDER BY id
                    """,
                    (snapshot_id,),
                )

            else:

                relationship_select = """
                    source,
                    target
                """

                if has_relationship_type:
                    relationship_select += ", relationship_type"
                else:
                    relationship_select += (
                        ", NULL AS relationship_type"
                    )

                cursor.execute(
                    f"""
                    SELECT
                        {relationship_select}
                    FROM relationships
                    ORDER BY id
                    """
                )

            relationship_rows = cursor.fetchall()

            for row in relationship_rows:

                relationship = Relationship(
                    source=row["source"],
                    target=row["target"],
                    type=(
                        row["relationship_type"]
                        or "unknown"
                    ),
                )

                relationships.append(relationship)

        # ====================================================
        # 6. LOAD METRICS
        # ====================================================

        metrics = {}

        metric_columns = _get_table_columns(
            cursor,
            "architecture_metrics"
        )

        if "snapshot_id" in metric_columns:

            metric_select = []

            if "metric_name" in metric_columns:
                metric_select.append("metric_name")

            if "metric_value" in metric_columns:
                metric_select.append("metric_value")
            else:
                metric_select.append(
                    "NULL AS metric_value"
                )

            if "metric_data" in metric_columns:
                metric_select.append("metric_data")
            else:
                metric_select.append(
                    "NULL AS metric_data"
                )

            if "metric_name" in metric_columns:

                cursor.execute(
                    f"""
                    SELECT
                        {", ".join(metric_select)}
                    FROM architecture_metrics
                    WHERE snapshot_id = ?
                    ORDER BY id
                    """,
                    (snapshot_id,),
                )

                metric_rows = cursor.fetchall()

                for row in metric_rows:

                    metric_name = row["metric_name"]

                    if metric_name is None:
                        continue

                    if row["metric_value"] is not None:
                        metrics[metric_name] = (
                            row["metric_value"]
                        )

                    elif row["metric_data"] is not None:
                        metrics[metric_name] = (
                            row["metric_data"]
                        )

        # ====================================================
        # 7. RECONSTRUCT SNAPSHOT
        # ====================================================

        snapshot = ArchitectureSnapshot(
            version=(
                str(snapshot_row["version"])
                if snapshot_row["version"] is not None
                else "unknown"
            ),

            commit_hash=(
                snapshot_row["commit_hash"]
                or "unknown"
            ),

            components=components,

            relationships=relationships,

            metrics=metrics,

            violations=[],

            timestamp=(
                snapshot_row["timestamp"]
                or ""
            ),
        )

        return snapshot

    finally:

        connection.close()


# ============================================================
# LOAD ALL SNAPSHOTS FOR REPOSITORY
# ============================================================

def load_repository_snapshots(
    repository_id: int,
    database_path=None
):
    """
    Load all architecture snapshots for a repository.
    """

    connection = _get_connection(database_path)
    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            SELECT id
            FROM architecture_snapshots
            WHERE repository_id = ?
            ORDER BY timestamp ASC, id ASC
            """,
            (repository_id,),
        )

        rows = cursor.fetchall()

    finally:

        connection.close()

    snapshots = []

    for row in rows:

        snapshot = load_snapshot(
            row["id"],
            database_path=database_path,
        )

        if snapshot is not None:
            snapshots.append(snapshot)

    return snapshots


# ============================================================
# LOAD LATEST SNAPSHOT
# ============================================================

def load_latest_snapshot(
    repository_id: int,
    database_path=None
):
    """
    Load the latest architecture snapshot
    for a repository.
    """

    connection = _get_connection(database_path)
    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            SELECT id
            FROM architecture_snapshots
            WHERE repository_id = ?
            ORDER BY timestamp DESC, id DESC
            LIMIT 1
            """,
            (repository_id,),
        )

        row = cursor.fetchone()

    finally:

        connection.close()

    if row is None:
        return None

    return load_snapshot(
        row["id"],
        database_path=database_path,
    )


# ============================================================
# LOAD PREVIOUS SNAPSHOT
# ============================================================

def load_previous_snapshot(
    repository_id: int,
    current_snapshot_id: int,
    database_path=None
):
    """
    Load the snapshot immediately before
    the specified snapshot.
    """

    connection = _get_connection(database_path)
    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            SELECT id
            FROM architecture_snapshots
            WHERE repository_id = ?
              AND id < ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                repository_id,
                current_snapshot_id,
            ),
        )

        row = cursor.fetchone()

    finally:

        connection.close()

    if row is None:
        return None

    return load_snapshot(
        row["id"],
        database_path=database_path,
    )


# ============================================================
# SNAPSHOT INFORMATION
# ============================================================

def get_snapshot_info(
    snapshot_id: int,
    database_path=None
):
    """
    Return basic information about a snapshot.

    Useful for history UI without loading
    the complete architecture.
    """

    connection = _get_connection(database_path)
    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            SELECT
                id,
                repository_id,
                commit_hash,
                version,
                timestamp
            FROM architecture_snapshots
            WHERE id = ?
            """,
            (snapshot_id,),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)

    finally:

        connection.close()