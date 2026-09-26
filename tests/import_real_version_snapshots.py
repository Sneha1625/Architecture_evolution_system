import json
from pathlib import Path

from database.repository import (
    save_repository,
    save_architecture_snapshot,
)

from architecture_model.model import (
    ArchitectureSnapshot,
    Component,
    Relationship,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARENT_DIR = PROJECT_ROOT.parent

V1_JSON = (
    PARENT_DIR
    / "runtime_v1"
    / "architecture_snapshots"
    / "37e49eb.json"
)

V2_JSON = (
    PARENT_DIR
    / "runtime_v2"
    / "architecture_snapshots"
    / "b9f6a01.json"
)


def load_snapshot(json_path, version, commit_hash):
    """
    Load architecture recovery JSON and convert it into the
    ArchitectureSnapshot model used by the database layer.
    """

    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    components = []

    for item in data.get("components", []):
        component = Component(
            id=item.get("id", item.get("name", "")),
            name=item.get("name", ""),
            responsibility=item.get("responsibility", ""),
            layer=item.get("layer", ""),
            files=item.get("files", []),
            dependencies=item.get("dependencies", []),
        )

        components.append(component)

    relationships = []

    for item in data.get("relationships", []):
        relationship = Relationship(
            source=item.get("source", ""),
            target=item.get("target", ""),
            type=item.get("type", "dependency"),
        )

        relationships.append(relationship)

    snapshot = ArchitectureSnapshot(
        version=str(version),
        commit_hash=commit_hash,
        components=components,
        relationships=relationships,
        metrics=data.get("metrics", {}),
        violations=data.get("violations", []),
    )

    return snapshot


def main():
    print("=" * 60)
    print("IMPORT REAL ARCHITECTURE VERSIONS")
    print("=" * 60)

    # --------------------------------------------------------
    # Validate snapshot files
    # --------------------------------------------------------

    if not V1_JSON.exists():
        raise FileNotFoundError(
            f"V1 snapshot not found: {V1_JSON}"
        )

    if not V2_JSON.exists():
        raise FileNotFoundError(
            f"V2 snapshot not found: {V2_JSON}"
        )

    print("\nV1 snapshot found:")
    print(V1_JSON)

    print("\nV2 snapshot found:")
    print(V2_JSON)

    # --------------------------------------------------------
    # Create ONE repository for both versions
    # save_repository accepts name, source, and url.
    # --------------------------------------------------------

    repository_id = save_repository(
        name="Architecture_evolution_system",
        source="local",
        url=(
            "https://github.com/"
            "Sneha1625/Architecture_evolution_system"
        ),
    )

    print(f"\nRepository ID: {repository_id}")

    # --------------------------------------------------------
    # Build V1 snapshot
    # --------------------------------------------------------

    v1_snapshot = load_snapshot(
        V1_JSON,
        version=1,
        commit_hash="37e49eb",
    )

    print("\nV1:")
    print(f"  Components: {len(v1_snapshot.components)}")
    print(
        f"  Relationships: "
        f"{len(v1_snapshot.relationships)}"
    )

    # --------------------------------------------------------
    # Save V1 snapshot
    # --------------------------------------------------------

    v1_snapshot_id = save_architecture_snapshot(
        repository_id,
        v1_snapshot,
    )

    print(f"  Snapshot ID: {v1_snapshot_id}")

    # --------------------------------------------------------
    # Build V2 snapshot
    # --------------------------------------------------------

    v2_snapshot = load_snapshot(
        V2_JSON,
        version=2,
        commit_hash="b9f6a01",
    )

    print("\nV2:")
    print(f"  Components: {len(v2_snapshot.components)}")
    print(
        f"  Relationships: "
        f"{len(v2_snapshot.relationships)}"
    )

    # --------------------------------------------------------
    # Save V2 snapshot
    # --------------------------------------------------------

    v2_snapshot_id = save_architecture_snapshot(
        repository_id,
        v2_snapshot,
    )

    print(f"  Snapshot ID: {v2_snapshot_id}")

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("REAL VERSION HISTORY CREATED")
    print("=" * 60)

    print(f"Repository ID: {repository_id}")
    print(
        f"V1: snapshot {v1_snapshot_id}"
        " | commit 37e49eb"
    )
    print(
        f"V2: snapshot {v2_snapshot_id}"
        " | commit b9f6a01"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()