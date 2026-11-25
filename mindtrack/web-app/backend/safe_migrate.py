"""One-time safe database migration script.

Adds auth-related columns to the existing `users` table without destroying data.
Run once: python safe_migrate.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "mindtrack.db"


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def run_migration() -> None:
    print(f"Connecting to database at: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    migrations = [
        ("users", "password_hash", "TEXT"),
        ("users", "is_active", "INTEGER NOT NULL DEFAULT 1"),
        ("users", "is_admin", "INTEGER NOT NULL DEFAULT 0"),
    ]

    for table, col, col_def in migrations:
        if not column_exists(cursor, table, col):
            print(f"  Adding column `{table}.{col}` ...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            print(f"  ✓ Added `{col}`")
        else:
            print(f"  ✓ Column `{table}.{col}` already exists — skipping")

    conn.commit()
    conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    run_migration()
