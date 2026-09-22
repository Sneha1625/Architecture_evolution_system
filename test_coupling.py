from pathlib import Path

from features.coupling_miner import mine_logical_coupling


def test_logical_coupling():
    # Use the current project/repository directory.
    # This makes the test portable across different computers.
    repo_path = Path(__file__).resolve().parent

    result = mine_logical_coupling(repo_path)

    assert result is not None
    assert "commits_analyzed" in result
    assert "files_analyzed" in result
    assert "couplings" in result

    print("Commits analyzed:", result["commits_analyzed"])
    print("Files analyzed:", result["files_analyzed"])

    print("\nTop logical couplings:")

    for coupling in result["couplings"][:10]:
        print(
            f"{coupling['file_a']} "
            f"<--> "
            f"{coupling['file_b']} | "
            f"Score: {coupling['coupling_score']}% | "
            f"Changed together: "
            f"{coupling['co_change_count']} times"
        )