"""
Runtime Architecture UI.

Runs dynamic analysis for the selected execution target and can compare
runtime architectures from two Git worktrees (V1 and V2).
"""

import streamlit as st

from architecture_model.runtime_analyzer import RuntimeAnalyzer
from architecture_model.runtime_comparator import compare_architectures
from architecture_model.runtime_evolution import (
    compare_runtime_architectures,
    get_runtime_evolution_summary,
)
from architecture_model.runtime_version_runner import run_version_pair
from features.runtime_mapping import build_runtime_component_map


# ============================================================
# RUNTIME EVOLUTION
# ============================================================


def _render_runtime_evolution():
    """
    Run the same runtime scenario against V1 and V2 and display
    runtime evolution information and charts.
    """

    st.markdown("---")

    st.subheader(
        "Runtime Architecture Evolution"
    )

    st.caption(
        "Run the same scenario against the V1 and V2 Git worktrees, "
        "then compare observed modules, relationships, call counts, "
        "and functions."
    )

    # --------------------------------------------------------
    # RUN COMPARISON
    # --------------------------------------------------------

    if not st.button(
        "Run V1 vs V2 Runtime Comparison",
        key="run_runtime_evolution",
    ):
        st.info(
            "Click the button above to execute and compare both versions."
        )
        return

    with st.spinner(
        "Executing the runtime scenario against V1 and V2..."
    ):

        try:

            versions = run_version_pair()

            comparison = compare_runtime_architectures(
                versions["v1_runtime"],
                versions["v2_runtime"],
                old_version=versions["v1_commit"],
                new_version=versions["v2_commit"],
            )

        except Exception as error:

            st.error(
                "Runtime evolution comparison failed."
            )

            st.exception(error)

            return

    # ========================================================
    # VERSIONS
    # ========================================================

    st.markdown(
        "#### Versions Compared"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "V1 Commit",
            versions["v1_commit"],
        )

    with col2:

        st.metric(
            "V2 Commit",
            versions["v2_commit"],
        )

    st.caption(
        f"Scenario: `{versions['scenario']}`"
    )

    # ========================================================
    # RUNTIME METRICS
    # ========================================================

    st.markdown(
        "#### Runtime Metrics"
    )

    old_runtime = comparison["old_runtime"]
    new_runtime = comparison["new_runtime"]

    metric_cols = st.columns(3)

    metric_cols[0].metric(
        "Modules",
        new_runtime["modules"],
        delta=(
            new_runtime["modules"]
            - old_runtime["modules"]
        ),
    )

    metric_cols[1].metric(
        "Relationships",
        new_runtime["relationships"],
        delta=(
            new_runtime["relationships"]
            - old_runtime["relationships"]
        ),
    )

    metric_cols[2].metric(
        "Profiled Calls",
        new_runtime["total_calls"],
        delta=comparison["call_difference"],
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    st.info(
        get_runtime_evolution_summary(
            comparison
        )
    )

    # ========================================================
    # CHART 1 - RUNTIME METRICS V1 VS V2
    # ========================================================

    st.markdown("---")

    st.markdown(
        "### 📊 Runtime Architecture Comparison"
    )

    st.caption(
        "Comparison of the runtime architecture size and execution "
        "activity between V1 and V2."
    )

    chart_data = {
        "V1": [
            old_runtime["modules"],
            old_runtime["relationships"],
            old_runtime["total_calls"],
        ],
        "V2": [
            new_runtime["modules"],
            new_runtime["relationships"],
            new_runtime["total_calls"],
        ],
    }

    st.bar_chart(
        chart_data,
        horizontal=False,
    )

    st.caption(
        "Chart order: Modules → Relationships → Profiled Calls"
    )

    # ========================================================
    # CHANGE COUNTS
    # ========================================================

    summary = comparison["summary"]

    st.markdown(
        "#### Change Counts"
    )

    cols = st.columns(3)

    cols[0].metric(
        "Modules Added",
        summary["modules_added"],
    )

    cols[1].metric(
        "Modules Removed",
        summary["modules_removed"],
    )

    cols[2].metric(
        "Relationship Additions",
        summary["relationships_added"],
    )

    cols = st.columns(3)

    cols[0].metric(
        "Relationship Removals",
        summary["relationships_removed"],
    )

    cols[1].metric(
        "Call-Count Changes",
        summary["call_count_changes"],
    )

    cols[2].metric(
        "Function Changes",
        summary["function_changes"],
    )

    # ========================================================
    # MODULE CHANGES
    # ========================================================

    module_changes = comparison[
        "module_changes"
    ]

    with st.expander(
        "Module Changes",
        expanded=True,
    ):

        st.markdown(
            "**Added**"
        )

        if module_changes["added"]:

            for module in module_changes["added"]:

                st.write(
                    f"+ `{module}`"
                )

        else:

            st.write(
                "None"
            )

        st.markdown(
            "**Removed**"
        )

        if module_changes["removed"]:

            for module in module_changes["removed"]:

                st.write(
                    f"- `{module}`"
                )

        else:

            st.write(
                "None"
            )

        st.markdown(
            "**Present in Both Versions**"
        )

        if module_changes["common"]:

            st.write(
                ", ".join(
                    f"`{module}`"
                    for module in module_changes["common"]
                )
            )

        else:

            st.write(
                "None"
            )

    # ========================================================
    # RELATIONSHIP CHANGES
    # ========================================================

    relationship_changes = comparison[
        "relationship_changes"
    ]

    # --------------------------------------------------------
    # ADDED RELATIONSHIPS
    # --------------------------------------------------------

    with st.expander(
        "Runtime Relationships Added",
        expanded=True,
    ):

        if relationship_changes["added"]:

            for relationship in relationship_changes["added"]:

                st.write(
                    f"+ **{relationship['source']} → "
                    f"{relationship['target']}** "
                    f"({relationship['call_count']} calls)"
                )

                if relationship["functions"]:

                    st.caption(
                        "Functions: "
                        + ", ".join(
                            relationship["functions"]
                        )
                    )

        else:

            st.write(
                "None"
            )

    # --------------------------------------------------------
    # REMOVED RELATIONSHIPS
    # --------------------------------------------------------

    with st.expander(
        "Runtime Relationships Removed",
        expanded=True,
    ):

        if relationship_changes["removed"]:

            for relationship in relationship_changes["removed"]:

                st.write(
                    f"- **{relationship['source']} → "
                    f"{relationship['target']}** "
                    f"({relationship['call_count']} calls)"
                )

                if relationship["functions"]:

                    st.caption(
                        "Functions: "
                        + ", ".join(
                            relationship["functions"]
                        )
                    )

        else:

            st.write(
                "None"
            )

    # --------------------------------------------------------
    # CALL COUNT CHANGES
    # --------------------------------------------------------

    with st.expander(
        "Relationship Call-Count Changes",
        expanded=True,
    ):

        if relationship_changes[
            "call_count_changes"
        ]:

            for change in relationship_changes[
                "call_count_changes"
            ]:

                st.write(
                    f"**{change['source']} → "
                    f"{change['target']}**: "
                    f"{change['old_call_count']} → "
                    f"{change['new_call_count']} "
                    f"(difference: "
                    f"{change['difference']:+d})"
                )

        else:

            st.write(
                "None"
            )

    # ========================================================
    # CHART 2 - RELATIONSHIP CALL COUNTS
    # ========================================================

    call_count_changes = relationship_changes[
        "call_count_changes"
    ]

    if call_count_changes:

        st.markdown("---")

        st.markdown(
            "### 📈 Runtime Relationship Call Counts"
        )

        st.caption(
            "Runtime calls for relationships whose call count "
            "changed between V1 and V2."
        )

        relationship_labels = []
        v1_calls = []
        v2_calls = []

        for change in call_count_changes:

            label = (
                f"{change['source']} → "
                f"{change['target']}"
            )

            relationship_labels.append(
                label
            )

            v1_calls.append(
                change["old_call_count"]
            )

            v2_calls.append(
                change["new_call_count"]
            )

        relationship_chart_data = {
            "V1": v1_calls,
            "V2": v2_calls,
        }

        st.bar_chart(
            relationship_chart_data,
            horizontal=False,
        )

        st.caption(
            "Bars are shown in the same order as the relationship "
            "changes listed below."
        )

        with st.expander(
            "Chart Relationship Labels",
            expanded=False,
        ):

            for index, label in enumerate(
                relationship_labels,
                start=1,
            ):

                st.write(
                    f"{index}. `{label}`"
                )

    # ========================================================
    # FUNCTION LEVEL CHANGES
    # ========================================================

    with st.expander(
        "Function-Level Changes",
        expanded=True,
    ):

        if relationship_changes[
            "function_changes"
        ]:

            for change in relationship_changes[
                "function_changes"
            ]:

                st.markdown(
                    f"**{change['source']} → "
                    f"{change['target']}**"
                )

                if change[
                    "added_functions"
                ]:

                    st.write(
                        "Added functions: "
                        + ", ".join(
                            change[
                                "added_functions"
                            ]
                        )
                    )

                if change[
                    "removed_functions"
                ]:

                    st.write(
                        "Removed functions: "
                        + ", ".join(
                            change[
                                "removed_functions"
                            ]
                        )
                    )

        else:

            st.write(
                "None"
            )


# ============================================================
# RUNTIME ARCHITECTURE
# ============================================================


def render_runtime_architecture(
    static_relationships=None,
    static_components=None,
    target=None,
    include_prefixes=None,
):
    """
    Render runtime architecture analysis.

    Parameters
    ----------
    static_relationships:
        Relationships from the selected static architecture snapshot.

    static_components:
        Components from the selected static architecture snapshot.

    target:
        Callable to execute while collecting runtime calls.

    include_prefixes:
        Python module prefixes to trace.
    """

    st.subheader(
        "Dynamic / Runtime Architecture"
    )

    st.caption(
        "Runtime relationships observed during execution."
    )

    # --------------------------------------------------------
    # NO TARGET
    # --------------------------------------------------------

    if target is None:

        st.info(
            "No runtime execution target has been configured."
        )

        _render_runtime_evolution()

        return

    # --------------------------------------------------------
    # DEFAULT PREFIXES
    # --------------------------------------------------------

    if include_prefixes is None:

        include_prefixes = [
            "features",
            "src",
            "architecture_model",
        ]

    # --------------------------------------------------------
    # RUN BUTTON
    # --------------------------------------------------------

    if not st.button(
        "Run Runtime Analysis",
        key="run_runtime_analysis",
    ):

        st.info(
            "Click 'Run Runtime Analysis' "
            "to observe runtime behavior."
        )

    else:

        analyzer = RuntimeAnalyzer(
            include_prefixes=include_prefixes
        )

        with st.spinner(
            "Tracing runtime architecture..."
        ):

            try:

                runtime_architecture = analyzer.run(
                    target,
                    entry_point=(
                        "architecture_runtime_analysis"
                    ),
                )

            except Exception as error:

                st.error(
                    "Runtime analysis failed."
                )

                st.exception(
                    error
                )

                runtime_architecture = None

        # ----------------------------------------------------
        # DISPLAY RUNTIME RESULTS
        # ----------------------------------------------------

        if runtime_architecture is not None:

            st.markdown(
                "### Runtime Summary"
            )

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Runtime Modules",
                runtime_architecture.get_module_count(),
            )

            col2.metric(
                "Runtime Relationships",
                runtime_architecture.get_relationship_count(),
            )

            col3.metric(
                "Function Calls",
                runtime_architecture.total_calls,
            )

            # ------------------------------------------------
            # OBSERVED MODULES
            # ------------------------------------------------

            if runtime_architecture.modules:

                with st.expander(
                    "Observed Runtime Modules",
                    expanded=False,
                ):

                    for module in sorted(
                        runtime_architecture.modules
                    ):

                        st.write(
                            f"`{module}`"
                        )

            # ------------------------------------------------
            # RUNTIME RELATIONSHIPS
            # ------------------------------------------------

            relationships = (
                runtime_architecture.get_relationships()
            )

            st.markdown(
                "### Observed Runtime Relationships"
            )

            if not relationships:

                st.info(
                    "No cross-module runtime relationships "
                    "were observed."
                )

            else:

                for relationship in sorted(
                    relationships,
                    key=lambda item: item.call_count,
                    reverse=True,
                ):

                    st.write(
                        f"**{relationship.source} → "
                        f"{relationship.target}** "
                        f"({relationship.call_count} calls)"
                    )

                    if relationship.functions:

                        st.caption(
                            "Functions: "
                            + ", ".join(
                                sorted(
                                    relationship.functions
                                )
                            )
                        )

            # ------------------------------------------------
            # STATIC VS RUNTIME
            # ------------------------------------------------

            if static_relationships is not None:

                static_component_map = {}
                runtime_component_map = {}

                if static_components:

                    for component in static_components:

                        if component.id:

                            static_component_map[
                                component.id
                            ] = component.name

                    runtime_component_map = (
                        build_runtime_component_map(
                            static_components
                        )
                    )

                comparison = compare_architectures(
                    static_relationships,
                    relationships,
                    static_component_map=(
                        static_component_map
                    ),
                    runtime_component_map=(
                        runtime_component_map
                    ),
                )

                st.markdown(
                    "---"
                )

                st.markdown(
                    "### Static vs Runtime Architecture"
                )

                col1, col2, col3 = st.columns(3)

                col1.metric(
                    "Static Only",
                    len(
                        comparison["static_only"]
                    ),
                )

                col2.metric(
                    "Both",
                    len(
                        comparison["both"]
                    ),
                )

                col3.metric(
                    "Runtime Only",
                    len(
                        comparison["runtime_only"]
                    ),
                )

                # --------------------------------------------
                # STATIC ONLY
                # --------------------------------------------

                with st.expander(
                    "Static Relationships Not Observed at Runtime",
                    expanded=False,
                ):

                    if comparison[
                        "static_only"
                    ]:

                        for source, target_name in comparison[
                            "static_only"
                        ]:

                            st.write(
                                f"`{source}` → "
                                f"`{target_name}`"
                            )

                    else:

                        st.success(
                            "All static relationships "
                            "were observed."
                        )

                # --------------------------------------------
                # BOTH
                # --------------------------------------------

                with st.expander(
                    "Relationships Observed Both "
                    "Statically and at Runtime",
                    expanded=True,
                ):

                    if comparison[
                        "both"
                    ]:

                        for source, target_name in comparison[
                            "both"
                        ]:

                            st.write(
                                f"`{source}` → "
                                f"`{target_name}`"
                            )

                    else:

                        st.info(
                            "No matching static/runtime "
                            "relationships found."
                        )

                # --------------------------------------------
                # RUNTIME ONLY
                # --------------------------------------------

                with st.expander(
                    "Runtime Relationships Not "
                    "in Static Model",
                    expanded=True,
                ):

                    if comparison[
                        "runtime_only"
                    ]:

                        for source, target_name in comparison[
                            "runtime_only"
                        ]:

                            st.write(
                                f"`{source}` → "
                                f"`{target_name}`"
                            )

                    else:

                        st.info(
                            "No runtime-only relationships detected."
                        )

    # ========================================================
    # RUNTIME EVOLUTION
    # ========================================================

    _render_runtime_evolution()