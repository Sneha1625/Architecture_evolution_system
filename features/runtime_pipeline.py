from pathlib import Path
import sys

from src.parser import parse_folder


def run_repository_parser(repository_path: str):
    """
    Execute the real repository parser.

    This is intentionally kept separate from app.py so the
    RuntimeAnalyzer can observe the actual parser execution.
    """
    path = Path(repository_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Repository path does not exist: {path}")

    if not path.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {path}")

    return parse_folder(str(path))
from pathlib import Path


def normalize_file_path(file_path: str) -> str:
    """Normalize a repository-relative Python file path."""
    path = str(file_path).replace("\\", "/").lstrip("./")
    return path.lower()


def module_to_file(module_name: str) -> str:
    """Convert a Python module name into a normalized .py path."""
    return module_name.replace(".", "/").lower() + ".py"


def build_runtime_component_map(components):
    """
    Map runtime Python module names to static architecture components.

    Example:
        src.parser -> Parser
        architecture_model.runtime_analyzer -> Architecture Model
    """
    mapping = {}

    for component in components:
        for file_path in component.files:
            normalized_file = normalize_file_path(file_path)

            if normalized_file.endswith(".py"):
                module_name = normalized_file[:-3]

                # __init__.py represents the package itself.
                if module_name.endswith("/__init__"):
                    module_name = module_name[:-9]

                module_name = module_name.replace("/", ".")

                mapping[module_name] = component.name

    return mapping


def map_runtime_module(module_name: str, component_map: dict):
    """Return the static component corresponding to a runtime module."""
    normalized = module_name.replace("\\", "/").lower()

    return component_map.get(normalized)