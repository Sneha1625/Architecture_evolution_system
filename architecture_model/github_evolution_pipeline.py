
"""
github_evolution_pipeline.py

Generate architecture snapshots from real GitHub repository commits.

Uses:
- architecture_model.git_history
- src.parser
- architecture_model.history_manager
- database.db

This module performs static analysis only.
It does not execute code from the GitHub repository.
"""

from __future__ import annotations

import subprocess
import tempfile
import shutil
import tarfile

from pathlib import Path
from urllib.parse import urlparse

from architecture_model.git_history import (
    get_commits,
    commit_exists,
)

from architecture_model.history_manager import (
    save_architecture_history,
)

from database.db import get_connection
from src.parser import parse_folder


# ============================================================
# 1. NORMALIZE GITHUB URL
# ============================================================

def normalize_repository_url(repository_url: str) -> str:
    """Normalize a GitHub URL for consistent database lookup."""

    url = repository_url.strip()
    parsed = urlparse(url)

    if (
        parsed.scheme not in ("http", "https")
        or parsed.hostname is None
        or parsed.hostname.lower() != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
    ):
        raise ValueError("A valid public GitHub HTTPS URL is required.")

    parts = [
        part
        for part in parsed.path.strip("/").split("/")
        if part
    ]

    if len(parts) != 2:
        raise ValueError(
            "Expected a GitHub repository URL such as "
            "https://github.com/owner/repository"
        )

    owner, repository = parts
    repository = repository.removesuffix(".git")

    if not owner or not repository:
        raise ValueError("Invalid GitHub repository URL.")

    return f"https://github.com/{owner}/{repository}"


# ============================================================
# 2. FIND OR CREATE REPOSITORY
# ============================================================

def get_or_create_repository(
    name: str,
    repository_url: str,
) -> int:
    """Find an existing repository record or create a new one."""

    normalized_url = normalize_repository_url(repository_url)

    connection = get_connection()

    try:
        # Check exact URL first.
        row = connection.execute(
            """
            SELECT id
            FROM repositories
            WHERE url = ?
            ORDER BY id
            LIMIT 1
            """,
            (normalized_url,),
        ).fetchone()

        if row is not None:
            return int(row[0])

        # Also recognize previously saved URL variants.
        rows = connection.execute(
            """
            SELECT id, url
            FROM repositories
            WHERE url IS NOT NULL
            """
        ).fetchall()

        for row in rows:
            try:
                saved_url = normalize_repository_url(row[1])
            except (ValueError, TypeError):
                continue

            if saved_url.lower() == normalized_url.lower():
                return int(row[0])

        cursor = connection.execute(
            """
            INSERT INTO repositories
            (name, source, url)
            VALUES (?, ?, ?)
            """,
            (name, "GitHub", normalized_url),
        )

        connection.commit()

        return int(cursor.lastrowid)

    finally:
        connection.close()


# ============================================================
# 3. CHECK EXISTING SNAPSHOT
# ============================================================

def find_snapshot(
    repository_id: int,
    commit_hash: str,
) -> int | None:
    """Return an existing snapshot ID for this repository and commit."""

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT id
            FROM architecture_snapshots
            WHERE repository_id = ?
              AND commit_hash = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (repository_id, commit_hash),
        ).fetchone()

        return int(row[0]) if row is not None else None

    finally:
        connection.close()


# ============================================================
# 4. RESOLVE REAL GIT COMMIT
# ============================================================

def resolve_commit(
    repository_path: str | Path,
    commit_hash: str,
) -> str:
    """Resolve a commit reference to its full Git commit hash."""

    repo = Path(repository_path).resolve()

    if not repo.is_dir():
        raise FileNotFoundError(
            f"Repository directory does not exist: {repo}"
        )

    if not commit_exists(repo, commit_hash):
        raise ValueError(
            f"Commit does not exist in repository: {commit_hash}"
        )

    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "rev-parse",
            f"{commit_hash}^{{commit}}",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    return result.stdout.strip()


# ============================================================
# 5. EXTRACT COMMIT WITHOUT CHECKOUT
# ============================================================

def extract_commit(
    repository_path: str | Path,
    commit_hash: str,
    destination: str | Path,
) -> None:
    """
    Extract the source files at a Git commit.

    Does not change the repository's working tree.
    Rejects archive links and paths outside the destination.
    """

    repo = Path(repository_path).resolve()
    destination = Path(destination).resolve()

    destination.mkdir(parents=True, exist_ok=True)

    archive_path = destination.parent / "commit_archive.tar"

    with archive_path.open("wb") as archive_file:
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "archive",
                "--format=tar",
                commit_hash,
            ],
            stdout=archive_file,
            stderr=subprocess.PIPE,
            check=True,
            timeout=120,
        )

    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()

        # Keep the initial implementation bounded.
        max_files = 20000
        max_total_bytes = 250 * 1024 * 1024
        max_file_bytes = 10 * 1024 * 1024

        if len(members) > max_files:
            raise ValueError(
                "Repository commit contains too many archive entries."
            )

        total_bytes = 0

        for member in members:
            if member.issym() or member.islnk():
                continue

            if not (member.isdir() or member.isfile()):
                continue

            target = (destination / member.name).resolve()

            if not target.is_relative_to(destination):
                raise ValueError(
                    f"Unsafe archive path: {member.name}"
                )

            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            if member.size > max_file_bytes:
                raise ValueError(
                    f"Repository file is too large: {member.name}"
                )

            total_bytes += member.size

            if total_bytes > max_total_bytes:
                raise ValueError(
                    "Repository commit exceeds the extraction size limit."
                )

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            source = archive.extractfile(member)

            if source is not None:
                with source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)


# ============================================================
# 6. PARSE ONE COMMIT
# ============================================================

def parse_commit(
    repository_path: str | Path,
    commit_hash: str,
) -> list[dict]:
    """
    Parse all Python files from a specific Git commit.

    Returns repository-relative file paths so that
    architecture comparisons remain consistent.
    """

    resolved_commit = resolve_commit(
        repository_path,
        commit_hash,
    )

    with tempfile.TemporaryDirectory(
        prefix="github_architecture_"
    ) as temporary_directory:

        source_directory = (
            Path(temporary_directory) / "source"
        )

        extract_commit(
            repository_path,
            resolved_commit,
            source_directory,
        )

        parsed_results = parse_folder(
            str(source_directory)
        )

        for result in parsed_results:
            original_path = Path(result["file"])

            relative_path = original_path.relative_to(
                source_directory
            )

            result["file"] = relative_path.as_posix()

        return parsed_results


# ============================================================
# 7. ANALYZE AND SAVE ONE COMMIT
# ============================================================

def analyze_commit(
    repository_path: str,
    repository_url: str,
    commit_hash: str,
) -> dict:
    """
    Generate and save an architecture snapshot
    for one real Git commit.
    """

    repo = Path(repository_path).resolve()

    if not repo.is_dir():
        raise FileNotFoundError(
            f"Repository not found: {repo}"
        )

    normalized_url = normalize_repository_url(
        repository_url
    )

    resolved_commit = resolve_commit(
        repo,
        commit_hash,
    )

    repository_name = (
        normalized_url.rstrip("/").split("/")[-1]
    )

    repository_id = get_or_create_repository(
        name=repository_name,
        repository_url=normalized_url,
    )

    existing_snapshot = find_snapshot(
        repository_id,
        resolved_commit,
    )

    if existing_snapshot is not None:
        return {
            "repository_id": repository_id,
            "snapshot_id": existing_snapshot,
            "commit_hash": resolved_commit,
            "created": False,
        }

    parsed_results = parse_commit(
        repo,
        resolved_commit,
    )

    snapshot_id = save_architecture_history(
        repository_id=repository_id,
        parsed_results=parsed_results,
        commit_hash=resolved_commit,
    )

    return {
        "repository_id": repository_id,
        "snapshot_id": snapshot_id,
        "commit_hash": resolved_commit,
        "created": True,
    }


# ============================================================
# 8. ANALYZE RECENT GIT COMMITS
# ============================================================

def analyze_recent_commits(
    repository_path: str,
    repository_url: str,
    limit: int = 5,
) -> list[dict]:
    """
    Generate architecture snapshots for recent commits.

    Commits are analyzed from oldest to newest.
    """

    if not 1 <= limit <= 100:
        raise ValueError(
            "Commit limit must be between 1 and 100."
        )

    repo = Path(repository_path).resolve()

    commits = get_commits(
        repo,
        limit=limit,
    )

    results = []

    for commit in reversed(commits):
        result = analyze_commit(
            repository_path=str(repo),
            repository_url=repository_url,
            commit_hash=commit.hash,
        )

        results.append(result)

    return results
