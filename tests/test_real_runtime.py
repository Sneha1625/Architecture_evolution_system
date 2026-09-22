from architecture_model.runtime_analyzer import RuntimeAnalyzer


def run_real_architecture_flow():
    """
    Import and execute a small real project flow.

    Keep this lightweight so the test does not launch Streamlit.
    """

    from architecture_model.model import Component

    component = Component(
        id="runtime-test",
        name="Runtime Test Component",
        responsibility="Testing runtime analysis",
        layer="test",
    )

    return component


def test_real_project_runtime():

    analyzer = RuntimeAnalyzer(
        include_prefixes=[
            "architecture_model",
        ]
    )

    architecture = analyzer.run(
        run_real_architecture_flow,
        entry_point="real_project_runtime_test",
    )

    print("\nRuntime modules:")
    for module in sorted(architecture.modules):
        print("  ", module)

    print("\nRuntime relationships:")
    for relationship in architecture.get_relationships():
        print(
            f"  {relationship.source}"
            f" -> {relationship.target}"
            f" ({relationship.call_count} calls)"
        )

    print("\nTotal runtime calls:", architecture.total_calls)

    assert architecture.total_calls > 0