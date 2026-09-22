import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "data" / "architecture.db"

connection = sqlite3.connect(DATABASE_PATH)

print("=" * 60)
print("DATABASE SCHEMA CHECK")
print("=" * 60)

print("\nDatabase:")
print(DATABASE_PATH)

print("\nTABLES:")

tables = connection.execute(
    """
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name
    """
).fetchall()

for table in tables:
    print(" -", table[0])

for table_name in [
    "components",
    "relationships",
    "architecture_snapshots",
    "repositories",
    "component_files",
    "component_dependencies",
    "architecture_metrics",
]:

    print("\n" + "=" * 60)
    print(table_name)

    exists = connection.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table'
        AND name = ?
        """,
        (table_name,),
    ).fetchone()[0]

    if not exists:
        print("MISSING")
        continue

    columns = connection.execute(
        f"PRAGMA table_info([{table_name}])"
    ).fetchall()

    for column in columns:
        print(column)

connection.close()

print("\n" + "=" * 60)
print("SCHEMA CHECK COMPLETE")
print("=" * 60)