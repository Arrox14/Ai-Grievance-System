import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.core import config


CURRENT_SCHEMA_VERSION = 3


def _connect(database_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, timeout=10)
    connection.execute("PRAGMA foreign_keys = ON")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        connection.close()
        raise RuntimeError("SQLite foreign-key enforcement could not be enabled")
    return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    escaped_name = table_name.replace('"', '""')
    return {
        row[1]
        for row in connection.execute(f'PRAGMA table_info("{escaped_name}")')
    }


def _add_column_if_missing(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    declaration: str,
) -> None:
    if column_name not in _columns(connection, table_name):
        connection.execute(
            f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {declaration}'
        )


def _create_legacy_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'citizen',
            created_at TEXT NOT NULL,
            token_version INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    _add_column_if_missing(
        connection,
        "users",
        "token_version",
        "INTEGER NOT NULL DEFAULT 0",
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            file TEXT,
            lat REAL,
            lon REAL,
            status TEXT DEFAULT 'Pending',
            timestamp TEXT NOT NULL,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            resolution_date TEXT,
            resolution_remarks TEXT,
            officer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            assigned_at TEXT
        )
        """
    )
    complaint_columns = (
        ("user_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
        ("resolution_date", "TEXT"),
        ("resolution_remarks", "TEXT"),
        ("officer_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
        ("assigned_at", "TEXT"),
    )
    for column_name, declaration in complaint_columns:
        _add_column_if_missing(
            connection,
            "complaints",
            column_name,
            declaration,
        )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS uploaded_files (
            file_path TEXT PRIMARY KEY,
            owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS complaint_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL
                REFERENCES complaints(id) ON DELETE CASCADE,
            previous_status TEXT,
            status TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            actor_name TEXT NOT NULL,
            actor_email TEXT NOT NULL,
            remarks TEXT
        )
        """
    )
    _add_column_if_missing(
        connection,
        "complaint_status_history",
        "previous_status",
        "TEXT",
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS complaint_investigation_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL
                REFERENCES complaints(id) ON DELETE CASCADE,
            officer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            author_name TEXT NOT NULL,
            note_type TEXT NOT NULL
                CHECK (note_type IN ('internal', 'citizen_visible')),
            note TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS complaint_resolution_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL
                REFERENCES complaints(id) ON DELETE CASCADE,
            officer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            officer_name TEXT NOT NULL,
            findings TEXT NOT NULL,
            remarks TEXT NOT NULL,
            resolution_date TEXT NOT NULL,
            file_path TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            content_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            submitted_at TEXT NOT NULL,
            review_status TEXT NOT NULL DEFAULT 'pending_review'
                CHECK (review_status IN ('pending_review', 'approved', 'rejected')),
            reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            reviewed_at TEXT,
            review_remarks TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            complaint_id INTEGER NOT NULL
                REFERENCES complaints(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1))
        )
        """
    )

    required_complaint_columns = {
        "id",
        "text",
        "category",
        "priority",
        "file",
        "lat",
        "lon",
        "status",
        "timestamp",
        "user_id",
        "resolution_date",
        "resolution_remarks",
        "officer_id",
        "assigned_at",
    }
    missing_complaint_columns = required_complaint_columns - _columns(
        connection, "complaints"
    )
    if missing_complaint_columns:
        raise RuntimeError(
            "Unsupported complaints table; missing columns: "
            + ", ".join(sorted(missing_complaint_columns))
        )
    required_user_columns = {
        "id",
        "name",
        "email",
        "password_hash",
        "role",
        "created_at",
        "token_version",
    }
    missing_user_columns = required_user_columns - _columns(connection, "users")
    if missing_user_columns:
        raise RuntimeError(
            "Unsupported users table; missing columns: "
            + ", ".join(sorted(missing_user_columns))
        )


def _migrate_to_v1(connection: sqlite3.Connection) -> None:
    _create_legacy_tables(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            description TEXT,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS officer_profiles (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS complaint_assignment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL
                REFERENCES complaints(id) ON DELETE CASCADE,
            previous_officer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            new_officer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
            assigned_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            assigned_at TEXT NOT NULL,
            reason TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL
                REFERENCES complaints(id) ON DELETE CASCADE,
            analysis_type TEXT NOT NULL,
            model_name TEXT NOT NULL,
            model_version TEXT,
            result_json TEXT NOT NULL,
            confidence REAL CHECK (
                confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
            ),
            created_at TEXT NOT NULL
        )
        """
    )

    indexes = (
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique "
        "ON users(email COLLATE NOCASE)",
        "CREATE INDEX IF NOT EXISTS idx_complaints_user_timestamp "
        "ON complaints(user_id, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_complaints_officer_assignment "
        "ON complaints(officer_id, assigned_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_uploaded_files_owner "
        "ON uploaded_files(owner_id)",
        "CREATE INDEX IF NOT EXISTS idx_complaint_status_history_complaint "
        "ON complaint_status_history(complaint_id, changed_at, id)",
        "CREATE INDEX IF NOT EXISTS idx_investigation_notes_complaint "
        "ON complaint_investigation_notes(complaint_id, created_at, id)",
        "CREATE INDEX IF NOT EXISTS idx_resolution_submissions_complaint "
        "ON complaint_resolution_submissions(complaint_id, submitted_at DESC, id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_notifications_user_created "
        "ON notifications(user_id, created_at DESC, id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_officer_profiles_department "
        "ON officer_profiles(department_id)",
        "CREATE INDEX IF NOT EXISTS idx_assignment_history_complaint "
        "ON complaint_assignment_history(complaint_id, assigned_at, id)",
        "CREATE INDEX IF NOT EXISTS idx_assignment_history_officer "
        "ON complaint_assignment_history(new_officer_id, assigned_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_ai_analysis_complaint_created "
        "ON ai_analysis_results(complaint_id, created_at DESC, id DESC)",
    )
    for index_sql in indexes:
        connection.execute(index_sql)

    # A role already recorded as officer is sufficient to create an empty profile;
    # no department, assignment, or historical event is inferred.
    connection.execute(
        """
        INSERT INTO officer_profiles (user_id, department_id, created_at)
        SELECT id, NULL, created_at
        FROM users
        WHERE role = 'officer'
          AND NOT EXISTS (
              SELECT 1 FROM officer_profiles WHERE user_id = users.id
          )
        """
    )


def _migrate_to_v2(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE notifications_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            complaint_id INTEGER REFERENCES complaints(id) ON DELETE CASCADE,
            notification_type TEXT NOT NULL DEFAULT 'general'
                CHECK (length(trim(notification_type)) > 0),
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1))
        )
        """
    )
    notification_type_expression = (
        "notification_type"
        if "notification_type" in _columns(connection, "notifications")
        else "'general'"
    )
    connection.execute(
        """
        INSERT INTO notifications_v2
            (id, user_id, complaint_id, notification_type, title, message,
             created_at, is_read)
        SELECT id, user_id, complaint_id, {notification_type_expression}, title, message, created_at,
               is_read
        FROM notifications
        """.format(notification_type_expression=notification_type_expression)
    )
    connection.execute("DROP TABLE notifications")
    connection.execute("ALTER TABLE notifications_v2 RENAME TO notifications")
    _add_column_if_missing(
        connection,
        "ai_analysis_results",
        "error_message",
        "TEXT",
    )
    connection.execute(
        "CREATE INDEX idx_notifications_user_created "
        "ON notifications(user_id, created_at DESC, id DESC)"
    )
    connection.execute(
        "CREATE INDEX idx_notifications_unread "
        "ON notifications(user_id, created_at DESC, id DESC) WHERE is_read = 0"
    )
    connection.execute(
        "CREATE INDEX idx_notifications_complaint "
        "ON notifications(complaint_id, created_at DESC, id DESC)"
    )


def _migrate_to_v3(connection: sqlite3.Connection) -> None:
    _add_column_if_missing(
        connection,
        "users",
        "is_active",
        "INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))",
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_role_active "
        "ON users(role, is_active, name COLLATE NOCASE)"
    )


def _table_snapshot(connection: sqlite3.Connection) -> dict:
    table_names = [
        row[0]
        for row in connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
              AND name != 'schema_migrations'
            ORDER BY name
            """
        )
    ]
    snapshot = {}
    for table_name in table_names:
        quoted_name = table_name.replace('"', '""')
        columns = [
            row[1]
            for row in connection.execute(
                f'PRAGMA table_info("{quoted_name}")'
            )
        ]
        rows = connection.execute(
            f'SELECT * FROM "{quoted_name}" ORDER BY rowid'
        ).fetchall()
        snapshot[table_name] = (columns, rows)
    return snapshot


def migrate_database(database_path: str | os.PathLike) -> int:
    database_path = os.fspath(database_path)
    connection = _connect(database_path)
    try:
        if connection.in_transaction:
            raise RuntimeError("Unexpected SQLite transaction before migration")
        pre_migration_fk_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        if pre_migration_fk_errors:
            raise RuntimeError(
                "Database has foreign-key violations before migration; "
                "no changes were applied"
            )
        original_snapshot = _table_snapshot(connection)

        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL
            )
            """
        )
        current_version_row = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()
        current_version = current_version_row[0] or 0
        if current_version > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {current_version} is newer than "
                f"this application supports ({CURRENT_SCHEMA_VERSION})"
            )
        if current_version < 1:
            _migrate_to_v1(connection)
            connection.execute(
                """
                INSERT INTO schema_migrations (version, name, applied_at)
                VALUES (?, ?, ?)
                """,
                (
                    1,
                    "add_departments_assignments_and_ai_results",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            current_version = 1
        if current_version < 2:
            _migrate_to_v2(connection)
            connection.execute(
                """
                INSERT INTO schema_migrations (version, name, applied_at)
                VALUES (?, ?, ?)
                """,
                (
                    2,
                    "add_notification_types_and_analysis_errors",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            current_version = 2
        if current_version < 3:
            _migrate_to_v3(connection)
            connection.execute(
                """
                INSERT INTO schema_migrations (version, name, applied_at)
                VALUES (?, ?, ?)
                """,
                (
                    3,
                    "add_user_active_state",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        if foreign_key_errors:
            raise RuntimeError(
                f"Migration produced foreign-key violations: {foreign_key_errors!r}"
            )
        updated_snapshot = _table_snapshot(connection)
        for table_name, (old_columns, old_rows) in original_snapshot.items():
            if table_name not in updated_snapshot:
                raise RuntimeError(f"Migration unexpectedly removed {table_name}")
            new_columns, new_rows = updated_snapshot[table_name]
            if not set(old_columns).issubset(new_columns):
                raise RuntimeError(
                    f"Migration unexpectedly removed columns from {table_name}"
                )
            column_positions = [
                list(new_columns).index(column) for column in old_columns
            ]
            projected_rows = [
                tuple(row[position] for position in column_positions)
                for row in new_rows
            ]
            if old_rows != projected_rows:
                raise RuntimeError(
                    f"Migration changed existing records in {table_name}"
                )
        connection.commit()
        return CURRENT_SCHEMA_VERSION
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def require_current_schema(database_path: str | os.PathLike | None = None) -> None:
    database_path = os.fspath(
        database_path or os.path.join(config.BASE_DIR, "complaints.db")
    )
    connection = _connect(database_path)
    try:
        if not _table_exists(connection, "schema_migrations"):
            raise RuntimeError(
                "Database migrations have not been applied. From Backend, run "
                "the documented versioned migration command before starting the API."
            )
        row = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()
        version = row[0] or 0
        if version != CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {version} is not current "
                f"(expected {CURRENT_SCHEMA_VERSION}); apply migrations before startup."
            )
    finally:
        connection.close()


def create_backup(
    database_path: str | os.PathLike,
    backup_path: str | os.PathLike,
) -> Path:
    database_path = Path(database_path).resolve()
    backup_path = Path(backup_path).resolve()
    if not database_path.is_file():
        raise FileNotFoundError(f"Database file not found: {database_path}")
    if database_path == backup_path:
        raise ValueError("Backup path must be different from the database path")
    if backup_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing backup: {backup_path}"
        )

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{backup_path.name}.",
        suffix=".tmp",
        dir=backup_path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        source = _connect(str(database_path))
        destination = _connect(str(temporary_path))
        try:
            source.backup(destination)
            integrity = destination.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(
                    f"SQLite backup integrity check failed: {integrity}"
                )
            destination.commit()
        finally:
            destination.close()
            source.close()
        if backup_path.exists():
            raise FileExistsError(
                f"Refusing to overwrite existing backup: {backup_path}"
            )
        os.replace(temporary_path, backup_path)
        return backup_path
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def backup_and_migrate(
    database_path: str | os.PathLike,
    backup_path: str | os.PathLike,
) -> tuple[Path, int]:
    backup = create_backup(database_path, backup_path)
    version = migrate_database(database_path)
    return backup, version
