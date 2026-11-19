"""
Runtime Architecture UI.

Runs dynamic analysis for the selected execution target and can compare
runtime architectures from two Git worktrees (V1 and V2).
"""

import streamlit as st
from pathlib import Path

from architecture_model.runtime_analyzer import RuntimeAnalyzer
from architecture_model.runtime_comparator import compare_architectures
from architecture_model.runtime_evolution import (
    compare_runtime_architectures,
    get_runtime_evolution_summary,
)
from architecture_model.runtime_version_runner import (
    list_repository_commits,
    list_common_runtime_entrypoints,
    run_version_pair,
)
from features.runtime_mapping import build_runtime_component_map


# ============================================================
# RUNTIME EVOLUTION
# ============================================================


def _render_runtime_evolution(repository_path):
    """
    Run the same runtime scenario against V1 and V2 and display
    runtime evolution information and charts.
    """

    st.markdown("---")

    st.subheader(
        "Runtime Architecture Evolution"
    )

    st.caption(
        "Choose any two commits from the repository selected in app_combined. "
        "The comparison below will use only those exact commits."
    )
    st.info(
        "Runtime V1/V2 execution evidence currently supports Python, JavaScript, "
        "erasable TypeScript, Ruby, Go, Java, C, C++, and C# when the required toolchains are installed. "
        "Go, C/C++, and C# use compiler coverage to identify executed source files (not call "
        "edges or call counts); Java uses sampled Flight Recorder stacks (not exact invocation "
        "counts). Static architecture recovery supports all 11 language families. "
        "Rust and PHP remain static-analysis only."
    )

    try:
        commits = list_repository_commits(repository_path)
    except Exception as error:
        st.error(f"Could not load commits from the selected repository: {error}")
        return

    if len(commits) < 2:
        st.warning("At least two Git commits are required for runtime comparison.")
        return

    commit_by_sha = {item["sha"]: item for item in commits}
    commit_options = [item["sha"] for item in commits]

    def commit_label(sha):
        item = commit_by_sha[sha]
        return f'{item["short_sha"]} · {item["message"][:90]} · {item["date"][:10]}'

    with st.form("runtime_commit_selection"):
        st.markdown("#### Select the two commits to compare")
        col1, col2 = st.columns(2)
        with col1:
            v1_commit = st.selectbox(
                "Version 1 (older or baseline)",
                options=commit_options,
                index=min(1, len(commit_options) - 1),
                format_func=commit_label,
                key="runtime_v1_selected_commit",
            )
        with col2:
            v2_commit = st.selectbox(
                "Version 2 (newer or target)",
                options=commit_options,
                index=0,
                format_func=commit_label,
                key="runtime_v2_selected_commit",
            )

        try:
            scenario_options = list_common_runtime_entrypoints(
                repository_path, v1_commit, v2_commit
            )
        except Exception as error:
            st.error(f"Could not inspect runnable scenarios in the selected commits: {error}")
            return

        if not scenario_options:
            st.warning(
                "These commits do not share a supported bounded runtime scenario. "
                "For Python, add runtime_scenario.py; for JavaScript or erasable "
                "TypeScript, add runtime_scenario.js or runtime_scenario.ts; "
                "for Ruby, add runtime_scenario.rb; for Go, use a bounded package-main file "
                "such as main.go with go.mod; for Java, select a class with static main; "
                "for C/C++, select a source file defining main(); for C#, select a bounded "
                "console application's .csproj file. The same scenario must exist in both commits."
            )
            return

        preferred_scenario = next(
            (name for name in ("runtime_scenario.py", "runtime_scenario.js", "runtime_scenario.ts", "runtime_scenario.rb", "runtime_scenario.go", "runtime_scenario.java", "runtime_scenario.c", "runtime_scenario.cpp", "runtime_scenario.csproj", "main.py", "cli.py", "run.py", "index.js", "index.ts", "main.rb", "main.go", "Main.java", "main.c", "main.cpp")
             if name in scenario_options),
            scenario_options[0],
        )
        selected_scenario = st.selectbox(
            "Runtime scenario (the same script runs against both commits)",
            options=scenario_options,
            index=scenario_options.index(preferred_scenario),
            help=(
                "Choose a bounded Python, JavaScript, erasable TypeScript, Ruby, Go, Java, C, or C++ "
                "scenario that exercises application logic. Go, C/C++, and C# report executed "
                "source files through coverage; Java reports sampled stack evidence, not "
                "exact call counts. Long-running web-server launchers are excluded."
            ),
            key="runtime_selected_scenario",
        )
        run_comparison = st.form_submit_button("Compare selected commits")

    if not run_comparison:
        st.info("Select two commits and click **Compare selected commits**.")
        return

    if v1_commit == v2_commit:
        st.error("Please select two different commits.")
        return

    with st.spinner("Preparing the selected Git versions and tracing runtime execution..."):
        try:
            versions = run_version_pair(
                repository_path=repository_path,
                v1_commit=v1_commit,
                v2_commit=v2_commit,
                scenario=selected_scenario,
            )

            comparison = compare_runtime_architectures(
                versions["v1_runtime"],
                versions["v2_runtime"],
                old_version=versions["v1_commit"],
                new_version=versions["v2_commit"],
            )

        except FileNotFoundError as error:
            # Runtime tracing requires a shared, bounded scenario in both
            # selected commits. Keep the static
            # repository graph, dependencies, and architecture history visible.
            st.warning(
                "Runtime execution comparison is unavailable for these commits. "
                "The selected versions do not share a runnable supported scenario. "
                "Your static architecture graph, inferred relationships, dependency "
                "inventory, and snapshot history remain available above. "
                "Runtime tracing for Rust and PHP is not implemented yet. "
                "TypeScript requires syntax that Node.js "
                "can strip without a separate build configuration."
            )
            st.caption(str(error))
            return

        except Exception as error:
            error_text = str(error)

            if "ModuleNotFoundError" in error_text or "No module named" in error_text:
                st.warning(
                    "Runtime execution needs a dependency that is not available "
                    "in the selected commit. The runtime runner now checks the "
                    "repository and scenario requirements.txt files and installs "
                    "declared packages in a temporary environment. If the missing "
                    "module is still reported, add its correct package distribution "
                    "to the applicable requirements.txt file and retry. If it is "
                    "a project-local module, verify that the file exists in both "
                    "selected commits and that its import path is correct."
                )
                st.code(error_text)
                st.info(
                    "Static architecture, source inventory, and commit-level "
                    "architecture comparison remain available. Runtime metrics "
                    "are not reported because the scenario did not complete."
                )
            else:
                st.error("Runtime execution comparison could not be completed.")
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
        f"Runtime scenario executed in both versions: `{versions['scenario']}`"
    )
    if Path(versions["scenario"]).suffix.lower() == ".go":
        st.info(
            "Go runtime evidence uses compiler-instrumented coverage. The module list "
            "shows project source files reached during execution; Go function-call "
            "relationships and call counts are not collected by this adapter."
        )
    elif Path(versions["scenario"]).suffix.lower() == ".java":
        st.info(
            "Java runtime evidence comes from sampled Java Flight Recorder stacks. "
            "The observed stack relationships are sampling evidence, not exact "
            "function invocation counts."
        )
    elif Path(versions["scenario"]).suffix.lower() in {".c", ".cc", ".cpp", ".cxx", ".c++"}:
        st.info(
            "C/C++ runtime evidence uses GCC/gcov coverage to identify executed source "
            "files. It does not collect runtime call relationships or call counts."
        )
    elif Path(versions["scenario"]).suffix.lower() == ".csproj":
        st.info(
            "C# runtime evidence uses dotnet-coverage to identify executed source files. "
            "It does not collect runtime call relationships or call counts."
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
        "Observed Calls",
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
        "Chart order: Modules → Relationships → Observed Calls (Go coverage does not provide call counts)"
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

    with st.expander("Observed Runtime Modules and Relationships", expanded=False):
        left, right = st.columns(2)
        with left:
            st.markdown("**V1 executed modules**")
            st.write(versions["v1_runtime"].modules or ["No project modules were observed"])
            st.markdown("**V1 runtime relationships**")
            v1_edges = [f"{edge.source} → {edge.target} ({edge.call_count} calls)"
                        for edge in versions["v1_runtime"].get_relationships()]
            st.write(v1_edges or ["No cross-module calls were observed"])
        with right:
            st.markdown("**V2 executed modules**")
            st.write(versions["v2_runtime"].modules or ["No project modules were observed"])
            st.markdown("**V2 runtime relationships**")
            v2_edges = [f"{edge.source} → {edge.target} ({edge.call_count} calls)"
                        for edge in versions["v2_runtime"].get_relationships()]
            st.write(v2_edges or ["No cross-module calls were observed"])

    st.caption(
        "These change counts describe only modules and calls reached by the selected "
        "runtime scenario. A zero means no difference was observed during that run; "
        "it does not mean the source files are identical."
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


def _render_repository_architecture(repository_path):
    """Build a language-neutral architecture view from the shared repository."""
    from collections import Counter
    from pathlib import Path
    from src.parser import parse_folder

    root = Path(repository_path).resolve()
    if not root.is_dir():
        st.error(f"The selected repository path is unavailable: {root}")
        return

    with st.spinner("Analyzing source files across supported languages..."):
        parsed_files = parse_folder(str(root))

    parsed_files = [item for item in parsed_files if not item.get("error") or item.get("functions") or item.get("classes") or item.get("imports")]
    if not parsed_files:
        st.warning("No supported source files could be parsed in this repository.")
        return

    language_counts = Counter(item.get("language", "unknown") for item in parsed_files)
    function_count = sum(len(item.get("functions", [])) + sum(len(cls.get("methods", [])) for cls in item.get("classes", [])) for item in parsed_files)
    class_count = sum(len(item.get("classes", [])) for item in parsed_files)
    import_count = sum(len(item.get("imports", [])) for item in parsed_files)

    st.markdown("### Repository Architecture Overview")
    st.caption("This view is generated from the repository selected in the combined sidebar. Relationships are inferred from source imports and parser call graphs; they are not observed live execution calls.")
    a, b, c, d = st.columns(4)
    a.metric("Source files", len(parsed_files))
    b.metric("Functions / methods", function_count)
    c.metric("Classes / types", class_count)
    d.metric("Imports", import_count)

    st.markdown("#### Languages detected")
    st.bar_chart(dict(language_counts))

    from architecture_model.recovery import recover_architecture

    snapshot = recover_architecture(parsed_files)
    component_by_id = {component.id: component for component in snapshot.components}

    st.markdown("#### Recovered architecture components")
    component_rows = [
        {
            "Component": component.name,
            "Layer": component.layer,
            "Source files": len(component.files),
            "Dependencies": len(component.dependencies),
            "Responsibility": component.responsibility,
        }
        for component in snapshot.components
    ]
    if component_rows:
        st.dataframe(component_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No architecture components could be recovered from the parsed source files.")

    st.markdown("#### Internal component dependencies")
    relationship_rows = [
        {
            "Source component": component_by_id[edge.source].name,
            "Target component": component_by_id[edge.target].name,
            "Relationship": edge.type,
            "Evidence": "Resolved source import",
        }
        for edge in snapshot.relationships
        if edge.source in component_by_id and edge.target in component_by_id
    ]
    if relationship_rows:
        st.dataframe(relationship_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No internal component imports were resolved. External libraries are excluded from the internal architecture graph.")

    st.markdown("#### Architecture dependency graph")
    dot_lines = [
        "digraph Architecture {",
        "  rankdir=LR;",
        '  graph [bgcolor="transparent"];',
        '  node [shape=box, style="rounded,filled", fillcolor="#E8F0FE", color="#5B78A6"];',
    ]
    for component in snapshot.components:
        label = component.name.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        dot_lines.append(f'  "{component.id}" [label="{label}"];')
    for edge in snapshot.relationships:
        dot_lines.append(f'  "{edge.source}" -> "{edge.target}";')
    dot_lines.append("}")
    try:
        st.graphviz_chart("\n".join(dot_lines), use_container_width=True)
    except Exception as graph_error:
        st.warning(f"Could not render the dependency graph: {graph_error}")

    st.markdown("#### Dependency inventory")
    dependency_rows = []
    for item in parsed_files:
        source_name = Path(item["file"]).resolve().relative_to(root).as_posix()
        for imported in item.get("imports", []):
            dependency_rows.append({
                "Source file": source_name,
                "Language": item.get("language", "unknown"),
                "Imported dependency": str(imported),
            })
    if dependency_rows:
        st.dataframe(dependency_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No imports or dependencies were detected.")

    with st.expander("Source file inventory", expanded=False):
        for item in sorted(parsed_files, key=lambda value: str(value.get("file", ""))):
            rel = Path(item["file"]).resolve().relative_to(root).as_posix()
            st.markdown("**" + rel + "** · " + str(item.get("language", "unknown")))
            funcs = [fn.get("name", "") for fn in item.get("functions", [])]
            classes = [cls.get("name", "") for cls in item.get("classes", [])]
            if funcs:
                st.caption("Functions: " + ", ".join(funcs[:30]))
            if classes:
                st.caption("Types: " + ", ".join(classes[:30]))
            if item.get("error"):
                st.warning(str(item["error"]))

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
        repository_path = (
            st.session_state.get("evolution_repo_path")
            or st.session_state.get("repository_local_path")
            or st.session_state.get("github_repo_path")
        )
        repository_url = (
            st.session_state.get("evolution_repo_url")
            or st.session_state.get("repository_url")
            or st.session_state.get("github_repository_url")
        )
        if not repository_path:
            st.info("Load a GitHub repository from the shared app_combined sidebar to analyze its runtime architecture.")
            return
        st.caption("Selected repository: " + str(repository_url or repository_path))
        _render_repository_architecture(repository_path)
        st.info("The repository overview above is static analysis. Python runtime evolution below executes a selected entry point from the two Git versions; non-Python languages remain static-analysis only.")
        _render_runtime_evolution(repository_path)
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

    # Runtime Evolution belongs to Architecture Evolution and uses the
    # repository selected in the shared app_combined sidebar.
    repository_path = (
        st.session_state.get("evolution_repo_path")
        or st.session_state.get("repository_local_path")
        or st.session_state.get("github_repo_path")
    )
    if repository_path:
        _render_runtime_evolution(repository_path)
    else:
        st.info(
            "Load a GitHub repository from the shared app_combined sidebar "
            "before comparing runtime architecture commits."
        )