from pathlib import Path
import sys


def run_application_smoke(repository_path="."):
    """
    Execute representative application functionality for runtime tracing.

    This intentionally avoids launching Streamlit. It exercises project
    modules directly so RuntimeAnalyzer can observe application behavior
    inside the current Python process.
    """
    repository = Path(repository_path).resolve()

    if not repository.exists():
        raise FileNotFoundError(repository)

    # Exercise the existing parser as a representative project operation.
    from src.parser import parse_folder

    results = parse_folder(str(repository))

    return {
        "repository": str(repository),
        "files_parsed": len(results),
    }