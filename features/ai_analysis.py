import streamlit as st

from architecture_model.ai_analyzer import analyze_architecture
from database.repository import get_snapshots


def _snapshot_value(snapshot, key, default=None):
    """
    Safely read a value from a sqlite3.Row or dictionary.
    """
    try:
        return snapshot[key]
    except (KeyError, IndexError):
        return default


def _snapshot_label(snapshot):
    snapshot_id = _snapshot_value(
        snapshot,
        "id",
        "N/A",
    )

    commit_hash = _snapshot_value(
        snapshot,
        "commit_hash",
        "N/A",
    )

    return (
        f"Snapshot {snapshot_id} | "
        f"Commit: {commit_hash}"
    )


def _snapshot_to_dict(snapshot):
    """
    Convert sqlite3.Row into a normal dictionary.
    """

    return {
        key: snapshot[key]
        for key in snapshot.keys()
    }


def _build_ai_input(
    old_snapshot,
    new_snapshot,
):
    """
    Build a compact architecture input
    for the AI analyzer.
    """

    old_data = _snapshot_to_dict(
        old_snapshot
    )

    new_data = _snapshot_to_dict(
        new_snapshot
    )

    return {
        "snapshot": {
            "older": old_data,
            "newer": new_data,
        },
        "components": [],
        "relationships": [],
        "changes": [
            (
                f"Architecture comparison between "
                f"snapshot "
                f"{_snapshot_value(old_snapshot, 'id')} "
                f"and snapshot "
                f"{_snapshot_value(new_snapshot, 'id')}."
            )
        ],
    }


def render_ai_analysis():

    st.title(
        "🤖 AI Architecture Analysis"
    )

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

    # --------------------------------------------------------
    # SNAPSHOT SELECTION
    # --------------------------------------------------------

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

    old_snapshot = snapshot_lookup[
        old_label
    ]

    new_snapshot = snapshot_lookup[
        new_label
    ]

    old_id = _snapshot_value(
        old_snapshot,
        "id",
    )

    new_id = _snapshot_value(
        new_snapshot,
        "id",
    )

    if old_id == new_id:

        st.warning(
            "Choose two different snapshots."
        )

        return

    # --------------------------------------------------------
    # IMPROVEMENTS
    # --------------------------------------------------------

    if st.button(
        "🔍 Show Improvements",
        key="ai_show_improvements",
    ):

        st.subheader(
            "Architecture Improvements"
        )

        st.info(
            "The selected snapshots are:"
        )

        st.write(
            f"Older snapshot: **{old_id}**"
        )

        st.write(
            f"Newer snapshot: **{new_id}**"
        )

        st.markdown(
            """
            The selected snapshots represent an
            architectural evolution. The AI analysis
            below can be used to interpret the observed
            architectural changes.
            """
        )

    # --------------------------------------------------------
    # AI ANALYSIS
    # --------------------------------------------------------

    if st.button(
        "🤖 Analyze Architecture",
        key="run_ai_analysis",
    ):

        architecture_data = (
            _build_ai_input(
                old_snapshot,
                new_snapshot,
            )
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