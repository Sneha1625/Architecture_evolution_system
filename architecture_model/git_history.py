"""
git_history.py
--------------

Git history utilities for the Persistent Architecture Digital Twin.

Responsibilities:

1. Detect whether a directory is a Git repository.
2. Read Git commits.
3. Get commit metadata.
4. Get changed files between commits.
5. Checkout commits temporarily.
6. Restore the original branch/commit after analysis.

This module does NOT perform architecture recovery itself.

Pipeline:

    Git Repository
          ↓
    git_history.py
          ↓
    Commit information
          ↓
    recovery.py
          ↓
    ArchitectureSnapshot
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


# ============================================================
# DATA MODEL
# ============================================================


@dataclass
class GitCommit:
    """
    Represents one Git commit.
    """

    hash: str
    short_hash: str
    author: str
    timestamp: str
    message: str


# ============================================================
# GIT COMMAND HELPER
# ============================================================


def run_git(
    repository_path: str | Path,
    *arguments: str,
) -> str:
    """
    Execute a Git command inside a repository.

    Parameters
    ----------
    repository_path:
        Path to the Git repository.

    arguments:
        Git command arguments.

    Returns
    -------
    str
        Command output.

    Raises
    ------
    RuntimeError
        If Git command fails.
    """

    repository_path = Path(repository_path).resolve()

    command = [
        "git",
        "-C",
        str(repository_path),
        *arguments,
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    except FileNotFoundError as error:

        raise RuntimeError(
            "Git was not found on the system. "
            "Make sure Git is installed and available "
            "in PATH."
        ) from error

    if result.returncode != 0:

        error_message = (
            result.stderr.strip()
            or result.stdout.strip()
            or "Unknown Git error"
        )

        raise RuntimeError(
            f"Git command failed:\n"
            f"git {' '.join(arguments)}\n\n"
            f"{error_message}"
        )

    return result.stdout.strip()


# ============================================================
# REPOSITORY DETECTION
# ============================================================


def is_git_repository(
    repository_path: str | Path,
) -> bool:
    """
    Check whether a directory is a Git repository.

    Returns
    -------
    bool
    """

    path = Path(repository_path)

    if not path.exists():
        return False

    if not path.is_dir():
        return False

    try:

        run_git(
            path,
            "rev-parse",
            "--is-inside-work-tree",
        )

        return True

    except RuntimeError:

        return False


# ============================================================
# CURRENT COMMIT
# ============================================================


def get_current_commit(
    repository_path: str | Path,
) -> str:
    """
    Return the full hash of the currently checked-out commit.
    """

    return run_git(
        repository_path,
        "rev-parse",
        "HEAD",
    )


# ============================================================
# CURRENT BRANCH
# ============================================================


def get_current_branch(
    repository_path: str | Path,
) -> Optional[str]:
    """
    Return the current branch name.

    Returns None when the repository is in detached HEAD state.
    """

    branch = run_git(
        repository_path,
        "branch",
        "--show-current",
    )

    if not branch:
        return None

    return branch


# ============================================================
# COMMIT INFORMATION
# ============================================================


def get_commit(
    repository_path: str | Path,
    commit_hash: str = "HEAD",
) -> GitCommit:
    """
    Get information about one Git commit.
    """

    output = run_git(
        repository_path,
        "show",
        "-s",
        "--format=%H%x1f%h%x1f%an%x1f%aI%x1f%s",
        commit_hash,
    )

    parts = output.split("\x1f")

    if len(parts) != 5:

        raise RuntimeError(
            "Unable to parse Git commit information."
        )

    return GitCommit(
        hash=parts[0],
        short_hash=parts[1],
        author=parts[2],
        timestamp=parts[3],
        message=parts[4],
    )


# ============================================================
# GET COMMITS
# ============================================================


def get_commits(
    repository_path: str | Path,
    limit: Optional[int] = None,
) -> List[GitCommit]:
    """
    Return commits from newest to oldest.

    Parameters
    ----------
    repository_path:
        Git repository.

    limit:
        Maximum number of commits.

        None means all commits.
    """

    arguments = [
        "log",
        "--format=%H%x1f%h%x1f%an%x1f%aI%x1f%s",
    ]

    if limit is not None:

        if limit <= 0:
            return []

        arguments.append(
            f"-n{limit}"
        )

    output = run_git(
        repository_path,
        *arguments,
    )

    if not output:
        return []

    commits = []

    for line in output.splitlines():

        parts = line.split("\x1f")

        if len(parts) != 5:
            continue

        commits.append(
            GitCommit(
                hash=parts[0],
                short_hash=parts[1],
                author=parts[2],
                timestamp=parts[3],
                message=parts[4],
            )
        )

    return commits


# ============================================================
# GET COMMIT HISTORY
# ============================================================


def get_commit_hashes(
    repository_path: str | Path,
    limit: Optional[int] = None,
) -> List[str]:
    """
    Return commit hashes from newest to oldest.
    """

    commits = get_commits(
        repository_path,
        limit=limit,
    )

    return [
        commit.hash
        for commit in commits
    ]


# ============================================================
# CHANGED FILES
# ============================================================


def get_changed_files(
    repository_path: str | Path,
    commit_hash: str,
) -> List[str]:
    """
    Return files changed by a specific commit.

    The paths are relative to the repository root.
    """

    output = run_git(
        repository_path,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        commit_hash,
    )

    if not output:
        return []

    return [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]


# ============================================================
# FILES BETWEEN COMMITS
# ============================================================


def get_changed_files_between(
    repository_path: str | Path,
    old_commit: str,
    new_commit: str,
) -> List[str]:
    """
    Return files changed between two commits.
    """

    output = run_git(
        repository_path,
        "diff",
        "--name-only",
        old_commit,
        new_commit,
    )

    if not output:
        return []

    return [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]


# ============================================================
# COMMIT PARENTS
# ============================================================


def get_parent_commits(
    repository_path: str | Path,
    commit_hash: str,
) -> List[str]:
    """
    Return parent commit hashes for a commit.
    """

    output = run_git(
        repository_path,
        "rev-list",
        "--parents",
        "-n",
        "1",
        commit_hash,
    )

    parts = output.split()

    if len(parts) <= 1:
        return []

    return parts[1:]


# ============================================================
# PREVIOUS COMMIT
# ============================================================


def get_previous_commit(
    repository_path: str | Path,
    commit_hash: str,
) -> Optional[str]:
    """
    Return the first parent of a commit.

    Returns None if the commit has no parent.
    """

    parents = get_parent_commits(
        repository_path,
        commit_hash,
    )

    if not parents:
        return None

    return parents[0]


# ============================================================
# CHECK COMMIT EXISTS
# ============================================================


def commit_exists(
    repository_path: str | Path,
    commit_hash: str,
) -> bool:
    """
    Check whether a commit exists in the repository.
    """

    try:

        run_git(
            repository_path,
            "cat-file",
            "-e",
            f"{commit_hash}^{{commit}}",
        )

        return True

    except RuntimeError:

        return False


# ============================================================
# CHECKOUT COMMIT
# ============================================================


def checkout_commit(
    repository_path: str | Path,
    commit_hash: str,
) -> None:
    """
    Checkout a specific commit.

    This places the repository into detached HEAD state.

    WARNING:
        This changes the working tree.

    The caller should restore the original state afterwards.
    """

    if not commit_exists(
        repository_path,
        commit_hash,
    ):

        raise ValueError(
            f"Commit does not exist: {commit_hash}"
        )

    run_git(
        repository_path,
        "checkout",
        "--quiet",
        "--detach",
        commit_hash,
    )


# ============================================================
# RESTORE GIT STATE
# ============================================================


def restore_git_state(
    repository_path: str | Path,
    branch: Optional[str],
    commit_hash: Optional[str],
) -> None:
    """
    Restore the repository to its previous state.

    If a branch was originally checked out, restore that branch.

    Otherwise restore the original commit.
    """

    if branch:

        run_git(
            repository_path,
            "checkout",
            "--quiet",
            branch,
        )

        return

    if commit_hash:

        run_git(
            repository_path,
            "checkout",
            "--quiet",
            "--detach",
            commit_hash,
        )


# ============================================================
# CHECKOUT CONTEXT MANAGER
# ============================================================


class GitCommitCheckout:
    """
    Context manager for temporarily checking out a commit.

    Example
    -------

        with GitCommitCheckout(repo, commit_hash):

            # Analyze repository here

            snapshot = recover_architecture(...)

    After leaving the block, the original Git state
    is automatically restored.
    """

    def __init__(
        self,
        repository_path: str | Path,
        commit_hash: str,
    ):

        self.repository_path = Path(
            repository_path
        ).resolve()

        self.commit_hash = commit_hash

        self.original_branch = None
        self.original_commit = None

    def __enter__(self):

        # ----------------------------------------------
        # Validate repository
        # ----------------------------------------------

        if not is_git_repository(
            self.repository_path
        ):

            raise ValueError(
                f"Not a Git repository: "
                f"{self.repository_path}"
            )

        # ----------------------------------------------
        # Save current state
        # ----------------------------------------------

        self.original_branch = get_current_branch(
            self.repository_path
        )

        self.original_commit = get_current_commit(
            self.repository_path
        )

        # ----------------------------------------------
        # Checkout requested commit
        # ----------------------------------------------

        checkout_commit(
            self.repository_path,
            self.commit_hash,
        )

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):

        try:

            restore_git_state(
                self.repository_path,
                self.original_branch,
                self.original_commit,
            )

        except Exception as restore_error:

            print(
                "WARNING: Unable to restore Git state:"
            )

            print(
                restore_error
            )

        # Do not suppress original exceptions.
        return False


# ============================================================
# GET FILE CONTENT AT COMMIT
# ============================================================


def get_file_at_commit(
    repository_path: str | Path,
    commit_hash: str,
    file_path: str,
) -> str:
    """
    Read a file directly from a Git commit.

    This does NOT modify the working tree.
    """

    return run_git(
        repository_path,
        "show",
        f"{commit_hash}:{file_path}",
    )


# ============================================================
# GET PYTHON FILES AT COMMIT
# ============================================================


def get_python_files_at_commit(
    repository_path: str | Path,
    commit_hash: str,
) -> List[str]:
    """
    Return all Python files present at a specific commit.
    """

    output = run_git(
        repository_path,
        "ls-tree",
        "-r",
        "--name-only",
        commit_hash,
    )

    if not output:
        return []

    return [
        path
        for path in output.splitlines()
        if path.lower().endswith(".py")
    ]


# ============================================================
# HISTORY SUMMARY
# ============================================================


def get_history_summary(
    repository_path: str | Path,
) -> Dict[str, object]:
    """
    Return basic information about a Git repository's history.

    The returned dictionary is intentionally simple so that
    history_manager.py or the UI can consume it easily.
    """

    commits = get_commits(
        repository_path
    )

    current_commit = get_current_commit(
        repository_path
    )

    current_branch = get_current_branch(
        repository_path
    )

    return {
        "repository": str(
            Path(repository_path).resolve()
        ),
        "current_branch": current_branch,
        "current_commit": current_commit,
        "total_commits": len(commits),
        "commits": commits,
    }


# ============================================================
# TEST / DEMO
# ============================================================


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Inspect Git history for the "
            "Architecture Digital Twin."
        )
    )

    parser.add_argument(
        "repository",
        nargs="?",
        default=".",
        help="Path to Git repository",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of commits to display",
    )

    args = parser.parse_args()

    repository = Path(
        args.repository
    ).resolve()

    print("=" * 60)
    print("GIT HISTORY TEST")
    print("=" * 60)

    print(
        "\nRepository:",
        repository,
    )

    print(
        "Is Git repository:",
        is_git_repository(repository),
    )

    if not is_git_repository(repository):

        raise SystemExit(
            "The specified directory is not a Git repository."
        )

    print(
        "\nCurrent branch:",
        get_current_branch(repository),
    )

    print(
        "Current commit:",
        get_current_commit(repository),
    )

    commits = get_commits(
        repository,
        limit=args.limit,
    )

    print(
        f"\nRecent commits: {len(commits)}"
    )

    for index, commit in enumerate(
        commits,
        start=1,
    ):

        print(
            f"\n{index}. "
            f"{commit.short_hash} "
            f"- {commit.message}"
        )

        print(
            f"   Author: {commit.author}"
        )

        print(
            f"   Date:   {commit.timestamp}"
        )

    print("\n" + "=" * 60)
    print("GIT HISTORY MODULE TEST PASSED ✓")
    print("=" * 60)