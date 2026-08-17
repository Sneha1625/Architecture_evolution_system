"""
Repository Loader
-----------------

Responsible for obtaining a software repository from:

1. A public GitHub URL
2. An uploaded ZIP archive

The loader does NOT analyze the repository.

It only returns a local directory containing the source code.

Pipeline:

    User Input
        ↓
    Repository Loader
        ↓
    Local Repository
        ↓
    Architecture Analysis Engine
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


# ============================================================
# CONSTANTS
# ============================================================

GITHUB_PATTERN = re.compile(
    r"^https?://github\.com/[^/]+/[^/]+/?(?:\.git)?$",
    re.IGNORECASE,
)


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _validate_github_url(url: str) -> str:
    """
    Validate and normalize a GitHub repository URL.

    Example accepted URLs:

        https://github.com/user/project
        https://github.com/user/project.git
        https://github.com/user/project/

    Returns:
        Normalized URL.

    Raises:
        ValueError: if the URL is invalid.
    """

    if not isinstance(url, str):
        raise ValueError(
            "Repository URL must be a string."
        )

    url = url.strip()

    if not url:
        raise ValueError(
            "Repository URL cannot be empty."
        )

    if not GITHUB_PATTERN.match(url):
        raise ValueError(
            "Please enter a valid public GitHub repository URL.\n"
            "Example: https://github.com/user/project"
        )

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            "Only HTTP/HTTPS GitHub URLs are supported."
        )

    if parsed.netloc.lower() != "github.com":
        raise ValueError(
            "Only GitHub repositories are supported."
        )

    return url.rstrip("/")


def _create_repository_directory(
    prefix: str = "architecture_repo_",
) -> str:
    """
    Create a temporary directory for a repository.

    Returns:
        Absolute path of the created directory.
    """

    path = tempfile.mkdtemp(
        prefix=prefix
    )

    return os.path.abspath(path)


def _find_project_root(
    extracted_path: str,
) -> str:
    """
    Find the actual project root after extracting a ZIP.

    Handles ZIP files such as:

        project/
            src/
            app.py

    and also ZIP files containing files directly:

        src/
        app.py

    Returns:
        Path containing the project files.
    """

    root = Path(extracted_path)

    entries = [
        item
        for item in root.iterdir()
        if item.name != "__MACOSX"
    ]

    # No files/folders
    if not entries:
        raise ValueError(
            "The uploaded ZIP file is empty."
        )

    # If the ZIP contains exactly one directory,
    # use that directory as the project root.
    if (
        len(entries) == 1
        and entries[0].is_dir()
    ):
        return str(entries[0])

    return str(root)


def _validate_zip_member(
    member: zipfile.ZipInfo,
    destination: Path,
):
    """
    Protect ZIP extraction from path traversal attacks.

    A malicious ZIP could contain:

        ../../some_file

    This function ensures extraction stays inside
    the intended repository directory.
    """

    member_path = (
        destination / member.filename
    ).resolve()

    destination_path = (
        destination
    ).resolve()

    try:
        member_path.relative_to(
            destination_path
        )

    except ValueError:

        raise ValueError(
            "Unsafe ZIP archive detected. "
            "The archive contains an invalid file path."
        )


# ============================================================
# GITHUB REPOSITORY
# ============================================================

def clone_github_repository(
    github_url: str,
) -> str:
    """
    Clone a public GitHub repository.

    Args:
        github_url:
            Public GitHub repository URL.

    Returns:
        Absolute local path of the cloned repository.

    Example:

        repo_path = clone_github_repository(
            "https://github.com/user/project"
        )

    The returned path can then be passed to:

        parser
        dependency analyzer
        architecture recovery
        Time Machine
        etc.
    """

    github_url = _validate_github_url(
        github_url
    )

    parent_directory = _create_repository_directory(
        prefix="architecture_github_"
    )

    repository_name = (
        github_url
        .rstrip("/")
        .split("/")
        [-1]
    )

    if repository_name.endswith(
        ".git"
    ):
        repository_name = (
            repository_name[:-4]
        )

    clone_path = os.path.join(
        parent_directory,
        repository_name,
    )

    try:

        Repo.clone_from(
            github_url,
            clone_path,
        )

    except GitCommandError as e:

        # Remove partially cloned repository
        if os.path.exists(
            parent_directory
        ):
            shutil.rmtree(
                parent_directory,
                ignore_errors=True,
            )

        raise RuntimeError(
            "Unable to clone the GitHub repository.\n\n"
            "Please make sure:\n"
            "1. The URL is correct.\n"
            "2. The repository is public.\n"
            "3. The repository exists.\n\n"
            f"Git error: {e}"
        ) from e

    except Exception as e:

        if os.path.exists(
            parent_directory
        ):
            shutil.rmtree(
                parent_directory,
                ignore_errors=True,
            )

        raise RuntimeError(
            f"Repository loading failed: {e}"
        ) from e

    return os.path.abspath(
        clone_path
    )


# ============================================================
# ZIP REPOSITORY
# ============================================================

def extract_uploaded_repository(
    uploaded_file,
) -> str:
    """
    Extract an uploaded ZIP repository.

    Args:
        uploaded_file:
            Streamlit UploadedFile object.

    Returns:
        Absolute path of the extracted repository.

    Example:

        repo_path = extract_uploaded_repository(
            uploaded_zip
        )
    """

    if uploaded_file is None:
        raise ValueError(
            "No repository ZIP file was provided."
        )

    filename = getattr(
        uploaded_file,
        "name",
        "",
    )

    if not filename.lower().endswith(
        ".zip"
    ):
        raise ValueError(
            "Please upload a .zip repository archive."
        )

    repository_directory = _create_repository_directory(
        prefix="architecture_uploaded_"
    )

    destination = Path(
        repository_directory
    )

    zip_path = destination / filename

    try:

        # Save uploaded file temporarily
        with open(
            zip_path,
            "wb",
        ) as f:

            f.write(
                uploaded_file.getbuffer()
            )

        # Validate and extract ZIP
        with zipfile.ZipFile(
            zip_path,
            "r",
        ) as archive:

            members = archive.infolist()

            if not members:
                raise ValueError(
                    "The uploaded ZIP file is empty."
                )

            # Security validation
            for member in members:

                _validate_zip_member(
                    member,
                    destination,
                )

            archive.extractall(
                destination
            )

    except zipfile.BadZipFile as e:

        shutil.rmtree(
            repository_directory,
            ignore_errors=True,
        )

        raise ValueError(
            "The uploaded file is not a valid ZIP archive."
        ) from e

    except Exception as e:

        shutil.rmtree(
            repository_directory,
            ignore_errors=True,
        )

        raise RuntimeError(
            f"Unable to extract repository: {e}"
        ) from e

    finally:

        # Remove temporary ZIP file after extraction
        if zip_path.exists():

            try:
                zip_path.unlink()

            except Exception:
                pass

    project_root = _find_project_root(
        repository_directory
    )

    return os.path.abspath(
        project_root
    )


# ============================================================
# REPOSITORY INFORMATION
# ============================================================

def get_repository_name(
    repository_path: str,
) -> str:
    """
    Return the name of a loaded repository.
    """

    path = Path(
        repository_path
    )

    return path.name


def get_repository_files(
    repository_path: str,
) -> list[str]:
    """
    Return all files inside a repository.

    Hidden Git metadata and virtual environments are skipped.

    This function does NOT analyze the files.
    """

    root = Path(
        repository_path
    )

    if not root.exists():
        raise ValueError(
            "Repository path does not exist."
        )

    ignored_directories = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".idea",
        ".vscode",
    }

    files = []

    for path in root.rglob("*"):

        if not path.is_file():
            continue

        if any(
            part in ignored_directories
            for part in path.parts
        ):
            continue

        files.append(
            str(path)
        )

    return files


def get_python_files(
    repository_path: str,
) -> list[str]:
    """
    Return Python source files from the repository.
    """

    files = get_repository_files(
        repository_path
    )

    return [
        path
        for path in files
        if path.lower().endswith(
            ".py"
        )
    ]