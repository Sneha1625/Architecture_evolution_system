"""
Git history logical coupling analysis.

The Streamlit app clones a GitHub repository first and passes the
local clone path to mine_logical_coupling().
"""

from itertools import combinations
from pathlib import Path

from git import Repo, InvalidGitRepositoryError, NoSuchPathError


IGNORED_DIRECTORIES = {
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", ".venv", "venv",
    "env", "node_modules", "site-packages", "dist", "build",
    "coverage", "htmlcov", ".idea", ".vscode",
}

IGNORED_SUFFIXES = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".class",
    ".jar", ".war", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".pdf", ".db", ".sqlite", ".sqlite3", ".bin", ".dat",
}


def _is_relevant_file(path):
    """Exclude generated/cache/binary artifacts from source-history mining."""
    normalized = Path(path).as_posix()
    parts = [part.lower() for part in Path(normalized).parts]

    if any(part in IGNORED_DIRECTORIES for part in parts[:-1]):
        return False

    suffix = Path(normalized).suffix.lower()
    if suffix in IGNORED_SUFFIXES:
        return False

    name = Path(normalized).name.lower()
    if name.endswith((".min.js", ".min.css", ".map")):
        return False

    return True


def mine_logical_coupling(repo_path, min_commits=2):
    """
    Analyze a Git repository's history and find files that are
    frequently changed together.

    Parameters
    ----------
    repo_path : str
        Local path to a Git repository.

    min_commits : int
        Minimum number of commits in which two files must be changed
        together before they are considered logically coupled.

    Returns
    -------
    dict
        Contains:
        - commits_analyzed
        - files_analyzed
        - couplings
        - ignored_root_commit: whether the initial baseline commit was excluded
        - ignored_artifact_paths: generated/binary paths excluded from analysis
    """

    # ---------------------------------------------------------
    # Convert repository path to an absolute Path
    # ---------------------------------------------------------

    repo_path = Path(repo_path).resolve()

    # ---------------------------------------------------------
    # Open Git repository
    # ---------------------------------------------------------

    try:
        repo = Repo(str(repo_path))

    except (InvalidGitRepositoryError, NoSuchPathError) as exc:
        raise ValueError(
            f"Not a valid Git repository: {repo_path}"
        ) from exc

    if repo.bare:
        raise ValueError(
            "The Git repository is bare."
        )

    # ---------------------------------------------------------
    # Data structures
    # ---------------------------------------------------------

    pair_counts = {}

    file_commit_counts = {}

    all_files = set()

    commits_analyzed = 0
    ignored_artifact_paths = set()
    ignored_root_commit = False

    for commit in repo.iter_commits():

        changed_files = set()

        try:
            # -------------------------------------------------
            # Ignore the root commit: it establishes the initial
            # baseline rather than recording a meaningful change
            # between two versions. Counting every baseline file
            # as co-changed creates artificial coupling.
            # -------------------------------------------------

            if not commit.parents:
                ignored_root_commit = True
                continue

            # -------------------------------------------------
            # Normal commit
            # -------------------------------------------------

            if commit.parents:

                parent = commit.parents[0]

                for diff in parent.diff(
                    commit,
                    create_patch=False
                ):

                    # File before the change
                    if diff.a_path:
                        if _is_relevant_file(diff.a_path):
                            changed_files.add(Path(diff.a_path).as_posix())
                        else:
                            ignored_artifact_paths.add(Path(diff.a_path).as_posix())

                    # File after the change
                    if diff.b_path:
                        if _is_relevant_file(diff.b_path):
                            changed_files.add(Path(diff.b_path).as_posix())
                        else:
                            ignored_artifact_paths.add(Path(diff.b_path).as_posix())

        except Exception:
            # Skip commits that cannot be processed.
            continue

        # -----------------------------------------------------
        # Ignore commits without changed files
        # -----------------------------------------------------

        if not changed_files:
            continue

        commits_analyzed += 1

        # Add files to overall file set
        all_files.update(
            changed_files
        )

        # -----------------------------------------------------
        # Count how many commits changed each file
        # -----------------------------------------------------

        for file_path in changed_files:

            file_commit_counts[file_path] = (
                file_commit_counts.get(
                    file_path,
                    0
                ) + 1
            )

        # -----------------------------------------------------
        # Count file pairs changed in the same commit
        # -----------------------------------------------------

        for file_a, file_b in combinations(
            sorted(changed_files),
            2
        ):

            pair = (
                file_a,
                file_b
            )

            pair_counts[pair] = (
                pair_counts.get(
                    pair,
                    0
                ) + 1
            )

    # ---------------------------------------------------------
    # Calculate logical coupling
    # ---------------------------------------------------------

    couplings = []

    for (
        file_a,
        file_b
    ), co_change_count in pair_counts.items():

        # Only consider pairs changed together at least
        # min_commits times.
        if co_change_count < min_commits:
            continue

        file_a_commits = file_commit_counts.get(
            file_a,
            0
        )

        file_b_commits = file_commit_counts.get(
            file_b,
            0
        )

        # Use the less frequently changed file as denominator.
        denominator = min(
            file_a_commits,
            file_b_commits
        )

        if denominator == 0:
            continue

        # -----------------------------------------------------
        # Coupling score
        # -----------------------------------------------------
        #
        # Example:
        #
        # analyzer.py changed in 3 commits
        # parser.py changed in 3 commits
        # changed together in 3 commits
        #
        # score = 3 / 3 * 100 = 100%
        # -----------------------------------------------------

        coupling_score = (
            co_change_count
            / denominator
        ) * 100

        coupling_score = min(
            coupling_score,
            100.0
        )

        couplings.append(
            {
                "file_a": file_a,

                "file_b": file_b,

                "coupling_score": round(
                    coupling_score,
                    1
                ),

                "co_change_count": (
                    co_change_count
                ),

                "file_a_commits": (
                    file_a_commits
                ),

                "file_b_commits": (
                    file_b_commits
                ),

                "reference_frequency": (
                    denominator
                ),
            }
        )

    # ---------------------------------------------------------
    # Sort strongest relationships first
    # ---------------------------------------------------------

    couplings.sort(
        key=lambda item: (
            item["coupling_score"],
            item["co_change_count"]
        ),
        reverse=True
    )

    # ---------------------------------------------------------
    # Return results to Streamlit
    # ---------------------------------------------------------

    return {
        "commits_analyzed": (
            commits_analyzed
        ),

        "files_analyzed": (
            len(all_files)
        ),

        "couplings": couplings,
        "ignored_root_commit": ignored_root_commit,
        "ignored_artifact_paths": len(ignored_artifact_paths),
    }