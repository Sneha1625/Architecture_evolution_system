import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH = DATA_DIR / "architecture.db"


def get_connection():
    """Return a connection to the architecture SQLite database."""

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection
if __name__ == "__main__":
    connection = get_connection()

    print("SQLite connected successfully!")
    print("Database:", DATABASE_PATH)

    connection.close()