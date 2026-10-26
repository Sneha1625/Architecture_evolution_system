import sqlite3
from pathlib import Path
from features.ai_analysis import render_ai_analysis
import streamlit as st
from git import Repo
import tempfile

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

# ============================================================
# REPOSITORY INPUT / COMMIT SELECTION
# ============================================================
st.sidebar.markdown("## GitHub Repository Input")
github_url = st.sidebar.text_input(
    "Enter GitHub Repository URL",
    placeholder="https://github.com/username/repository.git",
    key="evolution_github_url",
)

if "evolution_repo_path" not in st.session_state:
    st.session_state.evolution_repo_path = None
if "evolution_repo_url" not in st.session_state:
    st.session_state.evolution_repo_url = None

if st.sidebar.button("Load Repository", key="evolution_load_repo"):
    if not github_url.strip():
        st.sidebar.warning("Please enter a GitHub URL.")
    elif not github_url.strip().startswith(("https://github.com/", "http://github.com/")):
        st.sidebar.error("Please enter a public GitHub repository URL.")
    else:
        try:
            with st.spinner("Cloning repository..."):
                repo_folder = Path(tempfile.mkdtemp(prefix="evolution_repo_"))
                Repo.clone_from(github_url.strip(), str(repo_folder))
                st.session_state.evolution_repo_path = str(repo_folder)
                st.session_state.evolution_repo_url = github_url.strip()
                st.session_state.pop("evolution_selected_commit", None)
            st.sidebar.success("Repository cloned successfully.")
        except Exception as error:
            st.sidebar.error(f"Repository loading failed: {error}")

if st.session_state.evolution_repo_path:
    try:
        active_repo = Repo(st.session_state.evolution_repo_path)
        commits = list(active_repo.iter_commits(max_count=100))
        if commits:
            commit_labels = [
                f"{c.hexsha[:8]} — {c.summary[:75]}" for c in commits
            ]
            selected_label = st.sidebar.selectbox(
                "Select Git Commit", commit_labels,
                key="evolution_selected_commit_label",
            )
            selected_index = commit_labels.index(selected_label)
            st.session_state.evolution_selected_commit = commits[selected_index].hexsha
            st.sidebar.caption(f"Selected: {commits[selected_index].hexsha[:8]}")
        else:
            st.sidebar.warning("No commits found.")
    except Exception as error:
        st.sidebar.error(f"Unable to read Git history: {error}")


from features.architecture_history import render_architecture_history
from features.runtime_architecture import render_runtime_architecture
from features.runtime_pipeline import run_repository_parser
# ============================================================
# DATABASE
# ============================================================

def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def database_exists():
    return DATABASE_PATH.exists()

