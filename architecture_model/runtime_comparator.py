from typing import Iterable, Tuple


def normalize_relationship(source: str, target: str) -> Tuple[str, str]:
    return source.strip(), target.strip()


def extract_static_relationships(
    relationships: Iterable,
    component_map: dict | None = None,
):
    result = set()

    for relationship in relationships:
        source = getattr(relationship, "source", "")
        target = getattr(relationship, "target", "")

        if not source or not target:
            continue

        if component_map:
            source = component_map.get(source, source)
            target = component_map.get(target, target)

        result.add(
            normalize_relationship(source, target)
        )

    return result


def extract_runtime_relationships(
    relationships: Iterable,
    component_map: dict | None = None,
):
    result = set()

    for relationship in relationships:
        source = getattr(relationship, "source", "")
        target = getattr(relationship, "target", "")

        if not source or not target:
            continue

        if component_map:
            source = component_map.get(source, source)
            target = component_map.get(target, target)

        result.add(
            normalize_relationship(source, target)
        )

    return result


def compare_architectures(
    static_relationships,
    runtime_relationships,
    static_component_map=None,
    runtime_component_map=None,
):
    static_set = extract_static_relationships(
        static_relationships,
        component_map=static_component_map,
    )

    runtime_set = extract_runtime_relationships(
        runtime_relationships,
        component_map=runtime_component_map,
    )

    return {
        "static_only": sorted(static_set - runtime_set),
        "runtime_only": sorted(runtime_set - static_set),
        "both": sorted(static_set & runtime_set),
    }


def get_comparison_summary(comparison):
    return {
        "static_only": len(comparison.get("static_only", [])),
        "runtime_only": len(comparison.get("runtime_only", [])),
        "both": len(comparison.get("both", [])),
    }