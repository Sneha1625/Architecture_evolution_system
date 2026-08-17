"""
Repository input and loading utilities.

This package is responsible only for obtaining a software
repository from the user and making it available locally.
"""

from .loader import (
    clone_github_repository,
    extract_uploaded_repository,
)

__all__ = [
    "clone_github_repository",
    "extract_uploaded_repository",
]