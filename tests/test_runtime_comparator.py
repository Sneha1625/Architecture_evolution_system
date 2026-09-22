from architecture_model.model import Relationship
from architecture_model.runtime_model import RuntimeRelationship
from architecture_model.runtime_comparator import (
    compare_architectures,
    get_comparison_summary,
)


def test_static_runtime_comparison():

    static_relationships = [
        Relationship(
            source="Analyzer",
            target="Parser",
            type="import",
        ),
        Relationship(
            source="Analyzer",
            target="Database",
            type="import",
        ),
    ]

    runtime_relationships = [
        RuntimeRelationship(
            source="Analyzer",
            target="Parser",
            call_count=5,
        ),
        RuntimeRelationship(
            source="Parser",
            target="Logger",
            call_count=2,
        ),
    ]

    comparison = compare_architectures(
        static_relationships,
        runtime_relationships,
    )

    assert ("Analyzer", "Database") in comparison["static_only"]

    assert ("Parser", "Logger") in comparison["runtime_only"]

    assert ("Analyzer", "Parser") in comparison["both"]

    summary = get_comparison_summary(comparison)

    assert summary["static_only"] == 1
    assert summary["runtime_only"] == 1
    assert summary["both"] == 1