import argparse
from pathlib import Path

from app.migrations.runner import backup_and_migrate


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Back up and apply versioned SQLite schema migrations."
    )
    parser.add_argument(
        "--database",
        default="complaints.db",
        help="Existing SQLite database path (default: complaints.db)",
    )
    parser.add_argument(
        "--backup",
        required=True,
        help="New backup path; an existing file will never be overwritten",
    )
    arguments = parser.parse_args()
    database_path = Path(arguments.database).resolve()
    backup_path = Path(arguments.backup).resolve()
    backup, version = backup_and_migrate(database_path, backup_path)
    print(f"Verified backup: {backup}")
    print(f"Applied schema version: {version}")


if __name__ == "__main__":
    main()
