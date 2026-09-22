"""
Runtime Architecture UI.

Runs dynamic analysis and displays:
1. Runtime modules
2. Runtime relationships
3. Static vs runtime differences
"""

import streamlit as st

from architecture_model.runtime_analyzer import RuntimeAnalyzer
from architecture_model.runtime_comparator import compare_architectures
from features.runtime_mapping import build_runtime_component_map


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

    st.subheader("Dynamic / Runtime Architecture")

    st.caption(
        "Runtime relationships observed during execution."
    )

    if target is None:
        st.info(
            "No runtime execution target has been configured."
        )
        return

    if include_prefixes is None:
        include_prefixes = [
            "features",
            "src",
            "architecture_model",
        ]

    # ------------------------------------------------------------
    # Run button
    # ------------------------------------------------------------

    if not st.button(
        "Run Runtime Analysis",
        key="run_runtime_analysis",
    ):
        st.info(
            "Click 'Run Runtime Analysis' to observe runtime behavior."
        )
        return

    analyzer = RuntimeAnalyzer(
        include_prefixes=include_prefixes
    )

    with st.spinner(
        "Tracing runtime architecture..."
    ):

        try:

            runtime_architecture = analyzer.run(
                target,
                entry_point="architecture_runtime_analysis",
            )

        except Exception as error:

            st.error(
                "Runtime analysis failed."
            )

            st.exception(error)

            return

    # ------------------------------------------------------------
    # Runtime summary
    # ------------------------------------------------------------

    st.markdown("### Runtime Summary")

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Runtime Modules",
            runtime_architecture.get_module_count(),
        )

    with col2:

        st.metric(
            "Runtime Relationships",
            runtime_architecture.get_relationship_count(),
        )

    with col3:

        st.metric(
            "Function Calls",
            runtime_architecture.total_calls,
        )

    # ------------------------------------------------------------
    # Runtime modules
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # Runtime relationships
    # ------------------------------------------------------------

    relationships = (
        runtime_architecture.get_relationships()
    )

    st.markdown(
        "### Observed Runtime Relationships"
    )

    if not relationships:

        st.info(
            "No cross-module runtime relationships were observed."
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

    # ------------------------------------------------------------
    # Static vs Runtime
    # ------------------------------------------------------------

    if static_relationships is None:
        return

    # ------------------------------------------------------------
    # Build component mappings
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # Compare static and runtime architecture
    # ------------------------------------------------------------

    comparison = compare_architectures(
        static_relationships,
        relationships,
        static_component_map=static_component_map,
        runtime_component_map=runtime_component_map,
    )

    st.markdown("---")

    st.markdown(
        "### Static vs Runtime Architecture"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Static Only",
            len(
                comparison["static_only"]
            ),
        )

    with col2:

        st.metric(
            "Both",
            len(
                comparison["both"]
            ),
        )

    with col3:

        st.metric(
            "Runtime Only",
            len(
                comparison["runtime_only"]
            ),
        )

    # ------------------------------------------------------------
    # Static only
    # ------------------------------------------------------------

    with st.expander(
        "Static Relationships Not Observed at Runtime",
        expanded=False,
    ):

        if comparison["static_only"]:

            for source, target in comparison[
                "static_only"
            ]:

                st.write(
                    f"`{source}` → `{target}`"
                )

        else:

            st.success(
                "All static relationships were observed."
            )

    # ------------------------------------------------------------
    # Both
    # ------------------------------------------------------------

    with st.expander(
        "Relationships Observed Both Statically and at Runtime",
        expanded=True,
    ):

        if comparison["both"]:

            for source, target in comparison[
                "both"
            ]:

                st.write(
                    f"`{source}` → `{target}`"
                )

        else:

            st.info(
                "No matching static/runtime relationships found."
            )

    # ------------------------------------------------------------
    # Runtime only
    # ------------------------------------------------------------

    with st.expander(
        "Runtime Relationships Not in Static Model",
        expanded=True,
    ):

        if comparison["runtime_only"]:

            for source, target in comparison[
                "runtime_only"
            ]:

                st.write(
                    f"`{source}` → `{target}`"
                )

        else:

            st.info(
                "No runtime-only relationships detected."
            )