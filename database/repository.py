from .db import get_connection


# ============================================================
# REPOSITORY
# ============================================================

def save_repository(name, source=None, url=None):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO repositories
            (name, source, url)
            VALUES (?, ?, ?)
            """,
            (name, source, url),
        )

        repository_id = cursor.lastrowid

        connection.commit()

        return repository_id

    finally:
        connection.close()


def get_repositories():
    connection = get_connection()

    try:
        return connection.execute(
            """
            SELECT
                id,
                name,
                source,
                url,
                created_at
            FROM repositories
            ORDER BY created_at DESC
            """
        ).fetchall()

    finally:
        connection.close()


# ============================================================
# SNAPSHOTS
# ============================================================

def save_snapshot(
    repository_id,
    commit_hash,
    version=None,
    timestamp=None,
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        if timestamp is None:
            cursor.execute(
                """
                INSERT INTO architecture_snapshots
                (
                    repository_id,
                    commit_hash,
                    version
                )
                VALUES (?, ?, ?)
                """,
                (
                    repository_id,
                    commit_hash,
                    version,
                ),
            )

        else:
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
                    commit_hash,
                    version,
                    timestamp,
                ),
            )

        snapshot_id = cursor.lastrowid

        connection.commit()

        return snapshot_id

    finally:
        connection.close()


def get_snapshots(repository_id=None):
    connection = get_connection()

    try:
        if repository_id is None:
            return connection.execute(
                """
                SELECT
                    id,
                    repository_id,
                    commit_hash,
                    version,
                    timestamp
                FROM architecture_snapshots
                ORDER BY timestamp DESC
                """
            ).fetchall()

        return connection.execute(
            """
            SELECT
                id,
                repository_id,
                commit_hash,
                version,
                timestamp
            FROM architecture_snapshots
            WHERE repository_id = ?
            ORDER BY timestamp DESC
            """,
            (repository_id,),
        ).fetchall()

    finally:
        connection.close()


# ============================================================
# COMPONENTS
# ============================================================

def save_component(
    snapshot_id,
    name,
    component_type=None,
    component_key=None,
    responsibility=None,
    layer=None,
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO components
            (
                snapshot_id,
                name,
                component_type,
                component_key,
                responsibility,
                layer
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                name,
                component_type,
                component_key,
                responsibility,
                layer,
            ),
        )

        component_id = cursor.lastrowid

        connection.commit()

        return component_id

    finally:
        connection.close()


def get_components(snapshot_id=None):
    connection = get_connection()

    try:
        if snapshot_id is None:
            return connection.execute(
                """
                SELECT
                    id,
                    snapshot_id,
                    name,
                    component_type,
                    component_key,
                    responsibility,
                    layer
                FROM components
                ORDER BY snapshot_id, id
                """
            ).fetchall()

        return connection.execute(
            """
            SELECT
                id,
                snapshot_id,
                name,
                component_type,
                component_key,
                responsibility,
                layer
            FROM components
            WHERE snapshot_id = ?
            ORDER BY id
            """,
            (snapshot_id,),
        ).fetchall()

    finally:
        connection.close()


# ============================================================
# COMPONENT FILES
# ============================================================

def save_component_file(
    component_id,
    file_path,
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

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

        file_id = cursor.lastrowid

        connection.commit()

        return file_id

    finally:
        connection.close()


def get_component_files(component_id):
    connection = get_connection()

    try:
        return connection.execute(
            """
            SELECT
                id,
                component_id,
                file_path
            FROM component_files
            WHERE component_id = ?
            ORDER BY id
            """,
            (component_id,),
        ).fetchall()

    finally:
        connection.close()


# ============================================================
# COMPONENT DEPENDENCIES
# ============================================================

def save_component_dependency(
    component_id,
    dependency_component_key,
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

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
                dependency_component_key,
            ),
        )

        dependency_id = cursor.lastrowid

        connection.commit()

        return dependency_id

    finally:
        connection.close()


def get_component_dependencies(component_id):
    connection = get_connection()

    try:
        return connection.execute(
            """
            SELECT
                id,
                component_id,
                dependency_component_key
            FROM component_dependencies
            WHERE component_id = ?
            ORDER BY id
            """,
            (component_id,),
        ).fetchall()

    finally:
        connection.close()


# ============================================================
# RELATIONSHIPS
# ============================================================

def save_relationship(
    snapshot_id,
    source,
    target,
    relationship_type=None,
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

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
                source,
                target,
                relationship_type,
            ),
        )

        relationship_id = cursor.lastrowid

        connection.commit()

        return relationship_id

    finally:
        connection.close()


def get_relationships(snapshot_id=None):
    connection = get_connection()

    try:
        if snapshot_id is None:
            return connection.execute(
                """
                SELECT
                    id,
                    snapshot_id,
                    source,
                    target,
                    relationship_type
                FROM relationships
                ORDER BY snapshot_id, id
                """
            ).fetchall()

        return connection.execute(
            """
            SELECT
                id,
                snapshot_id,
                source,
                target,
                relationship_type
            FROM relationships
            WHERE snapshot_id = ?
            ORDER BY id
            """,
            (snapshot_id,),
        ).fetchall()

    finally:
        connection.close()


# ============================================================
# ARCHITECTURE METRICS
# ============================================================

def save_architecture_metric(
    snapshot_id,
    metric_name,
    metric_value=None,
    metric_data=None,
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO architecture_metrics
            (
                snapshot_id,
                metric_name,
                metric_value,
                metric_data
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                snapshot_id,
                metric_name,
                metric_value,
                metric_data,
            ),
        )

        metric_id = cursor.lastrowid

        connection.commit()

        return metric_id

    finally:
        connection.close()


def get_architecture_metrics(snapshot_id):
    connection = get_connection()

    try:
        return connection.execute(
            """
            SELECT
                id,
                snapshot_id,
                metric_name,
                metric_value,
                metric_data
            FROM architecture_metrics
            WHERE snapshot_id = ?
            ORDER BY id
            """,
            (snapshot_id,),
        ).fetchall()

    finally:
        connection.close()


# ============================================================
# COMPLETE ARCHITECTURE SNAPSHOT
# ============================================================

def save_architecture_snapshot(
    repository_id,
    snapshot,
):
    """
    Persist a complete ArchitectureSnapshot.

    Saves:

        1. architecture_snapshots
        2. components
        3. component_files
        4. component_dependencies
        5. relationships
        6. architecture_metrics

    All records are saved inside ONE database transaction.

    Returns:
        int: Database snapshot ID.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # ----------------------------------------------------
        # 1. SAVE SNAPSHOT HEADER
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # 2. SAVE COMPONENTS
        # ----------------------------------------------------

        for component in snapshot.components:

            cursor.execute(
                """
                INSERT INTO components
                (
                    snapshot_id,
                    name,
                    component_type,
                    component_key,
                    responsibility,
                    layer
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    component.name,
                    getattr(
                        component,
                        "component_type",
                        None,
                    ),
                    component.id,
                    component.responsibility,
                    component.layer,
                ),
            )

            component_id = cursor.lastrowid

            # ------------------------------------------------
            # 2a. SAVE COMPONENT FILES
            # ------------------------------------------------

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

            # ------------------------------------------------
            # 2b. SAVE COMPONENT DEPENDENCIES
            # ------------------------------------------------

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

        # ----------------------------------------------------
        # 3. SAVE RELATIONSHIPS
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # 4. SAVE METRICS
        # ----------------------------------------------------

        for metric_name, metric_value in snapshot.metrics.items():

            if isinstance(
                metric_value,
                bool,
            ):
                # bool is technically an int in Python,
                # but storing it as metric_data is clearer.
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

            elif isinstance(
                metric_value,
                (int, float),
            ):
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
                        metric_value,
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

        # ----------------------------------------------------
        # 5. COMMIT COMPLETE SNAPSHOT
        # ----------------------------------------------------

        connection.commit()

        return snapshot_id

    except Exception:
        # If anything fails, do not leave a half-written
        # architecture snapshot in the database.
        connection.rollback()
        raise
    # ============================================================
# RUNTIME ARCHITECTURE PERSISTENCE
# ============================================================

import json

from architecture_model.runtime_model import (
    RuntimeArchitecture,
    RuntimeRelationship,
)


def save_runtime_execution(
    repository_id,
    runtime_architecture,
    snapshot_id=None,
    version=None,
    commit_hash=None,
    scenario=None,
):
    """
    Persist one runtime architecture execution.

    Stores:
        1. runtime execution metadata
        2. aggregated runtime relationships

    Returns:
        int: runtime execution database ID
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # ----------------------------------------------------
        # 1. SAVE RUNTIME EXECUTION
        # ----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO runtime_executions
            (
                repository_id,
                snapshot_id,
                version,
                commit_hash,
                scenario,
                entry_point,
                total_calls,
                module_count,
                relationship_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repository_id,
                snapshot_id,
                version,
                commit_hash,
                scenario,
                runtime_architecture.entry_point,
                runtime_architecture.total_calls,
                runtime_architecture.get_module_count(),
                runtime_architecture.get_relationship_count(),
            ),
        )

        execution_id = cursor.lastrowid

        # ----------------------------------------------------
        # 2. SAVE RUNTIME RELATIONSHIPS
        # ----------------------------------------------------

        for relationship in runtime_architecture.get_relationships():

            cursor.execute(
                """
                INSERT INTO runtime_relationships
                (
                    execution_id,
                    source,
                    target,
                    call_count,
                    functions
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    execution_id,
                    relationship.source,
                    relationship.target,
                    relationship.call_count,
                    json.dumps(
                        sorted(relationship.functions)
                    ),
                ),
            )

        connection.commit()

        return execution_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_runtime_executions(
    repository_id=None,
    snapshot_id=None,
):
    """
    Return saved runtime executions.

    Can optionally filter by repository or snapshot.
    """

    connection = get_connection()

    try:

        if snapshot_id is not None:

            return connection.execute(
                """
                SELECT *
                FROM runtime_executions
                WHERE snapshot_id = ?
                ORDER BY timestamp DESC, id DESC
                """,
                (snapshot_id,),
            ).fetchall()

        if repository_id is not None:

            return connection.execute(
                """
                SELECT *
                FROM runtime_executions
                WHERE repository_id = ?
                ORDER BY timestamp DESC, id DESC
                """,
                (repository_id,),
            ).fetchall()

        return connection.execute(
            """
            SELECT *
            FROM runtime_executions
            ORDER BY timestamp DESC, id DESC
            """
        ).fetchall()

    finally:
        connection.close()


def load_runtime_architecture(execution_id):
    """
    Reconstruct a RuntimeArchitecture object from the database.
    """

    connection = get_connection()

    try:

        execution = connection.execute(
            """
            SELECT *
            FROM runtime_executions
            WHERE id = ?
            """,
            (execution_id,),
        ).fetchone()

        if execution is None:
            raise ValueError(
                f"Runtime execution {execution_id} not found."
            )

        runtime_architecture = RuntimeArchitecture(
            entry_point=execution["entry_point"] or ""
        )

        relationship_rows = connection.execute(
            """
            SELECT *
            FROM runtime_relationships
            WHERE execution_id = ?
            ORDER BY id
            """,
            (execution_id,),
        ).fetchall()

        # Reconstruct aggregated relationships directly.
        for row in relationship_rows:

            try:
                functions = set(
                    json.loads(row["functions"] or "[]")
                )
            except (json.JSONDecodeError, TypeError):
                functions = set()

            relationship = RuntimeRelationship(
                source=row["source"],
                target=row["target"],
                call_count=row["call_count"] or 0,
                functions=functions,
            )

            relationship_key = (
                f"{relationship.source}->{relationship.target}"
            )

            runtime_architecture.relationships[
                relationship_key
            ] = relationship

            runtime_architecture.modules.add(
                relationship.source
            )

            runtime_architecture.modules.add(
                relationship.target
            )

        runtime_architecture.total_calls = (
            execution["total_calls"] or 0
        )

        return runtime_architecture

    
    finally:
        connection.close()