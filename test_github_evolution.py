
"""
Test GitHub Architecture Evolution using only a GitHub URL.

No local repository path is required.
"""

import subprocess
import tempfile
import traceback

from pathlib import Path

from architecture_model.github_evolution_pipeline import (
    analyze_recent_commits,
    normalize_repository_url,
)


# =====================================================
# ENTER ONLY THE GITHUB REPOSITORY URL
# =====================================================

repository_url = "https://github.com/aeff60/Sentiment-Analysis--Flask.git"

# Number of recent commits to analyze
commit_limit = 3


# =====================================================
# AUTOMATICALLY CLONE AND ANALYZE
# =====================================================

def test_github_evolution():

    url = normalize_repository_url(repository_url)

    print("\nGitHub Architecture Evolution Test")
    print("=" * 55)
    print("Repository URL:", url)
    print("Commits to analyze:", commit_limit)

    # Automatically deleted when the test finishes
    with tempfile.TemporaryDirectory(
        prefix="github_evolution_test_"
    ) as temporary_directory:

        local_repository = (
            Path(temporary_directory) / "repository"
        )

        print("\nCloning GitHub repository...")

        subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--no-checkout",
                url,
                str(local_repository),
            ],
            check=True,
            timeout=300,
        )

        print("Repository cloned successfully.")
        print("\nAnalyzing real Git commits...")

        results = analyze_recent_commits(
            repository_path=str(local_repository),
            repository_url=url,
            limit=commit_limit,
        )

        print("\nARCHITECTURE EVOLUTION RESULTS")
        print("=" * 55)

        for index, result in enumerate(results, start=1):

            print(f"\nCommit {index}")
            print("-" * 55)

            print(
                "Repository ID:",
                result["repository_id"],
            )

            print(
                "Snapshot ID:",
                result["snapshot_id"],
            )

            print(
                "Commit Hash:",
                result["commit_hash"],
            )

            print(
                "New Snapshot:",
                result["created"],
            )

        print("\nAnalysis completed successfully.")
        print("Snapshots have been saved to the database.")


# =====================================================
# RUN TEST
# =====================================================

if __name__ == "__main__":

    try:
        test_github_evolution()

    except Exception:
        print("\nArchitecture Evolution Test Failed:")
        traceback.print_exc()
