"""
AI-ASSISTED SOFTWARE ARCHITECTURE INTELLIGENCE SYSTEM

Core capabilities:
1. Source-code structural analysis
2. AST analysis
3. Architecture recovery
4. Persistent architecture snapshots
5. Interactive architecture visualization
6. Dependency analysis
7. Multi-file architecture analysis
8. Architecture metrics
9. Logical coupling analysis
10. Module boundary detection
11. Architecture risk analysis
12. Architecture debt analysis
13. Semantic embeddings foundation
14. GitHub repository analysis

Architecture Time Machine:
    Recover architecture at historical Git commits and compare
    architecture snapshots over time.

Future:
    Architecture-aware RAG
    Evidence-grounded architecture assistant
    What-if architecture simulation
"""

# ============================================================
# IMPORTS
# ============================================================

import os
import sys
import tempfile
import ast
from pathlib import Path

import streamlit as st
import networkx as nx
import plotly.graph_objects as go
from git import Repo, InvalidGitRepositoryError, NoSuchPathError
from dotenv import load_dotenv


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

FEATURES_DIR = os.path.join(BASE_DIR, "features")

if FEATURES_DIR not in sys.path:
    sys.path.insert(0, FEATURES_DIR)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

SRC_ENV = os.path.join(BASE_DIR, "src", ".env")

if os.path.exists(SRC_ENV):
    load_dotenv(SRC_ENV)


# ============================================================
# REPOSITORY IMPORTS
# ============================================================

from repository.loader import (
    clone_github_repository,
    extract_uploaded_repository,
    get_repository_name,
    get_python_files,
)


# ============================================================
# PROJECT IMPORTS
# ============================================================

from src.parser import (
    parse_file,
    read_file,
    get_summary,
)

from src.analyzer import analyze_parsed_result

from src.architect import (
    build_graph,
    draw_graph,
)

from src.dependency import (
    build_dependency_graph,
    draw_dependency_graph,
)

from src.embedder import embed_parsed_result


# ============================================================
# ARCHITECTURE MODEL
# ============================================================

try:
    from architecture_model.recovery import recover_architecture

    ARCHITECTURE_MODEL_AVAILABLE = True

except ImportError:
    ARCHITECTURE_MODEL_AVAILABLE = False


# ============================================================
# OPTIONAL ARCHITECTURE FEATURES
# ============================================================

try:
    from features.coupling_miner import mine_logical_coupling

    COUPLING_AVAILABLE = True

except ImportError:
    COUPLING_AVAILABLE = False


try:
    from features.community_detector import analyze_modularity

    COMMUNITY_AVAILABLE = True

except ImportError:
    COMMUNITY_AVAILABLE = False


try:
    from features.risk_predictor import compute_risk_scores

    RISK_AVAILABLE = True

except ImportError:
    RISK_AVAILABLE = False


try:
    from features.impact_predictor import predict_change_impact

    IMPACT_AVAILABLE = True

except ImportError:
    IMPACT_AVAILABLE = False


try:
    from features.techdebt import calculate_technical_debt

    TECH_DEBT_AVAILABLE = True

except ImportError:
    TECH_DEBT_AVAILABLE = False


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Architecture Intelligence System",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CUSTOM CSS
# ============================================================

STYLE_PATH = os.path.join(BASE_DIR, "style.css")

if os.path.exists(STYLE_PATH):

    try:

        with open(
            STYLE_PATH,
            "r",
            encoding="utf-8",
        ) as f:

            st.markdown(
                f"<style>{f.read()}</style>",
                unsafe_allow_html=True,
            )

    except Exception:
        pass


# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================

DEFAULT_SESSION_STATE = {

    "uploaded_file_data": [],

    "github_repo_path": None,

    "repository_source": None,

    "repository_name": None,

    "repository_file_paths": [],

    "repository_local_path": None,

    "repository_url": None,

    "latest_architecture_snapshot": None,

    "architecture_snapshots": [],

    "active_page": "🏠 Overview",

}


for key, default_value in DEFAULT_SESSION_STATE.items():

    if key not in st.session_state:

        st.session_state[key] = default_value


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def repository_loaded():
    """
    Return True if a repository or uploaded Python files
    are currently available.
    """

    return bool(
        st.session_state.get("repository_file_paths")
        or st.session_state.get("uploaded_file_data")
    )


def git_repository_available():
    """
    Return True when the currently loaded repository has
    usable Git history.
    """

    repo_path = (
        st.session_state.get("github_repo_path")
        or st.session_state.get("repository_local_path")
    )

    if not repo_path:
        return False

    try:

        repo = Repo(repo_path)

        return not repo.bare and repo.head.is_valid()

    except Exception:
        return False


def get_current_repository_path():
    """
    Return the active repository path.
    """

    return (
        st.session_state.get("repository_local_path")
        or st.session_state.get("github_repo_path")
    )


def get_relative_file_name(file_path):
    """
    Convert an absolute repository file path into
    a repository-relative path.
    """

    root = get_current_repository_path()

    if root:

        try:

            return os.path.relpath(
                file_path,
                root,
            )

        except Exception:
            pass

    return file_path


def require_uploaded_files():
    """
    Require a loaded repository or uploaded Python files.
    """

    if not repository_loaded():

        st.warning(
            "📂 Open **📂 Repository Input** and load a "
            "GitHub repository, ZIP repository, or Python files first."
        )

        st.stop()


def require_git_repository():
    """
    Require a repository with valid Git history.
    """

    require_uploaded_files()

    if not git_repository_available():

        st.warning(
            "🐙 This feature requires a repository with valid Git history. "
            "Load a GitHub repository containing its `.git` history."
        )

        st.stop()


# ============================================================
# UPLOADED FILE HELPERS
# ============================================================

def create_temp_files():
    """
    Recreate uploaded Python files as temporary files.

    Returns:
        list[str]: temporary file paths
    """

    file_paths = []

    uploaded_files = st.session_state.get(
        "uploaded_file_data",
        [],
    )

    for item in uploaded_files:

        try:

            tmp = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".py",
            )

            tmp.write(item["data"])

            tmp.close()

            file_paths.append(tmp.name)

        except Exception as e:

            st.warning(
                f"Could not create temporary file "
                f"for `{item.get('name', 'unknown')}`: {e}"
            )

    return file_paths


def parse_uploaded_files():
    """
    Parse repository Python files or legacy uploaded Python files.

    Returns:
        file_paths
        parsed_files
        source_files
    """

    repository_files = st.session_state.get(
        "repository_file_paths",
        [],
    )

    if repository_files:

        file_paths = list(repository_files)

    else:

        file_paths = create_temp_files()

    parsed_files = []

    source_files = []

    for path in file_paths:

        try:

            parsed = parse_file(path)

            source = read_file(path)

            parsed_files.append(parsed)

            source_files.append(source)

        except Exception as e:

            st.warning(
                f"Could not parse `{path}`: {e}"
            )

    return (
        file_paths,
        parsed_files,
        source_files,
    )


# ============================================================
# DEPENDENCY GRAPH
# ============================================================

def build_combined_dependency_graph(file_paths):

    G = nx.DiGraph()

    for path in file_paths:

        try:

            subgraph = build_dependency_graph(path)

            G = nx.compose(
                G,
                subgraph,
            )

        except Exception as e:

            st.warning(
                f"Could not analyze `{path}`: {e}"
            )

    return G


# ============================================================
# ARCHITECTURE GRAPH VISUALIZATION
# ============================================================

def create_architecture_graph(G):
    """
    Create interactive architecture graph.
    """

    if G.number_of_nodes() == 0:

        st.warning(
            "No architecture nodes were detected."
        )

        return

    pos = nx.spring_layout(
        G,
        seed=42,
        k=2.0,
        iterations=100,
    )

    edge_x = []
    edge_y = []

    for source, target in G.edges():

        if source not in pos or target not in pos:
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

    for node in G.nodes():

        x, y = pos[node]

        node_x.append(x)
        node_y.append(y)

        node_text.append(
            str(node)
        )

        node_hover.append(
            f"<b>{node}</b><br>"
            f"Dependencies: {G.degree(node)}"
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

    fig = go.Figure(
        data=[
            edge_trace,
            node_trace,
        ]
    )

    fig.update_layout(
        title={
            "text": "🏗️ Recovered Software Architecture",
            "x": 0.5,
            "xanchor": "center",
        },
        showlegend=False,
        height=700,
        hovermode="closest",
        margin=dict(
            b=20,
            l=20,
            r=20,
            t=80,
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
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Components",
        G.number_of_nodes(),
    )

    c2.metric(
        "Dependencies",
        G.number_of_edges(),
    )

    density = (
        nx.density(G)
        if G.number_of_nodes() > 0
        else 0
    )

    c3.metric(
        "Graph Density",
        f"{density:.3f}",
    )


# ============================================================
# SNAPSHOT HELPERS
# ============================================================

def snapshot_to_dict(snapshot):
    """
    Convert ArchitectureSnapshot into a dictionary.
    """

    if snapshot is None:
        return {}

    if isinstance(snapshot, dict):
        return snapshot

    try:

        if hasattr(snapshot, "model_dump"):

            return snapshot.model_dump()

        if hasattr(snapshot, "dict"):

            return snapshot.dict()

        if hasattr(snapshot, "__dict__"):

            return dict(snapshot.__dict__)

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

            if hasattr(snapshot, field):

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
    """
    Display ArchitectureSnapshot in the UI.
    """

    if snapshot is None:

        st.info(
            "No architecture snapshot available."
        )

        return

    data = snapshot_to_dict(
        snapshot
    )

    st.markdown(
        f"### 🏗️ {title}"
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

    if not isinstance(metrics, dict):
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
            len(data.get("components", [])),
        ),
    )

    c4, c5, c6 = st.columns(3)

    c4.metric(
        "Relationships",
        metrics.get(
            "total_relationships",
            len(data.get("relationships", [])),
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


# ============================================================
# TEMP FILE CLEANUP
# ============================================================

def cleanup_temp_files(file_paths):

    for path in file_paths:

        try:

            if os.path.exists(path):

                os.unlink(path)

        except Exception:
            pass


# ============================================================
# ANIMATED ARCHITECTURE
# ============================================================

def create_animated_architecture(G):
    """
    Create interactive animated architecture diagram.
    """

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

    nodes = list(G.nodes())

    edge_x = []
    edge_y = []

    for source, target in G.edges():

        if source not in pos or target not in pos:
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

        visible_nodes = nodes[:step]

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
            text="🏗️ Interactive Software Architecture",
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

                        label="⏹ Show Complete",

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

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Modules",
        G.number_of_nodes(),
    )

    col2.metric(
        "Dependencies",
        G.number_of_edges(),
    )

    density = (
        nx.density(G)
        if G.number_of_nodes() > 0
        else 0
    )

    col3.metric(
        "Graph Density",
        f"{density:.2f}",
    )

    st.info(
        "💡 Click 'Build Architecture' to see the architecture "
        "appear step-by-step. Hover over modules to inspect "
        "their connections. You can also zoom and drag the diagram."
    )


# ============================================================
# GITHUB HELPERS
# ============================================================

def get_github_repository_overview(
    repo_path,
    github_url,
):
    """
    Return basic GitHub repository information.
    """

    repo = Repo(repo_path)

    repo_name = Path(
        repo_path
    ).name

    clean_url = (
        github_url
        .strip()
        .rstrip("/")
    )

    if clean_url.endswith(".git"):

        clean_url = clean_url[:-4]

    parts = clean_url.split("/")

    owner = "Unknown"

    if (
        len(parts) >= 2
        and "github.com" in clean_url.lower()
    ):

        owner = parts[-2]

        repo_name = (
            parts[-1]
            or repo_name
        )

    try:

        branch = repo.active_branch.name

    except TypeError:

        branch = "Detached HEAD"

    except Exception:

        branch = "Unknown"

    try:

        commit_count = sum(
            1
            for _ in repo.iter_commits("--all")
        )

    except Exception:

        commit_count = 0

    return {

        "name": repo_name,

        "owner": owner,

        "branch": branch,

        "url": github_url.strip(),

        "commit_count": commit_count,
    }


def get_recent_commits(
    repo_path,
    limit=10,
):
    """
    Return recent commits with changed files.
    """

    repo = Repo(repo_path)

    commits = []

    for commit in repo.iter_commits(
        "--all",
        max_count=limit,
    ):

        changed_files = set()

        try:

            if commit.parents:

                parent = commit.parents[0]

                for diff in parent.diff(
                    commit,
                    create_patch=False,
                ):

                    if diff.a_path:

                        changed_files.add(
                            diff.a_path
                        )

                    if diff.b_path:

                        changed_files.add(
                            diff.b_path
                        )

            else:

                for item in commit.tree.traverse():

                    if item.type == "blob":

                        changed_files.add(
                            item.path
                        )

        except Exception:

            changed_files = set()

        commits.append({

            "hash":
                commit.hexsha[:7],

            "full_hash":
                commit.hexsha,

            "message":
                (
                    commit.message
                    .strip()
                    .splitlines()[0]
                    if commit.message.strip()
                    else "No commit message"
                ),

            "author":
                commit.author.name
                or "Unknown",

            "date":
                commit.committed_datetime.strftime(
                    "%Y-%m-%d %H:%M"
                ),

            "files_changed":
                len(changed_files),

            "changed_files":
                sorted(changed_files),
        })

    return commits


# ============================================================
# ARCHITECTURE TIME MACHINE
# ============================================================

def get_commit_hash(repo_path):
    """
    Return currently checked-out commit SHA.
    """

    try:

        repo = Repo(repo_path)

        return repo.head.commit.hexsha

    except Exception:

        return "unknown"


def get_commit_short_hash(repo_path):

    commit_hash = get_commit_hash(
        repo_path
    )

    if commit_hash == "unknown":

        return commit_hash

    return commit_hash[:7]


def parse_repository_at_commit(
    repo_path,
    commit_hash,
):
    """
    Checkout a Git commit, parse Python files,
    and restore the original repository state.

    Returns:
        parsed_results
        source_contents
        file_paths
    """

    repo = Repo(repo_path)

    original_commit = (
        repo.head.commit.hexsha
    )

    original_branch = None

    try:

        if not repo.head.is_detached:

            original_branch = (
                repo.active_branch.name
            )

    except Exception:

        original_branch = None

    parsed_results = []
    source_contents = []
    file_paths = []

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

                    "file":
                        os.path.relpath(
                            file_path,
                            repo_path,
                        ),

                    "tree":
                        tree,

                    "source":
                        source,
                })

                source_contents.append(
                    source
                )

                file_paths.append(
                    file_path
                )

            except Exception:

                continue

        return (
            parsed_results,
            source_contents,
            file_paths,
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


def recover_architecture_from_commit(
    repo_path,
    commit_hash,
):
    """
    Recover ArchitectureSnapshot for a Git commit.
    """

    if not ARCHITECTURE_MODEL_AVAILABLE:

        raise RuntimeError(
            "architecture_model package is not available."
        )

    parsed_results = []

    repo = Repo(repo_path)

    original_commit = (
        repo.head.commit.hexsha
    )

    original_branch = None

    try:

        if not repo.head.is_detached:

            original_branch = (
                repo.active_branch.name
            )

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

                    "file":
                        os.path.relpath(
                            file_path,
                            repo_path,
                        ),

                    "tree":
                        tree,

                    "source":
                        source,
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


def architecture_snapshot_to_graph(
    snapshot,
):
    """
    Convert ArchitectureSnapshot into NetworkX graph.
    """

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


# ============================================================
# NAVIGATION
# ============================================================

PAGES = [

    "🏠 Overview",

    "💻 Source Code",

    "🌳 AST Structure",

    "🤖 Structural Analysis",

    "🏗️ Architecture Model",

    "🔗 Dependency Analysis",

    "📊 Architecture Metrics",

    "🧩 Module Boundaries",

    "🔀 Logical Coupling",

    "🔥 Architecture Risk",

    "💰 Architecture Debt",

    "🩺 Architecture Health",

    "🔢 Semantic Embeddings",

    "📂 Repository Input",

    "⏳ Architecture Time Machine",
]


# ============================================================
# APPLICATION TITLE
# ============================================================

st.title(
    "🏗️ Architecture Intelligence System"
)

st.caption(
    "Recover, visualize and evaluate software architecture "
    "from source-code structure and repository evidence."
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        '<div class="sidebar-logo">🏗️ Architecture Intelligence</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "AI-assisted software architecture analysis"
    )

    st.markdown("---")

    page = st.radio(
        "Navigation",
        PAGES,
        index=PAGES.index(
            st.session_state.get(
                "active_page",
                "🏠 Overview",
            )
        ),
        label_visibility="collapsed",
        key="active_page",
    )

    st.markdown("---")

    st.markdown(
        "### Project Pipeline"
    )

    st.markdown(
        """
        **Repository**

        ↓

        **AST Analysis**

        ↓

        **Architecture Recovery**

        ↓

        **Dependency Graph**

        ↓

        **Architecture Metrics**

        ↓

        **Governance & Risk**

        ↓

        **Evidence-Grounded AI**
        """
    )


# ============================================================
# COMMON PARSING
# ============================================================

file_paths = []
parsed_files = []
all_sources = []

if page not in [
    "🏠 Overview",
    "📂 Repository Input",
    "⏳ Architecture Time Machine",
]:

    if repository_loaded():

        (
            file_paths,
            parsed_files,
            all_sources,
        ) = parse_uploaded_files()


# ============================================================
# PAGE 1 — OVERVIEW
# ============================================================

if page == "🏠 Overview":

    st.header(
        "🏗️ Software Architecture Intelligence"
    )

    st.write(
        """
        This system analyzes a software repository and constructs
        machine-readable architectural evidence from its source code.
        """
    )

    st.markdown(
        "### Core Objective"
    )

    st.info(
        """
        **Automatically recover and understand the architecture of a
        software system from source-code structure, dependencies and
        repository evidence, then measure its architectural characteristics
        and provide evidence for architectural decisions.**
        """
    )

    st.markdown(
        "### Analysis Pipeline"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.markdown("### 1️⃣")

        st.markdown(
            "**Recover**"
        )

        st.caption(
            "AST + dependencies → architecture model"
        )

    with col2:

        st.markdown("### 2️⃣")

        st.markdown(
            "**Measure**"
        )

        st.caption(
            "Coupling, structure, cycles and risk"
        )

    with col3:

        st.markdown("### 3️⃣")

        st.markdown(
            "**Govern**"
        )

        st.caption(
            "Identify architectural problems"
        )

    with col4:

        st.markdown("### 4️⃣")

        st.markdown(
            "**Reason**"
        )

        st.caption(
            "Future evidence-grounded RAG"
        )

    st.divider()

    st.markdown(
        "### 📂 Upload Repository Files"
    )

    new_uploads = st.file_uploader(
        "Upload Python files",
        type=["py"],
        accept_multiple_files=True,
        key="overview_python_upload",
    )

    if new_uploads:

        st.session_state[
            "uploaded_file_data"
        ] = [

            {
                "name": file.name,
                "data": file.getvalue(),
            }

            for file in new_uploads
        ]

        # Clear repository-based state when using direct uploads.
        st.session_state[
            "repository_file_paths"
        ] = []

        st.session_state[
            "repository_local_path"
        ] = None

        st.session_state[
            "github_repo_path"
        ] = None

        st.session_state[
            "repository_source"
        ] = "Python Upload"

    uploaded_files = st.session_state.get(
        "uploaded_file_data",
        [],
    )

    if uploaded_files:

        st.success(
            f"✅ {len(uploaded_files)} Python file(s) ready."
        )

        with st.expander(
            "View uploaded files"
        ):

            for item in uploaded_files:

                st.write(
                    f"📄 {item['name']}"
                )

    else:

        st.info(
            "Upload one or more Python files or use "
            "**📂 Repository Input** for a complete repository."
        )

    st.divider()

    st.markdown(
        """
        ### Current Project Scope

        **Architecture Recovery**

        →

        **Persistent Architecture Model**

        →

        **Dependency Analysis**

        →

        **Architecture Metrics**

        →

        **Architecture Governance**

        →

        **Architecture Risk / Debt**

        →

        **Git Evolution**

        →

        **Architecture-aware RAG**

        →

        **What-if Simulation**
        """
    )


# ============================================================
# PAGE 2 — SOURCE CODE
# ============================================================

if page == "💻 Source Code":

    require_uploaded_files()

    st.header(
        "💻 Source Code"
    )

    if not all_sources:

        st.warning(
            "No readable Python source files were found."
        )

    for index, source in enumerate(
        all_sources
    ):

        if st.session_state.get(
            "repository_file_paths"
        ):

            name = get_relative_file_name(
                file_paths[index]
            )

        else:

            name = st.session_state[
                "uploaded_file_data"
            ][index]["name"]

        st.subheader(
            name
        )

        st.code(
            source,
            language="python",
        )


# ============================================================
# PAGE 3 — AST
# ============================================================

if page == "🌳 AST Structure":

    require_uploaded_files()

    st.header(
        "🌳 Abstract Syntax Tree"
    )

    st.caption(
        "Structural representation extracted from Python source code."
    )

    if parsed_files:

        selected = st.selectbox(
            "Select file",
            range(len(parsed_files)),
            format_func=lambda i:
                get_relative_file_name(
                    file_paths[i]
                )
                if st.session_state.get(
                    "repository_file_paths"
                )
                else st.session_state[
                    "uploaded_file_data"
                ][i]["name"],
        )

        parsed = parsed_files[selected]

        # Do not directly pass Python AST objects to st.json().
        # Convert them into a readable AST dump.
        if isinstance(parsed, dict):

            ast_tree = parsed.get(
                "tree"
            )

            if isinstance(
                ast_tree,
                ast.AST,
            ):

                st.code(
                    ast.dump(
                        ast_tree,
                        indent=2,
                    ),
                    language="text",
                )

            else:

                st.write(
                    parsed
                )

        else:

            st.write(
                parsed
            )

    else:

        st.warning(
            "No parsed Python files available."
        )


# ============================================================
# PAGE 4 — STRUCTURAL ANALYSIS
# ============================================================

if page == "🤖 Structural Analysis":

    require_uploaded_files()

    st.header(
        "🤖 Structural Analysis"
    )

    st.write(
        """
        Analyze source-code structure using the project's parser
        and analyzer. This is structural evidence, not generic
        AI code generation.
        """
    )

    if not parsed_files:

        st.warning(
            "No parsed files available."
        )

    elif st.button(
        "Run Structural Analysis",
        type="primary",
    ):

        try:

            # Existing analyzer is retained.
            # For multi-file repositories, analyze every parsed file.
            results = []

            for index, parsed in enumerate(
                parsed_files
            ):

                try:

                    result = analyze_parsed_result(
                        parsed,
                        all_sources[index],
                    )

                    results.append({

                        "file":
                            get_relative_file_name(
                                file_paths[index]
                            ),

                        "analysis":
                            result,
                    })

                except Exception as file_error:

                    results.append({

                        "file":
                            get_relative_file_name(
                                file_paths[index]
                            ),

                        "error":
                            str(file_error),
                    })

            st.success(
                "Structural analysis completed."
            )

            for item in results:

                with st.expander(
                    f"📄 {item['file']}"
                ):

                    if "error" in item:

                        st.error(
                            item["error"]
                        )

                    else:

                        result = item["analysis"]

                        if isinstance(
                            result,
                            (dict, list),
                        ):

                            st.json(
                                result
                            )

                        else:

                            st.write(
                                result
                            )

        except Exception as e:

            st.error(
                f"Analysis failed: {e}"
            )


# ============================================================
# PAGE 5 — ARCHITECTURE MODEL
# ============================================================

if page == "🏗️ Architecture Model":

    require_uploaded_files()

    st.header(
        "🏗️ Architecture Model"
    )

    st.write(
        """
        Recover a machine-readable representation of the
        architecture from the uploaded source code.
        """
    )

    if st.button(
        "🚀 Recover Architecture",
        type="primary",
    ):

        try:

            G = build_graph(
                parsed_files
            )

            st.markdown(
                "### Architecture Graph"
            )

            create_architecture_graph(
                G
            )

            st.divider()

            if ARCHITECTURE_MODEL_AVAILABLE:

                snapshot = recover_architecture(
                    parsed_files,
                    commit_hash="uploaded-code",
                )

                st.session_state[
                    "latest_architecture_snapshot"
                ] = snapshot

                st.session_state[
                    "architecture_snapshots"
                ].append(
                    snapshot
                )

                st.success(
                    "✅ Persistent architecture snapshot created."
                )

                display_architecture_snapshot(
                    snapshot,
                    "Current Architecture Snapshot",
                )

            else:

                st.warning(
                    "architecture_model package is not available. "
                    "The graph was recovered successfully, but a "
                    "persistent ArchitectureSnapshot could not be created."
                )

        except Exception as e:

            st.error(
                f"Architecture recovery failed: {e}"
            )

            st.exception(e)


# ============================================================
# PAGE 6 — DEPENDENCY ANALYSIS
# ============================================================

if page == "🔗 Dependency Analysis":

    require_uploaded_files()

    st.header(
        "🔗 Dependency Analysis"
    )

    st.write(
        """
        Recover direct dependencies between files/modules
        and inspect the resulting dependency graph.
        """
    )

    if st.button(
        "Generate Dependency Graph",
        type="primary",
    ):

        G = build_combined_dependency_graph(
            file_paths
        )

        if G.number_of_nodes() == 0:

            st.warning(
                "No dependencies detected."
            )

        else:

            create_architecture_graph(
                G
            )

            cycles = list(
                nx.simple_cycles(G)
            )

            st.subheader(
                "Circular Dependencies"
            )

            if cycles:

                st.error(
                    f"⚠️ {len(cycles)} circular dependency "
                    f"cycle(s) detected."
                )

                for cycle in cycles[:20]:

                    st.write(
                        " → ".join(
                            map(
                                str,
                                cycle,
                            )
                        )
                    )

            else:

                st.success(
                    "✅ No circular dependencies detected."
                )


# ============================================================
# PAGE 7 — ARCHITECTURE METRICS
# ============================================================

if page == "📊 Architecture Metrics":

    require_uploaded_files()

    st.header(
        "📊 Architecture Metrics"
    )

    st.write(
        """
        Quantitative measurements of the recovered architecture.
        These values are computed from the dependency graph rather
        than generated by an LLM.
        """
    )

    G = build_combined_dependency_graph(
        file_paths
    )

    if G.number_of_nodes() == 0:

        st.warning(
            "No architecture relationships detected."
        )

    else:

        components = G.number_of_nodes()

        dependencies = G.number_of_edges()

        density = nx.density(
            G
        )

        cycles = list(
            nx.simple_cycles(G)
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Components",
            components,
        )

        c2.metric(
            "Dependencies",
            dependencies,
        )

        c3.metric(
            "Graph Density",
            f"{density:.3f}",
        )

        c4.metric(
            "Cycles",
            len(cycles),
        )

        st.divider()

        st.subheader(
            "Component Connectivity"
        )

        degree_data = []

        for node in G.nodes():

            degree_data.append({

                "Component":
                    str(node),

                "Dependencies":
                    G.degree(node),

                "Incoming":
                    G.in_degree(node),

                "Outgoing":
                    G.out_degree(node),
            })

        degree_data.sort(
            key=lambda x:
                x["Dependencies"],
            reverse=True,
        )

        st.dataframe(
            degree_data,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# PAGE 8 — MODULE BOUNDARIES
# ============================================================

if page == "🧩 Module Boundaries":

    require_uploaded_files()

    st.header(
        "🧩 Architecture Module Boundaries"
    )

    st.caption(
        "Identify groups of strongly related components "
        "using graph community structure."
    )

    if not COMMUNITY_AVAILABLE:

        st.error(
            "community_detector.py is not available."
        )

    else:

        G = build_combined_dependency_graph(
            file_paths
        )

        if G.number_of_nodes() == 0:

            st.warning(
                "No dependency graph available."
            )

        elif st.button(
            "Detect Architecture Modules",
            type="primary",
        ):

            try:

                result = analyze_modularity(
                    G
                )

                if "error" in result:

                    st.error(
                        result["error"]
                    )

                else:

                    c1, c2 = st.columns(2)

                    c1.metric(
                        "Modularity",
                        result.get(
                            "modularity_score",
                            "N/A",
                        ),
                    )

                    c2.metric(
                        "Suggested Modules",
                        result.get(
                            "num_communities",
                            "N/A",
                        ),
                    )

                    if result.get(
                        "interpretation"
                    ):

                        st.info(
                            result[
                                "interpretation"
                            ]
                        )

                    st.subheader(
                        "Suggested Architecture Modules"
                    )

                    for (
                        community_id,
                        module,
                    ) in result.get(
                        "suggested_modules",
                        {},
                    ).items():

                        name = module.get(
                            "suggested_name",
                            f"Module {community_id}",
                        )

                        members = module.get(
                            "members",
                            [],
                        )

                        st.markdown(
                            f"### {name}"
                        )

                        st.write(
                            ", ".join(
                                map(
                                    str,
                                    members,
                                )
                            )
                        )

            except Exception as e:

                st.error(
                    f"Module detection failed: {e}"
                )


# ============================================================
# PAGE 9 — LOGICAL COUPLING
# ============================================================

if page == "🔀 Logical Coupling":

    st.header(
        "🔀 Architectural Logical Coupling"
    )

    st.write(
        """
        Detect files that repeatedly change together in Git history.
        This can reveal hidden architectural relationships that are
        not visible from direct dependencies alone.
        """
    )

    if not COUPLING_AVAILABLE:

        st.error(
            "coupling_miner.py is not available."
        )

    else:

        target = get_current_repository_path()

        if not target:

            st.warning(
                "Load a repository from the "
                "**📂 Repository Input** page first."
            )

        elif not git_repository_available():

            st.warning(
                "Logical coupling requires Git history. "
                "Load a Git repository containing `.git` history."
            )

        else:

            st.caption(
                f"Repository: `{target}`"
            )

            if st.button(
                "Analyze Logical Coupling",
                type="primary",
            ):

                try:

                    result = mine_logical_coupling(
                        target
                    )

                    c1, c2 = st.columns(2)

                    c1.metric(
                        "Commits Analyzed",
                        result.get(
                            "commits_analyzed",
                            0,
                        ),
                    )

                    c2.metric(
                        "Files Analyzed",
                        result.get(
                            "files_analyzed",
                            0,
                        ),
                    )

                    couplings = result.get(
                        "couplings",
                        [],
                    )

                    if not couplings:

                        st.info(
                            "No significant logical coupling detected."
                        )

                    else:

                        for item in couplings[:20]:

                            st.markdown(
                                f"""
                                **{item.get('file_a', 'Unknown')}**
                                ↔
                                **{item.get('file_b', 'Unknown')}**

                                - Coupling score: **{item.get('coupling_score', 0)}%**
                                - Changed together: **{item.get('co_change_count', 0)} times**
                                """
                            )

                            st.divider()

                except Exception as e:

                    st.error(
                        f"Logical coupling analysis failed: {e}"
                    )


# ============================================================
# PAGE 10 — ARCHITECTURE RISK
# ============================================================

if page == "🔥 Architecture Risk":

    require_uploaded_files()

    st.header(
        "🔥 Architecture Risk Analysis"
    )

    st.write(
        """
        Identify components that may become architectural hotspots
        using structural complexity and repository change evidence.
        """
    )

    target = get_current_repository_path()

    if not RISK_AVAILABLE:

        st.error(
            "risk_predictor.py is not available."
        )

    elif not target:

        st.warning(
            "Load a repository first."
        )

    elif not git_repository_available():

        st.warning(
            "Architecture Risk requires Git history."
        )

    elif st.button(
        "Compute Architecture Risk",
        type="primary",
    ):

        try:

            results = compute_risk_scores(
                parsed_files,
                repo_path=target,
                max_commits=300,
            )

            if not results:

                st.info(
                    "No risk results were generated."
                )

            for item in results[:25]:

                label = item.get(
                    "risk_label",
                    "UNKNOWN",
                )

                message = (
                    f"**{item.get('file', 'Unknown')}** — "
                    f"risk {item.get('risk_score', 0)}/100 "
                    f"[{label}]"
                )

                if label == "HIGH":

                    st.error(
                        message
                    )

                elif label == "MEDIUM":

                    st.warning(
                        message
                    )

                else:

                    st.success(
                        message
                    )

                st.caption(
                    f"Complexity: {item.get('complexity', 0)} | "
                    f"Churn: {item.get('churn', 0)} | "
                    f"Bug-fix commits: {item.get('bugfix_count', 0)}"
                )

        except Exception as e:

            st.error(
                f"Risk analysis failed: {e}"
            )

            st.exception(e)


# ============================================================
# PAGE 11 — ARCHITECTURE DEBT
# ============================================================

if page == "💰 Architecture Debt":

    require_uploaded_files()

    st.header(
        "💰 Architecture Debt"
    )

    st.write(
        """
        Architecture debt measures structural problems that make
        the architecture harder to maintain or evolve.
        """
    )

    if not TECH_DEBT_AVAILABLE:

        st.error(
            "techdebt.py is not available."
        )

    elif st.button(
        "Calculate Architecture Debt",
        type="primary",
    ):

        try:

            result = calculate_technical_debt(
                parsed_files
            )

            c1, c2 = st.columns(2)

            c1.metric(
                "Estimated Remediation Hours",
                f"{result.get('estimated_hours', 0)} hrs",
            )

            c2.metric(
                "Estimated Cost",
                f"₹{result.get('estimated_cost', 0)}",
            )

            st.divider()

            st.subheader(
                "Current Structural Indicators"
            )

            st.write(
                f"Functions: "
                f"{result.get('functions', 0)}"
            )

            st.write(
                f"Classes: "
                f"{result.get('classes', 0)}"
            )

            st.write(
                f"Complexity penalty: "
                f"{result.get('complexity_penalty', 0)} hrs"
            )

            st.write(
                f"Long-function penalty: "
                f"{result.get('long_function_penalty', 0)} hrs"
            )

            st.info(
                """
                Note: this existing estimator is currently a
                baseline. Later it should be replaced with a
                dedicated **Architecture Debt Index** based on
                coupling, cycles, boundary violations and
                architecture-rule violations.
                """
            )

        except Exception as e:

            st.error(
                f"Architecture debt calculation failed: {e}"
            )


# ============================================================
# PAGE 12 — ARCHITECTURE HEALTH
# ============================================================

if page == "🩺 Architecture Health":

    require_uploaded_files()

    st.header(
        "🩺 Architecture Health"
    )

    st.caption(
        "A transparent baseline health index computed from the recovered "
        "architecture graph and module structure. No LLM-generated scores."
    )

    G = build_combined_dependency_graph(
        file_paths
    )

    if G.number_of_nodes() == 0:

        st.warning(
            "No architecture graph is available yet."
        )

        st.info(
            "Load a repository with Python source files first."
        )

    else:

        node_count = G.number_of_nodes()

        edge_count = G.number_of_edges()

        density = nx.density(G)

        cycles = list(
            nx.simple_cycles(G)
        )

        coupling_health = max(
            0.0,
            min(
                100.0,
                100.0
                * (
                    1.0
                    - min(
                        1.0,
                        density * 2.0,
                    )
                ),
            ),
        )

        cycle_ratio = min(
            1.0,
            len(cycles)
            / max(
                1,
                node_count,
            ),
        )

        cycle_health = (
            100.0
            * (
                1.0
                - cycle_ratio
            )
        )

        modularity_score = None

        module_count = None

        if COMMUNITY_AVAILABLE:

            try:

                modularity_result = analyze_modularity(
                    G
                )

                raw_modularity = modularity_result.get(
                    "modularity_score"
                )

                if isinstance(
                    raw_modularity,
                    (int, float),
                ):

                    modularity_score = max(
                        0.0,
                        min(
                            100.0,
                            (
                                (
                                    float(
                                        raw_modularity
                                    )
                                    + 1.0
                                )
                                / 2.0
                            )
                            * 100.0,
                        ),
                    )

                module_count = modularity_result.get(
                    "num_communities"
                )

            except Exception:

                modularity_score = None

        health_parts = [
            coupling_health,
            cycle_health,
        ]

        if modularity_score is not None:

            health_parts.append(
                modularity_score
            )

        health = (
            sum(health_parts)
            / len(health_parts)
        )

        if health >= 80:

            health_label = "HEALTHY"

        elif health >= 60:

            health_label = "NEEDS ATTENTION"

        else:

            health_label = "AT RISK"

        st.markdown(
            "### Overall Architecture Health"
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Health Score",
            f"{health:.1f}/100",
        )

        c2.metric(
            "Status",
            health_label,
        )

        c3.metric(
            "Architecture Nodes",
            node_count,
        )

        st.progress(
            max(
                0.0,
                min(
                    1.0,
                    health / 100.0,
                ),
            )
        )

        st.divider()

        st.markdown(
            "### Evidence Behind the Score"
        )

        metric_rows = [

            {
                "Indicator":
                    "Dependency Coupling Health",

                "Score":
                    round(
                        coupling_health,
                        1,
                    ),

                "Evidence":
                    f"Graph density = {density:.4f}",
            },

            {
                "Indicator":
                    "Cycle Health",

                "Score":
                    round(
                        cycle_health,
                        1,
                    ),

                "Evidence":
                    f"{len(cycles)} cycle(s) across "
                    f"{node_count} nodes",
            },
        ]

        if modularity_score is not None:

            metric_rows.append({

                "Indicator":
                    "Modularity Health",

                "Score":
                    round(
                        modularity_score,
                        1,
                    ),

                "Evidence":
                    (
                        f"Detected {module_count} module(s)"
                        if module_count is not None
                        else
                        "Community analysis available"
                    ),
            })

        st.dataframe(
            metric_rows,
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        st.markdown(
            "### Architecture Facts"
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Components",
            node_count,
        )

        c2.metric(
            "Dependencies",
            edge_count,
        )

        c3.metric(
            "Cycles",
            len(cycles),
        )

        if cycles:

            with st.expander(
                "View detected cycles"
            ):

                for cycle in cycles[:20]:

                    st.write(
                        " → ".join(
                            map(
                                str,
                                cycle,
                            )
                        )
                    )

        st.info(
            """
            **Important:** this is the first transparent baseline of the
            Architecture Health Index. It intentionally does not invent
            weights for Risk, Debt, Logical Coupling, or Boundary
            Violations yet.

            The next implementation step will make this a research-grade
            composite index using evidence from the existing analysis
            modules.
            """
        )


# ============================================================
# PAGE 13 — SEMANTIC EMBEDDINGS
# ============================================================

if page == "🔢 Semantic Embeddings":

    require_uploaded_files()

    st.header(
        "🔢 Semantic Architecture Evidence"
    )

    st.write(
        """
        Generate semantic representations of the parsed code.

        These embeddings are intentionally retained because they
        will later become part of the Architecture-aware RAG layer.
        """
    )

    if not parsed_files:

        st.warning(
            "No parsed files available."
        )

    elif st.button(
        "Generate Semantic Representation",
        type="primary",
    ):

        try:

            # Preserve the existing embedder implementation.
            embedding = embed_parsed_result(
                parsed_files[0]
            )

            st.success(
                "Semantic representation generated."
            )

            if hasattr(
                embedding,
                "shape",
            ):

                st.write(
                    f"Embedding shape: {embedding.shape}"
                )

                st.write(
                    embedding[:10]
                )

            else:

                try:

                    st.write(
                        embedding[:10]
                    )

                except Exception:

                    st.write(
                        embedding
                    )

        except Exception as e:

            st.error(
                f"Embedding generation failed: {e}"
            )


# ============================================================
# PAGE 14 — REPOSITORY INPUT
# ============================================================

if page == "📂 Repository Input":

    st.header(
        "📂 Analyze Repository"
    )

    st.write(
        """
        Provide the software system that should be analyzed.

        The repository is the **input/evidence source** for the
        architecture intelligence engine. This page only loads the
        repository; the actual architecture analysis happens in
        the analysis pages.
        """
    )

    st.markdown(
        "### Choose an input method"
    )

    input_method = st.radio(
        "Repository source",
        [
            "GitHub URL",
            "Upload ZIP",
        ],
        horizontal=True,
        key="repository_input_method",
    )

    # --------------------------------------------------------
    # GITHUB
    # --------------------------------------------------------

    if input_method == "GitHub URL":

        github_url = st.text_input(
            "Public GitHub Repository URL",
            placeholder=(
                "https://github.com/username/repository"
            ),
            key="github_repository_url",
        )

        if st.button(
            "Load Repository",
            type="primary",
            key="load_github_repository",
        ):

            if not github_url.strip():

                st.warning(
                    "Please enter a GitHub repository URL."
                )

            else:

                try:

                    with st.spinner(
                        "Cloning repository..."
                    ):

                        repo_path = clone_github_repository(
                            github_url.strip()
                        )

                    python_files = get_python_files(
                        repo_path
                    )

                    # Clear previous state.
                    st.session_state[
                        "uploaded_file_data"
                    ] = []

                    st.session_state[
                        "architecture_snapshots"
                    ] = []

                    st.session_state[
                        "latest_architecture_snapshot"
                    ] = None

                    # Store new repository.
                    st.session_state[
                        "github_repo_path"
                    ] = repo_path

                    st.session_state[
                        "repository_local_path"
                    ] = None

                    st.session_state[
                        "repository_source"
                    ] = "GitHub"

                    st.session_state[
                        "repository_name"
                    ] = get_repository_name(
                        repo_path
                    )

                    st.session_state[
                        "repository_file_paths"
                    ] = python_files

                    # IMPORTANT:
                    # Store the URL under the same key used
                    # everywhere else.
                    st.session_state[
                        "repository_url"
                    ] = github_url.strip()

                    st.success(
                        "✅ Repository loaded successfully. "
                        "It is now available to the architecture "
                        "analysis engine."
                    )

                except Exception as e:

                    st.error(
                        f"❌ Repository loading failed: {e}"
                    )

                    st.exception(e)

    # --------------------------------------------------------
    # ZIP
    # --------------------------------------------------------

    else:

        uploaded_zip = st.file_uploader(
            "Upload repository as ZIP",
            type=["zip"],
            key="repository_zip_upload",
        )

        if st.button(
            "Load ZIP Repository",
            type="primary",
            key="load_zip_repository",
        ):

            if uploaded_zip is None:

                st.warning(
                    "Please upload a ZIP file first."
                )

            else:

                try:

                    with st.spinner(
                        "Extracting repository..."
                    ):

                        repo_path = (
                            extract_uploaded_repository(
                                uploaded_zip
                            )
                        )

                    python_files = get_python_files(
                        repo_path
                    )

                    # Clear previous state.
                    st.session_state[
                        "uploaded_file_data"
                    ] = []

                    st.session_state[
                        "architecture_snapshots"
                    ] = []

                    st.session_state[
                        "latest_architecture_snapshot"
                    ] = None

                    # Store ZIP repository.
                    st.session_state[
                        "github_repo_path"
                    ] = repo_path

                    st.session_state[
                        "repository_local_path"
                    ] = repo_path

                    st.session_state[
                        "repository_source"
                    ] = "ZIP"

                    st.session_state[
                        "repository_name"
                    ] = get_repository_name(
                        repo_path
                    )

                    st.session_state[
                        "repository_file_paths"
                    ] = python_files

                    st.session_state[
                        "repository_url"
                    ] = None

                    st.success(
                        "✅ ZIP repository loaded successfully. "
                        "It is now available to the architecture "
                        "analysis engine."
                    )

                except Exception as e:

                    st.error(
                        f"❌ ZIP repository loading failed: {e}"
                    )

                    st.exception(e)

    # --------------------------------------------------------
    # CURRENT REPOSITORY STATUS
    # --------------------------------------------------------

    repo_files = st.session_state.get(
        "repository_file_paths",
        [],
    )

    if repo_files:

        st.divider()

        st.subheader(
            "Repository Ready"
        )

        source = st.session_state.get(
            "repository_source",
            "Unknown",
        )

        name = st.session_state.get(
            "repository_name",
            "Repository",
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Repository",
            name,
        )

        c2.metric(
            "Source",
            source,
        )

        c3.metric(
            "Python Files",
            len(repo_files),
        )

        if git_repository_available():

            st.success(
                "🟢 Git history detected. "
                "Architecture Time Machine, Logical Coupling, "
                "and Git-based Risk analysis are available."
            )

        else:

            st.info(
                "🔵 Structural repository analysis is available. "
                "Git-history-based features require a repository "
                "with valid Git history."
            )

        with st.expander(
            "View discovered Python files"
        ):

            for path in repo_files:

                st.write(
                    f"📄 {get_relative_file_name(path)}"
                )

        if source == "ZIP":

            st.info(
                "ZIP input supports structural architecture analysis. "
                "If the ZIP does not contain `.git` history, "
                "Git-history-based features such as Logical Coupling "
                "and the Architecture Time Machine will remain unavailable."
            )


# ============================================================
# PAGE 15 — ARCHITECTURE TIME MACHINE
# ============================================================

if page == "⏳ Architecture Time Machine":

    st.markdown(
        "## ⏳ Architecture Time Machine"
    )

    st.caption(
        "Recover the software architecture at different Git commits "
        "and inspect how the architecture evolved over time."
    )

    repo_path = get_current_repository_path()

    if not repo_path:

        st.warning(
            "🐙 Please load a GitHub repository from the "
            "**📂 Repository Input** page first."
        )

    elif not git_repository_available():

        st.warning(
            "🐙 Architecture Time Machine requires a valid Git repository "
            "with commit history. A normal ZIP containing only source "
            "files cannot provide historical architecture snapshots."
        )

    elif not ARCHITECTURE_MODEL_AVAILABLE:

        st.error(
            "The `architecture_model` package is not available. "
            "The Time Machine cannot create ArchitectureSnapshot objects."
        )

    else:

        repository_url = st.session_state.get(
            "repository_url"
        )

        st.success(
            f"Repository loaded: "
            f"`{repository_url or repo_path}`"
        )

        try:

            repo = Repo(
                repo_path
            )

            commits = list(
                repo.iter_commits(
                    "--all"
                )
            )

        except Exception as e:

            st.error(
                f"Could not read Git history: {e}"
            )

            commits = []

        if not commits:

            st.warning(
                "No Git commits were found."
            )

        else:

            commit_options = {}

            for commit in commits:

                short_hash = (
                    commit.hexsha[:7]
                )

                message = (
                    commit.message
                    .strip()
                    .splitlines()[0]
                    if commit.message.strip()
                    else "No commit message"
                )

                label = (
                    f"{short_hash} — {message}"
                )

                commit_options[
                    label
                ] = commit.hexsha

            selected_commit_label = st.selectbox(
                "🕐 Select a Git commit",
                list(
                    commit_options.keys()
                ),
                key="architecture_tm_commit",
            )

            selected_commit_hash = (
                commit_options[
                    selected_commit_label
                ]
            )

            try:

                selected_commit = repo.commit(
                    selected_commit_hash
                )

            except Exception as e:

                st.error(
                    f"Could not load selected commit: {e}"
                )

                selected_commit = None

            if selected_commit:

                st.markdown(
                    "### 📌 Selected Commit"
                )

                c1, c2, c3 = st.columns(3)

                c1.metric(
                    "Commit",
                    selected_commit_hash[:7],
                )

                c2.metric(
                    "Author",
                    selected_commit.author.name
                    or "Unknown",
                )

                c3.metric(
                    "Date",
                    selected_commit.committed_datetime.strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                )

                st.write(
                    f"**Message:** "
                    f"{selected_commit.message.strip()}"
                )

                if st.button(
                    "🏗️ Recover Architecture at This Commit",
                    type="primary",
                    use_container_width=True,
                    key="recover_architecture_commit",
                ):

                    with st.spinner(
                        "Recovering architecture from the selected commit..."
                    ):

                        try:

                            snapshot = (
                                recover_architecture_from_commit(
                                    repo_path,
                                    selected_commit_hash,
                                )
                            )

                            st.session_state[
                                "latest_architecture_snapshot"
                            ] = snapshot

                            if (
                                "architecture_snapshots"
                                not in st.session_state
                            ):

                                st.session_state[
                                    "architecture_snapshots"
                                ] = []

                            existing_hashes = [

                                getattr(
                                    s,
                                    "commit_hash",
                                    "",
                                )

                                for s in
                                st.session_state[
                                    "architecture_snapshots"
                                ]
                            ]

                            if (
                                selected_commit_hash
                                not in existing_hashes
                            ):

                                st.session_state[
                                    "architecture_snapshots"
                                ].append(
                                    snapshot
                                )

                            st.success(
                                "✅ Architecture recovered successfully."
                            )

                            display_architecture_snapshot(
                                snapshot,
                                "Recovered Architecture",
                            )

                            G_snapshot = (
                                architecture_snapshot_to_graph(
                                    snapshot
                                )
                            )

                            if (
                                G_snapshot.number_of_nodes()
                                > 0
                            ):

                                st.markdown(
                                    "### 🗺️ Recovered Architecture Graph"
                                )

                                create_animated_architecture(
                                    G_snapshot
                                )

                            else:

                                st.info(
                                    "The selected commit does not contain "
                                    "enough recoverable architecture components "
                                    "to display a graph."
                                )

                        except Exception as e:

                            st.error(
                                f"❌ Architecture recovery failed: {e}"
                            )

                            st.exception(e)

                # ------------------------------------------------
                # SNAPSHOTS
                # ------------------------------------------------

                st.divider()

                st.markdown(
                    "### 📚 Recovered Architecture Snapshots"
                )

                snapshots = st.session_state.get(
                    "architecture_snapshots",
                    [],
                )

                if not snapshots:

                    st.info(
                        "No architecture snapshots have been created yet."
                    )

                else:

                    for i, snapshot in enumerate(
                        reversed(snapshots),
                        1,
                    ):

                        data = snapshot_to_dict(
                            snapshot
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

                        commit_hash = data.get(
                            "commit_hash",
                            "unknown",
                        )

                        with st.expander(
                            f"📸 Snapshot {i} — "
                            f"{str(commit_hash)[:7]}"
                        ):

                            c1, c2, c3, c4 = st.columns(4)

                            c1.metric(
                                "Commit",
                                str(
                                    commit_hash
                                )[:7],
                            )

                            c2.metric(
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

                            c3.metric(
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

                            c4.metric(
                                "Files",
                                metrics.get(
                                    "total_files",
                                    0,
                                ),
                            )

                            st.json(
                                data,
                                expanded=False,
                            )

                # ------------------------------------------------
                # COMPARE SNAPSHOTS
                # ------------------------------------------------

                if len(snapshots) >= 2:

                    st.divider()

                    st.markdown(
                        "### 🔄 Architecture Evolution"
                    )

                    st.caption(
                        "Compare recovered architecture snapshots "
                        "across Git commits."
                    )

                    comparison_rows = []

                    for snapshot in snapshots:

                        data = snapshot_to_dict(
                            snapshot
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

                        comparison_rows.append({

                            "Commit":
                                str(
                                    data.get(
                                        "commit_hash",
                                        "unknown",
                                    )
                                )[:7],

                            "Components":
                                metrics.get(
                                    "total_components",
                                    len(
                                        data.get(
                                            "components",
                                            [],
                                        )
                                    ),
                                ),

                            "Relationships":
                                metrics.get(
                                    "total_relationships",
                                    len(
                                        data.get(
                                            "relationships",
                                            [],
                                        )
                                    ),
                                ),

                            "Files":
                                metrics.get(
                                    "total_files",
                                    0,
                                ),

                            "Violations":
                                len(
                                    data.get(
                                        "violations",
                                        [],
                                    )
                                ),
                        })

                    st.dataframe(
                        comparison_rows,
                        use_container_width=True,
                        hide_index=True,
                    )


# ============================================================
# CLEANUP
# ============================================================

if (
    file_paths
    and not st.session_state.get(
        "repository_file_paths"
    )
):

    cleanup_temp_files(
        file_paths
    )