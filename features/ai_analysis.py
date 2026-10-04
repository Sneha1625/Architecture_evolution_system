import streamlit as st

from architecture_model.ai_analyzer import analyze_architecture
from database.repository import get_snapshots


def _snapshot_value(snapshot, key, default=None):
    try:
        return snapshot[key]
    except (KeyError, IndexError):
        return default


def _snapshot_label(snapshot):
    snapshot_id = _snapshot_value(snapshot, "id", "N/A")
    commit_hash = _snapshot_value(snapshot, "commit_hash", "N/A")
    return f"Snapshot {snapshot_id} | Commit: {commit_hash}"


def _snapshot_to_dict(snapshot):
    return {
        key: snapshot[key]
        for key in snapshot.keys()
    }


def _build_ai_input(old_snapshot, new_snapshot):
    old_data = _snapshot_to_dict(old_snapshot)
    new_data = _snapshot_to_dict(new_snapshot)

    return {
        "snapshot": {
            "older": old_data,
            "newer": new_data,
        },
        "components": [],
        "relationships": [],
        "changes": [
            f"Architecture comparison between snapshot "
            f"{_snapshot_value(old_snapshot, 'id')} and snapshot "
            f"{_snapshot_value(new_snapshot, 'id')}."
        ],
    }


def _get_architecture_data(snapshot):
    data = _snapshot_to_dict(snapshot)

    architecture = data.get("architecture")

    if isinstance(architecture, dict):
        return architecture

    return {}


def _get_components(snapshot):
    architecture = _get_architecture_data(snapshot)

    components = architecture.get("components", [])

    if isinstance(components, dict):
        return list(components.keys())

    if isinstance(components, list):
        result = []

        for component in components:
            if isinstance(component, dict):
                name = (
                    component.get("name")
                    or component.get("id")
                    or component.get("component")
                )

                if name:
                    result.append(str(name))

            elif component:
                result.append(str(component))

        return result

    return []


def _get_relationships(snapshot):
    architecture = _get_architecture_data(snapshot)

    relationships = architecture.get("relationships", [])

    result = []

    if isinstance(relationships, dict):
        relationships = list(relationships.values())

    if not isinstance(relationships, list):
        return result

    for relationship in relationships:
        if isinstance(relationship, dict):
            source = (
                relationship.get("source")
                or relationship.get("from")
                or relationship.get("caller")
            )

            target = (
                relationship.get("target")
                or relationship.get("to")
                or relationship.get("callee")
            )

            relationship_type = (
                relationship.get("type")
                or relationship.get("relationship_type")
                or ""
            )

            if source and target:
                result.append(
                    f"{source} -> {target}"
                    + (
                        f" ({relationship_type})"
                        if relationship_type
                        else ""
                    )
                )

        elif relationship:
            result.append(str(relationship))

    return result


def _compare_snapshots(old_snapshot, new_snapshot):
    old_components = set(_get_components(old_snapshot))
    new_components = set(_get_components(new_snapshot))

    old_relationships = set(
        _get_relationships(old_snapshot)
    )
    new_relationships = set(
        _get_relationships(new_snapshot)
    )

    return {
        "components_added": sorted(
            new_components - old_components
        ),
        "components_removed": sorted(
            old_components - new_components
        ),
        "components_unchanged": sorted(
            old_components & new_components
        ),
        "relationships_added": sorted(
            new_relationships - old_relationships
        ),
        "relationships_removed": sorted(
            old_relationships - new_relationships
        ),
        "relationships_unchanged": sorted(
            old_relationships & new_relationships
        ),
    }


def render_ai_analysis():

    st.title("🤖 AI Architecture Analysis")

    st.markdown(
        """
        Use AI to analyze the architectural evolution
        between two architecture snapshots.
        """
    )

    snapshots = get_snapshots()

    if len(snapshots) < 2:
        st.warning(
            "At least two architecture snapshots "
            "are required for AI analysis."
        )
        return

    snapshot_labels = [
        _snapshot_label(snapshot)
        for snapshot in snapshots
    ]

    snapshot_lookup = {
        _snapshot_label(snapshot): snapshot
        for snapshot in snapshots
    }

    col1, col2 = st.columns(2)

    with col1:
        old_label = st.selectbox(
            "Older snapshot",
            snapshot_labels,
            index=0,
            key="ai_old_snapshot",
        )

    with col2:
        new_index = (
            1
            if len(snapshot_labels) > 1
            else 0
        )

        new_label = st.selectbox(
            "Newer snapshot",
            snapshot_labels,
            index=new_index,
            key="ai_new_snapshot",
        )

    old_snapshot = snapshot_lookup[old_label]
    new_snapshot = snapshot_lookup[new_label]

    old_id = _snapshot_value(old_snapshot, "id")
    new_id = _snapshot_value(new_snapshot, "id")

    if old_id == new_id:
        st.warning("Choose two different snapshots.")
        return

    if st.button(
        "🔍 Show Improvements",
        key="ai_show_improvements",
    ):

        comparison = _compare_snapshots(
            old_snapshot,
            new_snapshot,
        )

        st.subheader("Architecture Improvements")

        st.write(
            f"Comparing snapshot **{old_id}** "
            f"→ **{new_id}**"
        )

        st.markdown("### Before → After")

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Components",
                len(
                    comparison[
                        "components_unchanged"
                    ]
                )
                + len(
                    comparison[
                        "components_added"
                    ]
                ),
            )

            st.metric(
                "Relationships",
                len(
                    comparison[
                        "relationships_unchanged"
                    ]
                )
                + len(
                    comparison[
                        "relationships_added"
                    ]
                ),
            )

        with col2:
            component_delta = (
                len(
                    comparison[
                        "components_added"
                    ]
                )
                - len(
                    comparison[
                        "components_removed"
                    ]
                )
            )

            relationship_delta = (
                len(
                    comparison[
                        "relationships_added"
                    ]
                )
                - len(
                    comparison[
                        "relationships_removed"
                    ]
                )
            )

            st.metric(
                "Component Change",
                component_delta,
            )

            st.metric(
                "Relationship Change",
                relationship_delta,
            )

        st.markdown("### Improvements")

        improvements_found = False

        if comparison["components_added"]:
            improvements_found = True
            st.write("**Components added:**")

            for component in comparison[
                "components_added"
            ]:
                st.success(f"+ {component}")

        if comparison["relationships_added"]:
            improvements_found = True
            st.write("**Relationships added:**")

            for relationship in comparison[
                "relationships_added"
            ]:
                st.success(f"+ {relationship}")

        if not improvements_found:
            st.info(
                "No new components or relationships "
                "were detected between these snapshots."
            )

        st.markdown("### Removed / Regressions")

        removals_found = False

        if comparison["components_removed"]:
            removals_found = True
            st.write("**Components removed:**")

            for component in comparison[
                "components_removed"
            ]:
                st.warning(f"- {component}")

        if comparison["relationships_removed"]:
            removals_found = True
            st.write("**Relationships removed:**")

            for relationship in comparison[
                "relationships_removed"
            ]:
                st.warning(f"- {relationship}")

        if not removals_found:
            st.success(
                "No components or relationships were removed."
            )

        st.markdown("### Overall Evolution")

        total_changes = (
            len(comparison["components_added"])
            + len(comparison["components_removed"])
            + len(comparison["relationships_added"])
            + len(comparison["relationships_removed"])
        )

        if total_changes == 0:
            st.info(
                "No structural architecture changes "
                "were detected."
            )
        else:
            st.success(
                f"{total_changes} structural architecture "
                f"change(s) detected."
            )

    if st.button(
        "🤖 Analyze Architecture",
        key="run_ai_analysis",
    ):

        architecture_data = _build_ai_input(
            old_snapshot,
            new_snapshot,
        )

        with st.spinner(
            "Analyzing architecture..."
        ):

            try:
                result = analyze_architecture(
                    architecture_data
                )

                st.subheader(
                    "AI Architecture Analysis"
                )

                st.markdown(result)

            except Exception as error:
                st.error(
                    f"AI analysis failed: {error}"
                )
