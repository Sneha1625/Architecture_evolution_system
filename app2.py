import sqlite3
from pathlib import Path

import streamlit as st


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "architecture.db"


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Architecture Evolution System",
    page_icon="🏗️",
    layout="wide",
)

from features.architecture_history import render_architecture_history
# ============================================================
# DATABASE
# ============================================================

def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def database_exists():
    return DATABASE_PATH.exists()


def get_tables():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()

        return [row["name"] for row in rows]

    finally:
        connection.close()


def get_table_count(table_name):
    connection = get_connection()

    try:
        return connection.execute(
            f"SELECT COUNT(*) AS count FROM [{table_name}]"
        ).fetchone()["count"]

    finally:
        connection.close()


def fetch_rows(query, params=()):
    connection = get_connection()

    try:
        rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    finally:
        connection.close()


# ============================================================
# DATA ACCESS
# ============================================================

def get_repositories():
    return fetch_rows(
        """
        SELECT
            id,
            name,
            source,
            url,
            created_at
        FROM repositories
        ORDER BY id
        """
    )


def get_snapshots():
    return fetch_rows(
        """
        SELECT
            id,
            repository_id,
            commit_hash,
            version,
            timestamp
        FROM architecture_snapshots
        ORDER BY id
        """
    )


def get_components(snapshot_id=None):

    if snapshot_id is None:
        return fetch_rows(
            """
            SELECT
                id,
                snapshot_id,
                name,
                component_type
            FROM components
            ORDER BY snapshot_id, id
            """
        )

    return fetch_rows(
        """
        SELECT
            id,
            snapshot_id,
            name,
            component_type
        FROM components
        WHERE snapshot_id = ?
        ORDER BY id
        """,
        (snapshot_id,),
    )


def get_relationships(snapshot_id=None):

    if snapshot_id is None:
        return fetch_rows(
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
        )

    return fetch_rows(
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
    )


# ============================================================
# RELATIONSHIP NORMALIZATION
# ============================================================

def normalize_component_reference(reference, components):

    if reference is None:
        return None

    reference = str(reference)

    # Direct match
    for component in components:

        if component["name"] == reference:
            return component["name"]

    # component_parser -> Parser
    if reference.startswith("component_"):

        suffix = reference[len("component_"):]

        normalized_suffix = (
            suffix
            .replace("_", " ")
            .strip()
            .lower()
        )

        for component in components:

            component_name = str(
                component["name"]
            ).strip()

            if component_name.lower() == normalized_suffix:
                return component_name

        # Parser -> component_parser
        for component in components:

            component_name = str(
                component["name"]
            ).strip()

            if (
                component_name
                .lower()
                .replace(" ", "_")
                == suffix.lower()
            ):
                return component_name

    return reference


def get_normalized_relationships(snapshot_id):

    components = get_components(snapshot_id)
    relationships = get_relationships(snapshot_id)

    normalized = []

    for relationship in relationships:

        source = normalize_component_reference(
            relationship["source"],
            components,
        )

        target = normalize_component_reference(
            relationship["target"],
            components,
        )

        normalized.append(
            {
                "id": relationship["id"],
                "snapshot_id": relationship["snapshot_id"],
                "source": source,
                "target": target,
                "relationship_type": relationship[
                    "relationship_type"
                ],
                "raw_source": relationship["source"],
                "raw_target": relationship["target"],
            }
        )

    return normalized


# ============================================================
# HELPERS
# ============================================================

def snapshot_label(snapshot):

    return (
        f"Snapshot {snapshot['id']} "
        f"(v{snapshot['version']}, "
        f"{snapshot['commit_hash']})"
    )


def component_names(snapshot_id):

    components = get_components(snapshot_id)

    return {
        str(component["name"]).strip()
        for component in components
        if component["name"] is not None
    }


def relationship_keys(snapshot_id):

    relationships = get_normalized_relationships(
        snapshot_id
    )

    result = set()

    for relationship in relationships:

        source = relationship["source"]
        target = relationship["target"]

        if source is None or target is None:
            continue

        result.add(
            (
                str(source).strip(),
                str(target).strip(),
            )
        )

    return result


def relationship_key_with_type(snapshot_id):

    relationships = get_normalized_relationships(
        snapshot_id
    )

    result = set()

    for relationship in relationships:

        source = relationship["source"]
        target = relationship["target"]
        relationship_type = relationship[
            "relationship_type"
        ]

        if source is None or target is None:
            continue

        result.add(
            (
                str(source).strip(),
                str(target).strip(),
                relationship_type,
            )
        )

    return result


# ============================================================
# ARCHITECTURE HEALTH CALCULATIONS
# ============================================================

def calculate_architecture_health(snapshot_id):

    components = get_components(snapshot_id)

    relationships = get_normalized_relationships(
        snapshot_id
    )

    component_set = {
        str(component["name"]).strip()
        for component in components
        if component["name"] is not None
    }

    fan_in = {
        component: 0
        for component in component_set
    }

    fan_out = {
        component: 0
        for component in component_set
    }

    incoming = {
        component: []
        for component in component_set
    }

    outgoing = {
        component: []
        for component in component_set
    }

    valid_relationships = []

    for relationship in relationships:

        source = relationship["source"]
        target = relationship["target"]

        if source not in component_set:
            continue

        if target not in component_set:
            continue

        valid_relationships.append(
            relationship
        )

        if target in fan_in:
            fan_in[target] += 1
            incoming[target].append(source)

        if source in fan_out:
            fan_out[source] += 1
            outgoing[source].append(target)

    isolated_components = sorted(
        [
            component
            for component in component_set
            if fan_in[component] == 0
            and fan_out[component] == 0
        ],
        key=str.lower,
    )

    component_metrics = []

    for component in sorted(
        component_set,
        key=str.lower,
    ):

        component_metrics.append(
            {
                "Component": component,
                "Fan-in": fan_in[component],
                "Fan-out": fan_out[component],
                "Total Connections": (
                    fan_in[component]
                    + fan_out[component]
                ),
            }
        )

    highest_fan_in = max(
        fan_in.values(),
        default=0,
    )

    highest_fan_out = max(
        fan_out.values(),
        default=0,
    )

    highest_connection = max(
        (
            fan_in[name] + fan_out[name]
            for name in component_set
        ),
        default=0,
    )

    fan_in_hubs = sorted(
        [
            name
            for name in component_set
            if fan_in[name] == highest_fan_in
            and highest_fan_in > 0
        ],
        key=str.lower,
    )

    fan_out_hubs = sorted(
        [
            name
            for name in component_set
            if fan_out[name] == highest_fan_out
            and highest_fan_out > 0
        ],
        key=str.lower,
    )

    connection_hubs = sorted(
        [
            name
            for name in component_set
            if (
                fan_in[name] + fan_out[name]
            ) == highest_connection
            and highest_connection > 0
        ],
        key=str.lower,
    )

    component_count = len(component_set)
    relationship_count = len(
        valid_relationships
    )

    if component_count > 0:
        average_fan_out = (
            sum(fan_out.values())
            / component_count
        )

        average_fan_in = (
            sum(fan_in.values())
            / component_count
        )
    else:
        average_fan_out = 0
        average_fan_in = 0

    return {
        "component_count": component_count,
        "relationship_count": relationship_count,
        "fan_in": fan_in,
        "fan_out": fan_out,
        "incoming": incoming,
        "outgoing": outgoing,
        "isolated_components": isolated_components,
        "component_metrics": component_metrics,
        "average_fan_in": average_fan_in,
        "average_fan_out": average_fan_out,
        "highest_fan_in": highest_fan_in,
        "highest_fan_out": highest_fan_out,
        "highest_connection": highest_connection,
        "fan_in_hubs": fan_in_hubs,
        "fan_out_hubs": fan_out_hubs,
        "connection_hubs": connection_hubs,
    }


def calculate_change_metrics(
    before_snapshot_id,
    after_snapshot_id,
):

    before_components = component_names(
        before_snapshot_id
    )

    after_components = component_names(
        after_snapshot_id
    )

    added_components = (
        after_components
        - before_components
    )

    removed_components = (
        before_components
        - after_components
    )

    unchanged_components = (
        before_components
        & after_components
    )

    before_relationships = (
        relationship_key_with_type(
            before_snapshot_id
        )
    )

    after_relationships = (
        relationship_key_with_type(
            after_snapshot_id
        )
    )

    added_relationships = (
        after_relationships
        - before_relationships
    )

    removed_relationships = (
        before_relationships
        - after_relationships
    )

    unchanged_relationships = (
        before_relationships
        & after_relationships
    )

    return {
        "added_components": added_components,
        "removed_components": removed_components,
        "unchanged_components": unchanged_components,
        "added_relationships": added_relationships,
        "removed_relationships": removed_relationships,
        "unchanged_relationships": unchanged_relationships,
    }


# ============================================================
# DATABASE STATUS
# ============================================================

def show_database_status():

    st.sidebar.markdown("### 🗄️ Database")

    if not database_exists():

        st.sidebar.error(
            "Database not found"
        )

        return

    try:

        tables = get_tables()

        st.sidebar.success(
            "DATABASE CONNECTED"
        )

        if "architecture_snapshots" in tables:

            st.sidebar.metric(
                "Snapshots",
                get_table_count(
                    "architecture_snapshots"
                ),
            )

        if "components" in tables:

            st.sidebar.metric(
                "Components",
                get_table_count(
                    "components"
                ),
            )

        if "relationships" in tables:

            st.sidebar.metric(
                "Relationships",
                get_table_count(
                    "relationships"
                ),
            )

        if "repositories" in tables:

            st.sidebar.metric(
                "Repositories",
                get_table_count(
                    "repositories"
                ),
            )

    except Exception as error:

        st.sidebar.error(
            f"Database error: {error}"
        )


# ============================================================
# OVERVIEW
# ============================================================

def show_overview():

    st.title(
        "🏗️ Architecture Evolution System"
    )

    st.markdown(
        """
        **Repository → Snapshot → Components → Relationships
        → Architecture Graph → Comparison → Health**
        """
    )

    st.divider()

    if not database_exists():

        st.error(
            f"Database not found:\n\n"
            f"`{DATABASE_PATH}`"
        )

        return

    st.success(
        "DATABASE CONNECTED"
    )

    tables = get_tables()

    st.subheader("Database")

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        count = (
            get_table_count("repositories")
            if "repositories" in tables
            else 0
        )

        st.metric(
            "Repositories",
            count,
        )

    with col2:

        count = (
            get_table_count(
                "architecture_snapshots"
            )
            if "architecture_snapshots"
            in tables
            else 0
        )

        st.metric(
            "Snapshots",
            count,
        )

    with col3:

        count = (
            get_table_count("components")
            if "components" in tables
            else 0
        )

        st.metric(
            "Components",
            count,
        )

    with col4:

        count = (
            get_table_count("relationships")
            if "relationships" in tables
            else 0
        )

        st.metric(
            "Relationships",
            count,
        )

    st.divider()

    st.subheader("System Flow")

    st.code(
        """
Repository
    ↓
Architecture Snapshot
    ↓
Components
    ↓
Relationships
    ↓
Normalized Architecture
    ↓
Architecture Graph
    ↓
Snapshot Comparison
    ↓
Architecture Health
    ↓
Risk Detection
        """,
        language="text",
    )

    st.info(
        "This dashboard reads the existing SQLite database. "
        "It does not modify database records."
    )


# ============================================================
# REPOSITORIES
# ============================================================

def show_repositories():

    st.title("📦 Repositories")

    repositories = get_repositories()

    if not repositories:

        st.warning(
            "No repositories found."
        )

        return

    st.write(
        f"Rows returned: **{len(repositories)}**"
    )

    st.dataframe(
        repositories,
        width="stretch",
        hide_index=True,
    )


# ============================================================
# SNAPSHOTS
# ============================================================

def show_snapshots():

    st.title("📸 Architecture Snapshots")

    snapshots = get_snapshots()

    if not snapshots:

        st.warning(
            "No snapshots found."
        )

        return

    st.write(
        f"Rows returned: **{len(snapshots)}**"
    )

    st.dataframe(
        snapshots,
        width="stretch",
        hide_index=True,
    )


# ============================================================
# COMPONENTS
# ============================================================

def show_components():

    st.title("🧩 Components")

    snapshots = get_snapshots()

    if not snapshots:

        st.warning(
            "No snapshots found."
        )

        return

    snapshot_options = {
        "All snapshots": None
    }

    for snapshot in snapshots:

        snapshot_options[
            snapshot_label(snapshot)
        ] = snapshot["id"]

    selected_label = st.selectbox(
        "Snapshot",
        list(snapshot_options.keys()),
    )

    selected_snapshot = snapshot_options[
        selected_label
    ]

    components = get_components(
        selected_snapshot
    )

    st.write(
        f"Rows returned: **{len(components)}**"
    )

    if not components:

        st.info(
            "No components found."
        )

        return

    st.dataframe(
        components,
        width="stretch",
        hide_index=True,
    )


# ============================================================
# RELATIONSHIPS
# ============================================================

def show_relationships():

    st.title(
        "🔗 Architecture Relationships"
    )

    snapshots = get_snapshots()

    if not snapshots:

        st.warning(
            "No snapshots found."
        )

        return

    snapshot_map = {
        snapshot_label(snapshot): snapshot["id"]
        for snapshot in snapshots
    }

    selected_label = st.selectbox(
        "Snapshot",
        list(snapshot_map.keys()),
        key="relationship_snapshot",
    )

    snapshot_id = snapshot_map[
        selected_label
    ]

    st.subheader(
        "Normalized Relationships"
    )

    st.caption(
        "The database is not modified. "
        "References such as `component_parser` "
        "are resolved to the component name `Parser`."
    )

    normalized = get_normalized_relationships(
        snapshot_id
    )

    if not normalized:

        st.info(
            "No relationships found for this snapshot."
        )

        return

    display_rows = []

    for relationship in normalized:

        display_rows.append(
            {
                "Source": relationship["source"],
                "Target": relationship["target"],
                "Relationship": (
                    relationship[
                        "relationship_type"
                    ]
                    if relationship[
                        "relationship_type"
                    ]
                    else "—"
                ),
            }
        )

    st.dataframe(
        display_rows,
        width="stretch",
        hide_index=True,
    )

    st.subheader(
        "Relationship Summary"
    )

    col1, col2, col3 = st.columns(3)

    unique_sources = {
        row["Source"]
        for row in display_rows
    }

    unique_targets = {
        row["Target"]
        for row in display_rows
    }

    with col1:

        st.metric(
            "Relationships",
            len(display_rows),
        )

    with col2:

        st.metric(
            "Sources",
            len(unique_sources),
        )

    with col3:

        st.metric(
            "Targets",
            len(unique_targets),
        )

    with st.expander(
        "Show raw database relationships"
    ):

        raw = get_relationships(
            snapshot_id
        )

        st.dataframe(
            raw,
            width="stretch",
            hide_index=True,
        )


# ============================================================
# ARCHITECTURE GRAPH
# ============================================================

def show_architecture_graph():

    st.title(
        "🕸️ Architecture Graph"
    )

    snapshots = get_snapshots()

    if not snapshots:

        st.warning(
            "No snapshots found."
        )

        return

    snapshot_map = {
        snapshot_label(snapshot): snapshot["id"]
        for snapshot in snapshots
    }

    selected_label = st.selectbox(
        "Snapshot",
        list(snapshot_map.keys()),
        key="graph_snapshot",
    )

    snapshot_id = snapshot_map[
        selected_label
    ]

    components = get_components(
        snapshot_id
    )

    relationships = get_normalized_relationships(
        snapshot_id
    )

    if not components:

        st.warning(
            "No components found for this snapshot."
        )

        return

    st.subheader(
        "Architecture"
    )

    component_names_list = [
        component["name"]
        for component in components
        if component["name"]
    ]

    unique_component_names = list(
        dict.fromkeys(
            component_names_list
        )
    )

    node_ids = {}

    for index, name in enumerate(
        unique_component_names
    ):

        node_ids[name] = f"node{index}"

    mermaid_lines = [
        "graph TD"
    ]

    for name in unique_component_names:

        safe_name = str(name).replace(
            '"',
            "'",
        )

        mermaid_lines.append(
            f'{node_ids[name]}["{safe_name}"]'
        )

    seen_edges = set()

    for relationship in relationships:

        source = relationship["source"]
        target = relationship["target"]

        if source not in node_ids:
            continue

        if target not in node_ids:
            continue

        edge = (
            node_ids[source],
            node_ids[target],
        )

        if edge in seen_edges:
            continue

        seen_edges.add(edge)

        mermaid_lines.append(
            f"{node_ids[source]} --> "
            f"{node_ids[target]}"
        )

    mermaid_code = "\n".join(
        mermaid_lines
    )

    st.components.v1.html(
        f"""
        <html>
        <head>
        <script type="module">
        import mermaid from
        'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';

        mermaid.initialize({{
            startOnLoad: true,
            securityLevel: 'loose',
            theme: 'default'
        }});
        </script>
        </head>

        <body>
        <div class="mermaid">
        {mermaid_code}
        </div>
        </body>
        </html>
        """,
        height=700,
        scrolling=True,
    )

    st.divider()

    st.subheader(
        "Graph Data"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Components",
            len(unique_component_names),
        )

    with col2:

        st.metric(
            "Relationships",
            len(seen_edges),
        )

    with col3:

        isolated = set(
            unique_component_names
        )

        for relationship in relationships:

            isolated.discard(
                relationship["source"]
            )

            isolated.discard(
                relationship["target"]
            )

        st.metric(
            "Isolated Components",
            len(isolated),
        )

    with st.expander(
        "Show normalized graph relationships"
    ):

        graph_rows = []

        for relationship in relationships:

            graph_rows.append(
                {
                    "Source": relationship["source"],
                    "Target": relationship["target"],
                    "Relationship": (
                        relationship[
                            "relationship_type"
                        ]
                        if relationship[
                            "relationship_type"
                        ]
                        else "—"
                    ),
                }
            )

        st.dataframe(
            graph_rows,
            width="stretch",
            hide_index=True,
        )


# ============================================================
# SNAPSHOT COMPARISON
# ============================================================

def show_snapshot_comparison():

    st.title(
        "🔄 Snapshot Comparison"
    )

    st.markdown(
        """
        Compare two architecture snapshots to identify:

        - Added components
        - Removed components
        - Unchanged components
        - Added relationships
        - Removed relationships
        """
    )

    snapshots = get_snapshots()

    if len(snapshots) < 2:

        st.warning(
            "At least two snapshots are required."
        )

        return

    snapshot_labels = [
        snapshot_label(snapshot)
        for snapshot in snapshots
    ]

    snapshot_lookup = {
        snapshot_label(snapshot): snapshot
        for snapshot in snapshots
    }

    col1, col2 = st.columns(2)

    with col1:

        before_label = st.selectbox(
            "Older snapshot",
            snapshot_labels,
            index=0,
            key="comparison_before",
        )

    with col2:

        after_default = (
            1
            if len(snapshot_labels) > 1
            else 0
        )

        after_label = st.selectbox(
            "Newer snapshot",
            snapshot_labels,
            index=after_default,
            key="comparison_after",
        )

    before_snapshot = snapshot_lookup[
        before_label
    ]

    after_snapshot = snapshot_lookup[
        after_label
    ]

    before_id = before_snapshot["id"]
    after_id = after_snapshot["id"]

    st.divider()

    if before_id == after_id:

        st.warning(
            "Choose two different snapshots."
        )

        return

    changes = calculate_change_metrics(
        before_id,
        after_id,
    )

    added_components = sorted(
        changes["added_components"],
        key=str.lower,
    )

    removed_components = sorted(
        changes["removed_components"],
        key=str.lower,
    )

    unchanged_components = sorted(
        changes["unchanged_components"],
        key=str.lower,
    )

    added_relationships = sorted(
        changes["added_relationships"],
        key=lambda item: (
            str(item[0]).lower(),
            str(item[1]).lower(),
        ),
    )

    removed_relationships = sorted(
        changes["removed_relationships"],
        key=lambda item: (
            str(item[0]).lower(),
            str(item[1]).lower(),
        ),
    )

    unchanged_relationships = sorted(
        changes["unchanged_relationships"],
        key=lambda item: (
            str(item[0]).lower(),
            str(item[1]).lower(),
        ),
    )

    st.subheader(
        "Component Changes"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Added",
            len(added_components),
        )

    with col2:

        st.metric(
            "Removed",
            len(removed_components),
        )

    with col3:

        st.metric(
            "Unchanged",
            len(unchanged_components),
        )

    change_col1, change_col2 = st.columns(2)

    with change_col1:

        st.markdown(
            "### 🟢 Added Components"
        )

        if added_components:

            for component in added_components:
                st.write(
                    f"＋ {component}"
                )

        else:

            st.success(
                "No components added."
            )

    with change_col2:

        st.markdown(
            "### 🔴 Removed Components"
        )

        if removed_components:

            for component in removed_components:
                st.write(
                    f"− {component}"
                )

        else:

            st.success(
                "No components removed."
            )

    with st.expander(
        "Show unchanged components"
    ):

        for component in unchanged_components:

            st.write(
                f"= {component}"
            )

    st.divider()

    st.subheader(
        "Relationship Changes"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Added Relationships",
            len(added_relationships),
        )

    with col2:

        st.metric(
            "Removed Relationships",
            len(removed_relationships),
        )

    with col3:

        st.metric(
            "Unchanged Relationships",
            len(unchanged_relationships),
        )

    rel_col1, rel_col2 = st.columns(2)

    with rel_col1:

        st.markdown(
            "### 🟢 Added Relationships"
        )

        if added_relationships:

            for (
                source,
                target,
                relationship_type,
            ) in added_relationships:

                relationship_text = (
                    relationship_type
                    if relationship_type
                    else "relationship"
                )

                st.write(
                    f"＋ **{source}** → "
                    f"**{target}** "
                    f"({relationship_text})"
                )

        else:

            st.success(
                "No relationships added."
            )

    with rel_col2:

        st.markdown(
            "### 🔴 Removed Relationships"
        )

        if removed_relationships:

            for (
                source,
                target,
                relationship_type,
            ) in removed_relationships:

                relationship_text = (
                    relationship_type
                    if relationship_type
                    else "relationship"
                )

                st.write(
                    f"− **{source}** → "
                    f"**{target}** "
                    f"({relationship_text})"
                )

        else:

            st.success(
                "No relationships removed."
            )

    with st.expander(
        "Show unchanged relationships"
    ):

        for (
            source,
            target,
            relationship_type,
        ) in unchanged_relationships:

            relationship_text = (
                relationship_type
                if relationship_type
                else "relationship"
            )

            st.write(
                f"= **{source}** → "
                f"**{target}** "
                f"({relationship_text})"
            )

    st.divider()

    st.subheader(
        "Evolution Summary"
    )

    component_changes = (
        len(added_components)
        + len(removed_components)
    )

    relationship_changes = (
        len(added_relationships)
        + len(removed_relationships)
    )

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Component Changes",
            component_changes,
        )

    with col2:

        st.metric(
            "Relationship Changes",
            relationship_changes,
        )

    if (
        component_changes == 0
        and relationship_changes == 0
    ):

        st.success(
            "No architectural changes detected."
        )

    else:

        st.info(
            "Architectural changes were detected."
        )


# ============================================================
# ARCHITECTURE HEALTH
# ============================================================

def show_architecture_health():

    st.title(
        "❤️ Architecture Health"
    )

    st.markdown(
        """
        This page calculates structural metrics from the
        architecture graph.

        It currently focuses on **coupling and connectivity**.
        These are measurements, not yet automated diagnoses.
        """
    )

    snapshots = get_snapshots()

    if not snapshots:

        st.warning(
            "No snapshots found."
        )

        return

    snapshot_map = {
        snapshot_label(snapshot): snapshot["id"]
        for snapshot in snapshots
    }

    selected_label = st.selectbox(
        "Analyze snapshot",
        list(snapshot_map.keys()),
        key="health_snapshot",
    )

    snapshot_id = snapshot_map[
        selected_label
    ]

    health = calculate_architecture_health(
        snapshot_id
    )

    st.divider()

    # --------------------------------------------------------
    # TOP LEVEL METRICS
    # --------------------------------------------------------

    st.subheader(
        "Architecture Metrics"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Components",
            health["component_count"],
        )

    with col2:

        st.metric(
            "Relationships",
            health["relationship_count"],
        )

    with col3:

        st.metric(
            "Average Fan-out",
            f"{health['average_fan_out']:.2f}",
        )

    with col4:

        st.metric(
            "Isolated Components",
            len(
                health[
                    "isolated_components"
                ]
            ),
        )

    # --------------------------------------------------------
    # EXPLANATION
    # --------------------------------------------------------

    st.subheader(
        "What the metrics mean"
    )

    st.markdown(
        """
        **Fan-in** = number of incoming relationships.

        **Fan-out** = number of outgoing relationships.

        **Total connections** = fan-in + fan-out.

        A high fan-out component may be a strong dependency
        point. A high fan-in component may be heavily relied upon.
        """
    )

    # --------------------------------------------------------
    # COMPONENT METRICS
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "Component Connectivity"
    )

    metrics = health[
        "component_metrics"
    ]

    if metrics:

        st.dataframe(
            metrics,
            width="stretch",
            hide_index=True,
        )

    else:

        st.info(
            "No component metrics available."
        )

    # --------------------------------------------------------
    # HUB ANALYSIS
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "Architectural Hubs"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.markdown(
            "### 📥 Highest Fan-in"
        )

        if health["fan_in_hubs"]:

            st.metric(
                "Fan-in",
                health["highest_fan_in"],
            )

            for component in health[
                "fan_in_hubs"
            ]:

                st.write(
                    f"• {component}"
                )

        else:

            st.info(
                "No incoming relationships."
            )

    with col2:

        st.markdown(
            "### 📤 Highest Fan-out"
        )

        if health["fan_out_hubs"]:

            st.metric(
                "Fan-out",
                health["highest_fan_out"],
            )

            for component in health[
                "fan_out_hubs"
            ]:

                st.write(
                    f"• {component}"
                )

        else:

            st.info(
                "No outgoing relationships."
            )

    with col3:

        st.markdown(
            "### 🔗 Most Connected"
        )

        if health["connection_hubs"]:

            st.metric(
                "Connections",
                health["highest_connection"],
            )

            for component in health[
                "connection_hubs"
            ]:

                st.write(
                    f"• {component}"
                )

        else:

            st.info(
                "No connected components."
            )

    # --------------------------------------------------------
    # ISOLATED COMPONENTS
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "Isolated Components"
    )

    isolated = health[
        "isolated_components"
    ]

    if isolated:

        st.warning(
            f"{len(isolated)} isolated "
            "component(s) detected."
        )

        for component in isolated:

            st.write(
                f"⚪ {component}"
            )

    else:

        st.success(
            "No isolated components detected."
        )

    # --------------------------------------------------------
    # RISK SIGNALS
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "Structural Signals"
    )

    signals = []

    if (
        health["highest_fan_out"] >= 5
    ):

        signals.append(
            (
                "High fan-out",
                "A component has 5 or more outgoing "
                "relationships."
            )
        )

    if (
        health["highest_fan_in"] >= 5
    ):

        signals.append(
            (
                "High fan-in",
                "A component has 5 or more incoming "
                "relationships."
            )
        )

    if (
        len(
            health[
                "isolated_components"
            ]
        )
        > 0
    ):

        signals.append(
            (
                "Isolated components",
                "One or more components have no "
                "incoming or outgoing relationships."
            )
        )

    if (
        health["component_count"] > 0
        and health["relationship_count"] == 0
    ):

        signals.append(
            (
                "Disconnected architecture",
                "Components exist but no relationships "
                "were detected."
            )
        )

    if signals:

        for title, description in signals:

            st.warning(
                f"**{title}:** {description}"
            )

    else:

        st.success(
            "No basic structural warning signals "
            "were detected."
        )

    # --------------------------------------------------------
    # CHANGE SINCE PREVIOUS SNAPSHOT
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "Evolution Since Previous Snapshot"
    )

    current_index = next(
        (
            index
            for index, snapshot in enumerate(
                snapshots
            )
            if snapshot["id"] == snapshot_id
        ),
        None,
    )

    if (
        current_index is None
        or current_index == 0
    ):

        st.info(
            "This is the first available snapshot, "
            "so there is no previous snapshot to compare."
        )

    else:

        previous_snapshot = snapshots[
            current_index - 1
        ]

        previous_id = previous_snapshot[
            "id"
        ]

        previous_health = (
            calculate_architecture_health(
                previous_id
            )
        )

        component_delta = (
            health["component_count"]
            - previous_health[
                "component_count"
            ]
        )

        relationship_delta = (
            health["relationship_count"]
            - previous_health[
                "relationship_count"
            ]
        )

        fan_out_delta = (
            health["average_fan_out"]
            - previous_health[
                "average_fan_out"
            ]
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "Component Change",
                health["component_count"],
                delta=component_delta,
            )

        with col2:

            st.metric(
                "Relationship Change",
                health["relationship_count"],
                delta=relationship_delta,
            )

        with col3:

            st.metric(
                "Average Fan-out",
                f"{health['average_fan_out']:.2f}",
                delta=f"{fan_out_delta:+.2f}",
            )

        st.caption(
            f"Compared with "
            f"{snapshot_label(previous_snapshot)}."
        )


# ============================================================
# DATABASE TEST
# ============================================================

def show_database_test():

    st.title(
        "🧪 Database Test"
    )

    st.write(
        "Database path:"
    )

    st.code(
        str(DATABASE_PATH)
    )

    if not database_exists():

        st.error(
            "Database does not exist."
        )

        return

    try:

        connection = get_connection()

        st.success(
            "DATABASE CONNECTED"
        )

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        connection.close()

        st.write(
            "Integrity check:"
        )

        st.code(
            str(integrity)
        )

        tables = get_tables()

        st.subheader(
            "Tables"
        )

        for table in tables:

            st.write(
                f"- {table}"
            )

        st.subheader(
            "Table Counts"
        )

        for table in tables:

            if table == "sqlite_sequence":
                continue

            st.write(
                f"**{table}:** "
                f"{get_table_count(table)} rows"
            )

    except Exception as error:

        st.error(
            f"DATABASE ERROR: {repr(error)}"
        )


# ============================================================
# SIDEBAR
# ============================================================

show_database_status()

st.sidebar.divider()

st.sidebar.title(
    "Navigation"
)

page = st.sidebar.radio(
    "Go to",
    [
        "Overview",
        "Repositories",
        "Snapshots",
        "Components",
        "Relationships",
        "Architecture Graph",
        "Snapshot Comparison",
        "Architecture Health",
        "Database Test",
        "Architecture History",

    ],
)


# ============================================================
# ROUTING
# ============================================================

try:

    if page == "Overview":
        show_overview()

    elif page == "Repositories":
        show_repositories()

    elif page == "Snapshots":
        show_snapshots()

    elif page == "Components":
        show_components()

    elif page == "Relationships":
        show_relationships()

    elif page == "Architecture Graph":
        show_architecture_graph()

    elif page == "Snapshot Comparison":
        show_snapshot_comparison()

    elif page == "Architecture Health":
        show_architecture_health()

    elif page == "Database Test":
        show_database_test()

    elif page == "Architecture History":
        render_architecture_history()

except sqlite3.Error as error:

    st.error(
        f"Database error: {repr(error)}"
    )

except Exception as error:

    st.error(
        f"Application error: {repr(error)}"
    )