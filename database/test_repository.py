from database.repository import (
    save_repository,
    save_snapshot,
    save_component,
    save_relationship,
)


repository_id = save_repository(
    name="My Test Repository",
    source="GitHub",
    url="https://github.com/example/project",
)

print("Repository ID:", repository_id)


snapshot_id = save_snapshot(
    repository_id=repository_id,
    commit_hash="test123",
    version=1,
)

print("Snapshot ID:", snapshot_id)


parser_id = save_component(
    snapshot_id=snapshot_id,
    name="Parser",
    component_type="module",
)

analyzer_id = save_component(
    snapshot_id=snapshot_id,
    name="Analyzer",
    component_type="module",
)

print("Components:", parser_id, analyzer_id)


relationship_id = save_relationship(
    snapshot_id=snapshot_id,
    source="Parser",
    target="Analyzer",
    relationship_type="depends_on",
)

print("Relationship ID:", relationship_id)

print("Database repository test completed!")