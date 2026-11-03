"""
Repository Loader
-----------------

Obtains a software repository from a public GitHub URL or uploaded ZIP.
The loader only returns a local directory and lists files; parsing and
architecture analysis are handled by the analysis pipeline.
"""

import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from git import Repo
from git.exc import GitCommandError


GITHUB_PATTERN = re.compile(
    r"^https?://github\.com/[^/]+/[^/]+/?(?:\.git)?$",
    re.IGNORECASE,
)

# Keep this list in sync with src/parser.py.
SUPPORTED_SOURCE_EXTENSIONS = {
    ".py",
    ".js", ".jsx", ".mjs", ".cjs",
    ".ts", ".tsx",
    ".java",
    ".c", ".h",
    ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx",
    ".cs",
    ".go",
    ".rs",
    ".php",
    ".rb",
}

IGNORED_DIRECTORIES = {
    ".git", ".venv", "venv", "env", "__pycache__", "node_modules",
    ".idea", ".vscode", "build", "dist", "target", "bin", "obj",
    ".next", ".nuxt", "coverage",
}


def _validate_github_url(url: str) -> str:
    """Validate and normalize a public GitHub repository URL."""
    if not isinstance(url, str):
        raise ValueError("Repository URL must be a string.")

    url = url.strip()
    if not url:
        raise ValueError("Repository URL cannot be empty.")

    if not GITHUB_PATTERN.match(url):
        raise ValueError(
            "Please enter a valid public GitHub repository URL.\n"
            "Example: https://github.com/user/project"
        )

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP/HTTPS GitHub URLs are supported.")
    if parsed.netloc.lower() != "github.com":
        raise ValueError("Only GitHub repositories are supported.")

    return url.rstrip("/")


def _create_repository_directory(prefix: str = "architecture_repo_") -> str:
    """Create and return an absolute temporary directory path."""
    return os.path.abspath(tempfile.mkdtemp(prefix=prefix))


def _find_project_root(extracted_path: str) -> str:
    """Find the project root inside an extracted ZIP archive."""
    root = Path(extracted_path)
    entries = [item for item in root.iterdir() if item.name != "__MACOSX"]

    if not entries:
        raise ValueError("The uploaded ZIP file is empty.")

    if len(entries) == 1 and entries[0].is_dir():
        return str(entries[0])

    return str(root)


def _validate_zip_member(member: zipfile.ZipInfo, destination: Path):
    """Prevent ZIP path traversal outside the extraction directory."""
    member_path = (destination / member.filename).resolve()
    destination_path = destination.resolve()

    try:
        member_path.relative_to(destination_path)
    except ValueError as exc:
        raise ValueError(
            "Unsafe ZIP archive detected. The archive contains an invalid file path."
        ) from exc


def clone_github_repository(github_url: str) -> str:
    """Clone a public GitHub repository and return its local path."""
    github_url = _validate_github_url(github_url)
    parent_directory = _create_repository_directory(
        prefix="architecture_github_"
    )

    repository_name = github_url.rstrip("/").split("/")[-1]
    if repository_name.endswith(".git"):
        repository_name = repository_name[:-4]

    clone_path = os.path.join(parent_directory, repository_name)

    try:
        Repo.clone_from(github_url, clone_path)
    except GitCommandError as exc:
        shutil.rmtree(parent_directory, ignore_errors=True)
        raise RuntimeError(
            "Unable to clone the GitHub repository.\n\n"
            "Please make sure:\n"
            "1. The URL is correct.\n"
            "2. The repository is public.\n"
            "3. The repository exists.\n\n"
            f"Git error: {exc}"
        ) from exc
    except Exception as exc:
        shutil.rmtree(parent_directory, ignore_errors=True)
        raise RuntimeError(f"Repository loading failed: {exc}") from exc

    return os.path.abspath(clone_path)


def extract_uploaded_repository(uploaded_file) -> str:
    """Safely extract an uploaded ZIP repository and return its project root."""
    if uploaded_file is None:
        raise ValueError("No repository ZIP file was provided.")

    filename = getattr(uploaded_file, "name", "")
    if not filename.lower().endswith(".zip"):
        raise ValueError("Please upload a .zip repository archive.")

    repository_directory = _create_repository_directory(
        prefix="architecture_uploaded_"
    )
    destination = Path(repository_directory)
    zip_path = destination / Path(filename).name

    try:
        with open(zip_path, "wb") as output_file:
            output_file.write(uploaded_file.getbuffer())

        with zipfile.ZipFile(zip_path, "r") as archive:
            members = archive.infolist()
            if not members:
                raise ValueError("The uploaded ZIP file is empty.")

            for member in members:
                _validate_zip_member(member, destination)

            archive.extractall(destination)

    except zipfile.BadZipFile as exc:
        shutil.rmtree(repository_directory, ignore_errors=True)
        raise ValueError(
            "The uploaded file is not a valid ZIP archive."
        ) from exc
    except Exception as exc:
        shutil.rmtree(repository_directory, ignore_errors=True)
        if isinstance(exc, ValueError):
            raise
        raise RuntimeError(f"Unable to extract repository: {exc}") from exc
    finally:
        try:
            if zip_path.exists():
                zip_path.unlink()
        except OSError:
            pass

    project_root = _find_project_root(repository_directory)
    return os.path.abspath(project_root)


def get_repository_name(repository_path: str) -> str:
    """Return the local repository directory name."""
    return Path(repository_path).name


def get_repository_files(repository_path: str) -> list[str]:
    """Return all repository files, excluding dependency and generated folders."""
    root = Path(repository_path)
    if not root.exists() or not root.is_dir():
        raise ValueError("Repository path does not exist or is not a directory.")

    files = []
    for current_root, dirs, filenames in os.walk(root):
        dirs[:] = sorted(
            directory
            for directory in dirs
            if directory not in IGNORED_DIRECTORIES
            and not directory.startswith(".")
        )

        for filename in filenames:
            full_path = Path(current_root) / filename
            try:
                relative_parts = full_path.relative_to(root).parts
            except ValueError:
                continue

            if any(part in IGNORED_DIRECTORIES for part in relative_parts[:-1]):
                continue

            files.append(str(full_path))

    return sorted(files)


def get_source_files(repository_path: str) -> list[str]:
    """
    Return supported source-code files for the multi-language parser.

    Configuration, documentation, images, binaries and other non-source files
    are intentionally excluded from code analysis.
    """
    return [
        path
        for path in get_repository_files(repository_path)
        if Path(path).suffix.lower() in SUPPORTED_SOURCE_EXTENSIONS
    ]


def get_python_files(repository_path: str) -> list[str]:
    """Backward-compatible helper: return Python source files only."""
    return [
        path
        for path in get_repository_files(repository_path)
        if Path(path).suffix.lower() == ".py"
    ]
