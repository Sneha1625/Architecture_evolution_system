from pathlib import Path


def module_from_file(file_path: str) -> str:
    """
    Convert a Python file path into a normalized module name.
    """
    path = Path(file_path)

    if path.suffix == ".py":
        path = path.with_suffix("")

    return ".".join(path.parts)


def build_runtime_component_map(components):
    """
    Build:
        runtime module -> static component name

    from Component.files.
    """
    mapping = {}

    for component in components:
        for file_path in component.files:
            normalized = module_from_file(file_path)
            mapping[normalized] = component.name

    return mapping