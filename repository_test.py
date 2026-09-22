from database.repository import (
    get_repositories,
    get_snapshots,
    get_components,
    get_relationships,
)

print("=" * 60)
print("REPOSITORY READ TEST")
print("=" * 60)


# ============================================================
# REPOSITORIES
# ============================================================

repositories = get_repositories()

print()
print("Repositories:", len(repositories))

for repository in repositories:
    print(
        repository["id"],
        repository["name"],
        repository["source"],
        repository["url"],
    )


# ============================================================
# SNAPSHOTS
# ============================================================

print()
print("Snapshots")

for repository in repositories:

    repository_id = repository["id"]

    snapshots = get_snapshots(
        repository_id
    )

    print(
        f"Repository {repository_id}: "
        f"{len(snapshots)} snapshot(s)"
    )

    for snapshot in snapshots:

        print(
            " ",
            snapshot["id"],
            snapshot["commit_hash"],
            snapshot["version"],
            snapshot["timestamp"],
        )


# ============================================================
# COMPONENTS
# ============================================================

print()
print("Components")

snapshots = get_snapshots(
    repositories[-1]["id"]
) if repositories else []

for snapshot in snapshots:

    components = get_components(
        snapshot["id"]
    )

    print(
        f"Snapshot {snapshot['id']}: "
        f"{len(components)} component(s)"
    )

    for component in components:

        print(
            " ",
            component["id"],
            component["name"],
            component["component_type"],
        )


# ============================================================
# RELATIONSHIPS
# ============================================================

print()
print("Relationships")

for snapshot in snapshots:

    relationships = get_relationships(
        snapshot["id"]
    )

    print(
        f"Snapshot {snapshot['id']}: "
        f"{len(relationships)} relationship(s)"
    )

    for relationship in relationships:

        print(
            " ",
            relationship["source"],
            "->",
            relationship["target"],
            relationship["relationship_type"],
        )


print()
print("=" * 60)
print("REPOSITORY READ TEST COMPLETE")
print("=" * 60)