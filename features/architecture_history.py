"""
Architecture History UI
-----------------------

Streamlit interface for the Persistent Architecture Digital Twin.

Features:
    1. View architecture snapshot history
    2. View individual snapshots
    3. Compare two architecture versions
    4. Display added/removed/modified components
    5. Display relationship changes
    6. Display architecture metrics
    7. Display architecture evolution summary

This module contains UI logic only.
The actual history and comparison logic remains in:

    architecture_model/
        snapshot_loader.py
        architecture_comparison.py
        history_manager.py
        architecture_history_engine.py
        git_history.py
"""

from typing import Any, Dict, List, Optional

import streamlit as st

from database.db import get_connection

from architecture_model.snapshot_loader import (
    load_snapshot,
    load_repository_snapshots,
    get_snapshot_info,
)

from architecture_model.architecture_comparison import (
    compare_snapshots,
)


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_repositories() -> List[Dict[str, Any]]:
    """
    Return all repositories stored in the database.
    """

    connection = get_connection()
    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            SELECT
                id,
                name,
                source,
                url,
                created_at
            FROM repositories
            ORDER BY id DESC
            """
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        connection.close()


def get_snapshot_list(
    repository_id: int
) -> List[Dict[str, Any]]:
    """
    Return lightweight information about all
    architecture snapshots for a repository.
    """

    connection = get_connection()
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
            WHERE repository_id = ?
            ORDER BY timestamp ASC, id ASC
            """,
            (repository_id,),
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        connection.close()


# ============================================================
# DISPLAY HELPERS
# ============================================================

def display_component(component):
    """
    Display one architecture component.
    """

    st.markdown(
        f"### {component.name}"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            f"**ID:** `{component.id}`"
        )

        st.write(
            f"**Layer:** `{component.layer}`"
        )

    with col2:

        st.write(
            "**Files:** "
            f"{len(component.files)}"
        )

        st.write(
            "**Dependencies:** "
            f"{len(component.dependencies)}"
        )

    if component.responsibility:

        st.write(
            f"**Responsibility:** "
            f"{component.responsibility}"
        )

    if component.files:

        with st.expander("Files"):

            for file_path in component.files:

                st.code(
                    file_path,
                    language="text"
                )

    if component.dependencies:

        with st.expander("Dependencies"):

            for dependency in component.dependencies:

                st.write(
                    f"→ `{dependency}`"
                )


def display_snapshot(
    snapshot,
    snapshot_info: Optional[Dict[str, Any]] = None
):
    """
    Display complete information about an
    ArchitectureSnapshot.
    """

    st.subheader(
        "Architecture Snapshot"
    )

    if snapshot_info:

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "Version",
                str(
                    snapshot_info.get(
                        "version",
                        snapshot.version
                    )
                )
            )

        with col2:

            st.metric(
                "Components",
                len(snapshot.components)
            )

        with col3:

            st.metric(
                "Relationships",
                len(snapshot.relationships)
            )

        st.write(
            "**Commit:** "
            f"`{snapshot.commit_hash}`"
        )

        st.write(
            "**Timestamp:** "
            f"{snapshot_info.get('timestamp', snapshot.timestamp)}"
        )

    else:

        st.write(
            f"**Version:** `{snapshot.version}`"
        )

        st.write(
            f"**Commit:** `{snapshot.commit_hash}`"
        )

    # --------------------------------------------------------
    # Components
    # --------------------------------------------------------

    st.markdown("---")

    st.subheader(
        "Components"
    )

    if not snapshot.components:

        st.info(
            "No components found in this snapshot."
        )

    else:

        for component in snapshot.components:

            with st.expander(
                f"{component.name} "
                f"({component.layer})"
            ):

                display_component(
                    component
                )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    st.markdown("---")

    st.subheader(
        "Relationships"
    )

    if not snapshot.relationships:

        st.info(
            "No relationships found."
        )

    else:

        for relationship in snapshot.relationships:

            st.write(
                f"`{relationship.source}` "
                f"→ "
                f"`{relationship.target}` "
                f"({relationship.type})"
            )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    st.markdown("---")

    st.subheader(
        "Architecture Metrics"
    )

    if not snapshot.metrics:

        st.info(
            "No architecture metrics available."
        )

    else:

        metric_columns = st.columns(
            min(
                len(snapshot.metrics),
                4
            )
        )

        for index, (
            metric_name,
            metric_value
        ) in enumerate(
            snapshot.metrics.items()
        ):

            with metric_columns[
                index % len(metric_columns)
            ]:

                st.metric(
                    metric_name.replace(
                        "_",
                        " "
                    ).title(),
                    str(metric_value)
                )


# ============================================================
# COMPONENT CHANGE DISPLAY
# ============================================================

def display_component_changes(
    comparison: Dict[str, Any]
):
    """
    Display component additions, removals
    and modifications.
    """

    components = comparison.get(
        "components",
        {}
    )

    added = components.get(
        "added",
        []
    )

    removed = components.get(
        "removed",
        []
    )

    modified = components.get(
        "modified",
        []
    )

    st.subheader(
        "Component Changes"
    )

    # --------------------------------------------------------
    # Added
    # --------------------------------------------------------

    if added:

        st.markdown(
            "#### Components Added"
        )

        for component in added:

            st.success(
                f"+ {component.get('name', component.get('id'))}"
            )

            st.caption(
                f"ID: {component.get('id')}"
            )

    else:

        st.write(
            "No components added."
        )

    # --------------------------------------------------------
    # Removed
    # --------------------------------------------------------

    if removed:

        st.markdown(
            "#### Components Removed"
        )

        for component in removed:

            st.error(
                f"- {component.get('name', component.get('id'))}"
            )

            st.caption(
                f"ID: {component.get('id')}"
            )

    else:

        st.write(
            "No components removed."
        )

    # --------------------------------------------------------
    # Modified
    # --------------------------------------------------------

    if modified:

        st.markdown(
            "#### Components Modified"
        )

        for component in modified:

            st.warning(
                f"~ {component.get('name', component.get('id'))}"
            )

            changes = component.get(
                "changes",
                {}
            )

            if changes:

                for (
                    change_name,
                    change_value
                ) in changes.items():

                    st.write(
                        f"**{change_name}:**"
                    )

                    st.json(
                        change_value
                    )

    else:

        st.write(
            "No components modified."
        )


# ============================================================
# RELATIONSHIP CHANGE DISPLAY
# ============================================================

def display_relationship_changes(
    comparison: Dict[str, Any]
):
    """
    Display relationship additions
    and removals.
    """

    relationships = comparison.get(
        "relationships",
        {}
    )

    added = relationships.get(
        "added",
        []
    )

    removed = relationships.get(
        "removed",
        []
    )

    st.subheader(
        "Relationship Changes"
    )

    # --------------------------------------------------------
    # Added
    # --------------------------------------------------------

    if added:

        st.markdown(
            "#### Relationships Added"
        )

        for relationship in added:

            source = relationship.get(
                "source",
                "unknown"
            )

            target = relationship.get(
                "target",
                "unknown"
            )

            relationship_type = relationship.get(
                "type",
                "unknown"
            )

            st.success(
                f"+ `{source}` → `{target}` "
                f"({relationship_type})"
            )

    else:

        st.write(
            "No relationships added."
        )

    # --------------------------------------------------------
    # Removed
    # --------------------------------------------------------

    if removed:

        st.markdown(
            "#### Relationships Removed"
        )

        for relationship in removed:

            source = relationship.get(
                "source",
                "unknown"
            )

            target = relationship.get(
                "target",
                "unknown"
            )

            relationship_type = relationship.get(
                "type",
                "unknown"
            )

            st.error(
                f"- `{source}` → `{target}` "
                f"({relationship_type})"
            )

    else:

        st.write(
            "No relationships removed."
        )


# ============================================================
# METRIC CHANGE DISPLAY
# ============================================================

def display_metric_changes(
    comparison: Dict[str, Any]
):
    """
    Display architecture metric changes.
    """

    metrics = comparison.get(
        "metrics",
        []
    )

    st.subheader(
        "Metric Changes"
    )

    if not metrics:

        st.info(
            "No metric changes detected."
        )

        return

    for metric in metrics:

        if isinstance(
            metric,
            dict
        ):

            metric_name = metric.get(
                "name",
                metric.get(
                    "metric",
                    "Metric"
                )
            )

            old_value = metric.get(
                "old"
            )

            new_value = metric.get(
                "new"
            )

            st.write(
                f"**{metric_name}**: "
                f"`{old_value}` → `{new_value}`"
            )

        else:

            st.write(
                metric
            )


# ============================================================
# ARCHITECTURE SIZE DISPLAY
# ============================================================

def display_architecture_size(
    comparison: Dict[str, Any]
):
    """
    Display architecture size changes.
    """

    architecture_size = comparison.get(
        "architecture_size",
        {}
    )

    if not architecture_size:

        return

    st.subheader(
        "Architecture Size"
    )

    for category, values in architecture_size.items():

        if not isinstance(
            values,
            dict
        ):

            continue

        old_value = values.get(
            "old",
            0
        )

        new_value = values.get(
            "new",
            0
        )

        change = values.get(
            "change",
            new_value - old_value
        )

        st.write(
            f"**{category.title()}:** "
            f"{old_value} → {new_value} "
            f"({change:+})"
        )


# ============================================================
# COMPARISON DISPLAY
# ============================================================

def display_comparison(
    comparison: Dict[str, Any]
):
    """
    Display complete architecture comparison.
    """

    if not comparison:

        st.warning(
            "No comparison result available."
        )

        return

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    old_version = comparison.get(
        "old_version",
        "unknown"
    )

    new_version = comparison.get(
        "new_version",
        "unknown"
    )

    old_commit = comparison.get(
        "old_commit",
        "unknown"
    )

    new_commit = comparison.get(
        "new_commit",
        "unknown"
    )

    st.subheader(
        "Architecture Evolution"
    )

    st.write(
        f"**Version:** "
        f"`{old_version}` → `{new_version}`"
    )

    st.write(
        f"**Commit:** "
        f"`{old_commit}` → `{new_commit}`"
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary = comparison.get(
        "summary",
        {}
    )

    if summary:

        st.markdown(
            "### Change Summary"
        )

        columns = st.columns(4)

        summary_items = [
            (
                "Total Changes",
                summary.get(
                    "total_changes",
                    0
                )
            ),
            (
                "Added",
                summary.get(
                    "components_added",
                    0
                )
            ),
            (
                "Removed",
                summary.get(
                    "components_removed",
                    0
                )
            ),
            (
                "Modified",
                summary.get(
                    "components_modified",
                    0
                )
            ),
        ]

        for index, (
            label,
            value
        ) in enumerate(summary_items):

            with columns[index]:

                st.metric(
                    label,
                    value
                )

        columns_2 = st.columns(3)

        relationship_items = [
            (
                "Relationships Added",
                summary.get(
                    "relationships_added",
                    0
                )
            ),
            (
                "Relationships Removed",
                summary.get(
                    "relationships_removed",
                    0
                )
            ),
            (
                "Metrics Changed",
                summary.get(
                    "metrics_changed",
                    0
                )
            ),
        ]

        for index, (
            label,
            value
        ) in enumerate(
            relationship_items
        ):

            with columns_2[index]:

                st.metric(
                    label,
                    value
                )

    st.markdown("---")

    # --------------------------------------------------------
    # Components
    # --------------------------------------------------------

    display_component_changes(
        comparison
    )

    st.markdown("---")

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    display_relationship_changes(
        comparison
    )

    st.markdown("---")

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    display_metric_changes(
        comparison
    )

    st.markdown("---")

    # --------------------------------------------------------
    # Architecture size
    # --------------------------------------------------------

    display_architecture_size(
        comparison
    )


# ============================================================
# HISTORY VIEW
# ============================================================

def render_history_view(
    repository_id: int
):
    """
    Render architecture history for one repository.
    """

    snapshots = get_snapshot_list(
        repository_id
    )

    if not snapshots:

        st.info(
            "No architecture snapshots exist "
            "for this repository yet."
        )

        return

    st.subheader(
        "Architecture Snapshot History"
    )

    # --------------------------------------------------------
    # History table
    # --------------------------------------------------------

    history_rows = []

    for snapshot in snapshots:

        history_rows.append(
            {
                "ID": snapshot["id"],
                "Version": snapshot["version"],
                "Commit": snapshot["commit_hash"],
                "Timestamp": snapshot["timestamp"],
            }
        )

    st.dataframe(
        history_rows,
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------
    # Snapshot selector
    # --------------------------------------------------------

    snapshot_options = {
        (
            f"Version {snapshot['version']} | "
            f"{snapshot['commit_hash']} | "
            f"ID {snapshot['id']}"
        ): snapshot["id"]
        for snapshot in snapshots
    }

    selected_snapshot_label = st.selectbox(
        "Select snapshot to inspect",
        list(snapshot_options.keys()),
        key="architecture_history_snapshot"
    )

    selected_snapshot_id = snapshot_options[
        selected_snapshot_label
    ]

    selected_snapshot = load_snapshot(
        selected_snapshot_id
    )

    selected_info = get_snapshot_info(
        selected_snapshot_id
    )

    if selected_snapshot is not None:

        display_snapshot(
            selected_snapshot,
            selected_info
        )

    # --------------------------------------------------------
    # Compare snapshots
    # --------------------------------------------------------

    st.markdown("---")

    st.subheader(
        "Compare Architecture Versions"
    )

    if len(snapshots) < 2:

        st.info(
            "At least two architecture snapshots "
            "are required for comparison."
        )

        return

    comparison_options = {
        (
            f"Version {snapshot['version']} | "
            f"{snapshot['commit_hash']} | "
            f"ID {snapshot['id']}"
        ): snapshot["id"]
        for snapshot in snapshots
    }

    labels = list(
        comparison_options.keys()
    )

    col1, col2 = st.columns(2)

    with col1:

        old_label = st.selectbox(
            "Older snapshot",
            labels,
            index=max(
                0,
                len(labels) - 2
            ),
            key="architecture_history_old"
        )

    with col2:

        new_label = st.selectbox(
            "Newer snapshot",
            labels,
            index=len(labels) - 1,
            key="architecture_history_new"
        )

    old_snapshot_id = comparison_options[
        old_label
    ]

    new_snapshot_id = comparison_options[
        new_label
    ]

    if old_snapshot_id == new_snapshot_id:

        st.warning(
            "Please select two different snapshots."
        )

        return

    if st.button(
        "Compare Architectures",
        key="compare_architectures_button"
    ):

        old_snapshot = load_snapshot(
            old_snapshot_id
        )

        new_snapshot = load_snapshot(
            new_snapshot_id
        )

        if (
            old_snapshot is None
            or new_snapshot is None
        ):

            st.error(
                "Unable to load one or both snapshots."
            )

            return

        comparison = compare_snapshots(
            old_snapshot,
            new_snapshot
        )

        display_comparison(
            comparison
        )


# ============================================================
# MAIN UI
# ============================================================

def render_architecture_history():
    """
    Main Streamlit entry point.

    Call this function from app.py.
    """

    st.title(
        "Architecture History"
    )

    st.caption(
        "Persistent Architecture Digital Twin "
        "and Architecture Evolution"
    )

    # --------------------------------------------------------
    # Load repositories
    # --------------------------------------------------------

    try:

        repositories = get_repositories()

    except Exception as error:

        st.error(
            "Unable to load repositories."
        )

        st.exception(
            error
        )

        return

    if not repositories:

        st.info(
            "No repositories found in the database."
        )

        return

    # --------------------------------------------------------
    # Repository selector
    # --------------------------------------------------------

    repository_options = {
        (
            f"{repository['name']} "
            f"(ID: {repository['id']})"
        ): repository["id"]
        for repository in repositories
    }

    selected_repository_label = st.selectbox(
        "Select Repository",
        list(repository_options.keys()),
        key="architecture_history_repository"
    )

    repository_id = repository_options[
        selected_repository_label
    ]

    # --------------------------------------------------------
    # Render history
    # --------------------------------------------------------

    render_history_view(
        repository_id
    )


# ============================================================
# ALIAS
# ============================================================

def architecture_history_page():
    """
    Alias for app.py integrations that prefer
    page-style function naming.
    """

    render_architecture_history()


# ============================================================
# OPTIONAL DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    render_architecture_history()