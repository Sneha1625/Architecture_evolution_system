from architecture_model.runtime_analyzer import RuntimeAnalyzer
from tests.runtime_test_analyzer import analyze


def test_runtime_relationship():

    analyzer = RuntimeAnalyzer(
        include_prefixes=["tests"]
    )

    architecture = analyzer.run(
        analyze,
        entry_point="test_runtime_relationship"
    )

    relationships = architecture.get_relationships()

    pairs = {
        (relationship.source, relationship.target)
        for relationship in relationships
    }

    assert any(
        source.endswith("runtime_test_analyzer")
        and target.endswith("runtime_test_parser")
        for source, target in pairs
    )