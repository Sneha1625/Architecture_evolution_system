import os
import ast
import networkx as nx
import plotly.graph_objects as go
import streamlit as st

from git import Repo

from repository.loader import get_python_files

from architecture_model.recovery import (
    recover_architecture,
)


def recover_architecture_from_commit(
    repo_path,
    commit_hash,
):
    parsed_results = []

    repo = Repo(repo_path)

    original_commit = repo.head.commit.hexsha

    original_branch = None

    try:
        if not repo.head.is_detached:
            original_branch = repo.active_branch.name
    except Exception:
        original_branch = None

    try:
        repo.git.checkout(
            commit_hash
        )

        python_files = get_python_files(
            repo_path
        )

        for file_path in python_files:
            try:
                with open(
                    file_path,
                    "r",
                    encoding="utf-8",
                    errors="replace",
                ) as f:
                    source = f.read()

                tree = ast.parse(
                    source,
                    filename=file_path,
                )

                parsed_results.append({
                    "file": os.path.relpath(
                        file_path,
                        repo_path,
                    ),
                    "tree": tree,
                    "source": source,
                })

            except Exception:
                continue

        snapshot = recover_architecture(
            parsed_results,
            commit_hash=commit_hash,
        )

        return snapshot

    except Exception as e:
        raise RuntimeError(
            f"Architecture recovery failed: {e}"
        )

    finally:
        try:
            if original_branch:
                repo.git.checkout(
                    original_branch
                )
            else:
                repo.git.checkout(
                    original_commit
                )

        except Exception:

            try:
                repo.git.checkout(
                    original_commit
                )
            except Exception:
                pass


def snapshot_to_dict(
    snapshot,
):

    if snapshot is None:
        return {}

    if isinstance(
        snapshot,
        dict,
    ):
        return snapshot

    try:

        if hasattr(
            snapshot,
            "model_dump",
        ):

            return snapshot.model_dump()

        if hasattr(
            snapshot,
            "dict",
        ):

            return snapshot.dict()

        if hasattr(
            snapshot,
            "__dict__",
        ):

            return dict(
                snapshot.__dict__
            )

    except Exception:

        pass

    data = {}

    for field in [
        "version",
        "commit_hash",
        "components",
        "relationships",
        "metrics",
        "violations",
        "timestamp",
    ]:

        try:

            if hasattr(
                snapshot,
                field,
            ):

                data[field] = getattr(
                    snapshot,
                    field,
                )

        except Exception:

            pass

    return data


def display_architecture_snapshot(
    snapshot,
    title="Architecture Snapshot",
):

    if snapshot is None:

        st.info(
            "No architecture snapshot available."
        )

        return

    data = snapshot_to_dict(
        snapshot
    )

    st.markdown(
        f"### 🗺️ {title}"
    )

    commit_hash = data.get(
        "commit_hash",
        "unknown",
    )

    version = data.get(
        "version",
        "unknown",
    )

    timestamp = data.get(
        "timestamp",
        None,
    )

    metrics = data.get(
        "metrics",
        {},
    )

    if not isinstance(
        metrics,
        dict,
    ):

        metrics = {}

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Version",
        str(version),
    )

    c2.metric(
        "Commit",
        str(commit_hash)[:7],
    )

    c3.metric(
        "Components",
        metrics.get(
            "total_components",
            len(
                data.get(
                    "components",
                    [],
                )
            ),
        ),
    )

    c4, c5, c6 = st.columns(3)

    c4.metric(
        "Relationships",
        metrics.get(
            "total_relationships",
            len(
                data.get(
                    "relationships",
                    [],
                )
            ),
        ),
    )

    c5.metric(
        "Files",
        metrics.get(
            "total_files",
            0,
        ),
    )

    c6.metric(
        "Violations",
        len(
            data.get(
                "violations",
                [],
            )
        ),
    )

    if timestamp:

        st.caption(
            f"Snapshot timestamp: {timestamp}"
        )

    with st.expander(
        "📦 View Architecture Snapshot Details"
    ):

        st.json(
            data,
            expanded=False,
        )
def architecture_snapshot_to_graph(
    snapshot,
):

    G = nx.DiGraph()

    if snapshot is None:

        return G

    components = getattr(
        snapshot,
        "components",
        [],
    )

    relationships = getattr(
        snapshot,
        "relationships",
        [],
    )

    for component in components:

        name = getattr(
            component,
            "name",
            str(component),
        )

        G.add_node(
            name
        )

    for relationship in relationships:

        source = getattr(
            relationship,
            "source",
            None,
        )

        target = getattr(
            relationship,
            "target",
            None,
        )

        if source is None:

            source = getattr(
                relationship,
                "from_component",
                None,
            )

        if target is None:

            target = getattr(
                relationship,
                "to_component",
                None,
            )

        if source and target:

            source_name = getattr(
                source,
                "name",
                str(source),
            )

            target_name = getattr(
                target,
                "name",
                str(target),
            )

            G.add_edge(
                source_name,
                target_name,
            )

    return G
def create_animated_architecture(
    G,
):

    if G.number_of_nodes() == 0:

        st.warning(
            "No architecture nodes found."
        )

        return

    pos = nx.spring_layout(
        G,
        seed=42,
        k=2.0,
        iterations=100,
    )

    nodes = list(
        G.nodes()
    )

    edge_x = []
    edge_y = []

    for source, target in G.edges():

        if (
            source not in pos
            or target not in pos
        ):

            continue

        x0, y0 = pos[source]
        x1, y1 = pos[target]

        edge_x.extend(
            [x0, x1, None]
        )

        edge_y.extend(
            [y0, y1, None]
        )

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(width=1.5),
        hoverinfo="none",
    )

    node_x = []
    node_y = []
    node_text = []
    node_hover = []

    for node in nodes:

        x, y = pos[node]

        node_x.append(x)
        node_y.append(y)

        node_text.append(
            str(node)
        )

        node_hover.append(
            f"<b>{node}</b><br>"
            f"Connections: {G.degree(node)}"
        )

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="top center",
        hovertext=node_hover,
        hoverinfo="text",
        marker=dict(
            size=28,
            line=dict(width=2),
        ),
    )

    frames = []

    for step in range(
        1,
        len(nodes) + 1,
    ):

        visible_nodes = nodes[
            :step
        ]

        visible_set = set(
            visible_nodes
        )

        visible_node_x = []
        visible_node_y = []
        visible_node_text = []
        visible_node_hover = []

        for node in visible_nodes:

            x, y = pos[node]

            visible_node_x.append(x)
            visible_node_y.append(y)

            visible_node_text.append(
                str(node)
            )

            visible_node_hover.append(
                f"<b>{node}</b><br>"
                f"Connections: {G.degree(node)}"
            )

        visible_edge_x = []
        visible_edge_y = []

        for source, target in G.edges():

            if (
                source in visible_set
                and target in visible_set
            ):

                x0, y0 = pos[source]
                x1, y1 = pos[target]

                visible_edge_x.extend(
                    [x0, x1, None]
                )

                visible_edge_y.extend(
                    [y0, y1, None]
                )

        frames.append(
            go.Frame(
                name=f"frame{step}",
                data=[
                    go.Scatter(
                        x=visible_edge_x,
                        y=visible_edge_y,
                        mode="lines",
                        line=dict(width=1.5),
                        hoverinfo="none",
                    ),
                    go.Scatter(
                        x=visible_node_x,
                        y=visible_node_y,
                        mode="markers+text",
                        text=visible_node_text,
                        textposition="top center",
                        hovertext=visible_node_hover,
                        hoverinfo="text",
                        marker=dict(
                            size=28,
                            line=dict(width=2),
                        ),
                    ),
                ],
            )
        )

    fig = go.Figure(
        data=[
            edge_trace,
            node_trace,
        ],
        frames=frames,
    )

    fig.update_layout(

        title=dict(
            text="🗺️ Interactive Software Architecture",
            x=0.5,
            xanchor="center",
        ),

        showlegend=False,

        hovermode="closest",

        height=700,

        margin=dict(
            b=20,
            l=20,
            r=20,
            t=100,
        ),

        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
        ),

        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
        ),

        updatemenus=[

            dict(

                type="buttons",

                showactive=False,

                x=0.01,

                y=1.12,

                buttons=[

                    dict(

                        label="▶ Build Architecture",

                        method="animate",

                        args=[

                            [
                                f"frame{i}"
                                for i in range(
                                    1,
                                    len(nodes) + 1,
                                )
                            ],

                            {
                                "frame": {
                                    "duration": 700,
                                    "redraw": True,
                                },

                                "transition": {
                                    "duration": 400,
                                },

                                "fromcurrent": True,

                                "mode": "immediate",
                            },
                        ],
                    ),

                    dict(

                        label="⏵ Show Complete",

                        method="animate",

                        args=[

                            [
                                f"frame{len(nodes)}"
                            ],

                            {
                                "frame": {
                                    "duration": 500,
                                    "redraw": True,
                                },

                                "transition": {
                                    "duration": 300,
                                },
                            },
                        ],
                    ),
                ],
            )
        ],
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )