import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import config
from app.database import connect_db
from app.migrations.runner import (
    CURRENT_SCHEMA_VERSION,
    create_backup,
    migrate_database,
)


class VersionedMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database_path = self.root / "complaints.db"
        self.base_dir_patch = patch.object(config, "BASE_DIR", self.temp_dir.name)
        self.base_dir_patch.start()
        self._create_legacy_database()

    def tearDown(self):
        self.base_dir_patch.stop()
        self.temp_dir.cleanup()

    def _create_legacy_database(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'citizen',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE complaints (
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
                );
                CREATE TABLE complaint_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    complaint_id INTEGER NOT NULL
                        REFERENCES complaints(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    actor_name TEXT NOT NULL,
                    actor_email TEXT NOT NULL,
                    remarks TEXT
                );
                CREATE TABLE notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    complaint_id INTEGER NOT NULL
                        REFERENCES complaints(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1))
                );
                INSERT INTO users
                    (id, name, email, password_hash, role, created_at)
                VALUES
                    (7, 'Citizen', 'citizen@example.com', 'bcrypt-hash', 'citizen',
                     '2026-01-01T10:00:00'),
                    (9, 'Officer', 'officer@example.com', 'bcrypt-hash', 'officer',
                     '2026-01-02T10:00:00');
                INSERT INTO complaints
                    (id, text, category, priority, file, lat, lon, status, timestamp,
                     user_id, resolution_date, resolution_remarks, officer_id, assigned_at)
                VALUES
                    (42, 'Existing complaint', 'Roads', 'High',
                     'C:\\legacy\\evidence.jpg', 51.5, -0.12, 'In Progress',
                     '2026-02-03T04:05:06', 7, NULL, NULL, 9,
                     '2026-02-04T04:05:06');
                INSERT INTO complaint_status_history
                    (id, complaint_id, status, changed_at, actor_id, actor_name,
                     actor_email, remarks)
                VALUES
                    (17, 42, 'In Progress', '2026-02-04T04:05:06', 9, 'Officer',
                     'officer@example.com', 'Existing history');
                INSERT INTO notifications
                    (id, user_id, complaint_id, title, message, created_at, is_read)
                VALUES
                    (23, 7, 42, 'Status update', 'Existing notification',
                     '2026-02-04T04:05:06', 0);
                """
            )
            connection.commit()

    def _rows(self, table, order_by, columns="*"):
        with closing(sqlite3.connect(self.database_path)) as connection:
            return connection.execute(
                f"SELECT {columns} FROM {table} ORDER BY {order_by}"
            ).fetchall()

    def test_migration_preserves_records_relationships_and_attachment_references(self):
        original_complaints = self._rows("complaints", "id")
        original_users = self._rows(
            "users", "id", "id, name, email, password_hash, role, created_at"
        )
        original_history = self._rows(
            "complaint_status_history",
            "id",
            "id, complaint_id, status, changed_at, actor_id, actor_name, "
            "actor_email, remarks",
        )
        notification_columns = (
            "id, user_id, complaint_id, title, message, created_at, is_read"
        )
        original_notifications = self._rows(
            "notifications", "id", notification_columns
        )

        self.assertEqual(migrate_database(self.database_path), CURRENT_SCHEMA_VERSION)
        self.assertEqual(self._rows("complaints", "id"), original_complaints)
        self.assertEqual(
            self._rows(
                "users", "id", "id, name, email, password_hash, role, created_at"
            ),
            original_users,
        )
        self.assertEqual(
            self._rows(
                "complaint_status_history",
                "id",
                "id, complaint_id, status, changed_at, actor_id, actor_name, "
                "actor_email, remarks",
            ),
            original_history,
        )
        self.assertEqual(
            self._rows("notifications", "id", notification_columns),
            original_notifications,
        )

        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT id FROM complaints").fetchall(), [(42,)]
            )
            self.assertEqual(
                connection.execute(
                    "SELECT user_id, officer_id FROM complaints WHERE id = 42"
                ).fetchone(),
                (7, 9),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT file, timestamp FROM complaints WHERE id = 42"
                ).fetchone(),
                ("C:\\legacy\\evidence.jpg", "2026-02-03T04:05:06"),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT user_id FROM officer_profiles ORDER BY user_id"
                ).fetchall(),
                [(9,)],
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM complaint_assignment_history"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM ai_analysis_results"
                ).fetchone()[0],
                0,
            )
            legacy_notification = connection.execute(
                """
                SELECT notification_type, complaint_id
                FROM notifications WHERE id = 23
                """
            ).fetchone()
            self.assertEqual(legacy_notification, ("general", 42))
            self.assertIn(
                "error_message",
                {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(ai_analysis_results)"
                    )
                },
            )
            self.assertEqual(
                connection.execute("PRAGMA foreign_key_check").fetchall(), []
            )
            self.assertEqual(
                connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
            )
            self.assertEqual(
                connection.execute(
                    "SELECT MAX(version) FROM schema_migrations"
                ).fetchone(),
                (CURRENT_SCHEMA_VERSION,),
            )

    def test_migration_is_safe_to_rerun_and_enforces_new_constraints(self):
        migrate_database(self.database_path)
        migrate_database(self.database_path)

        with closing(connect_db()) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(
                connection.execute(
                    "SELECT is_active FROM users WHERE role = 'officer'"
                ).fetchall(),
                [(1,)],
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO departments (name, created_at) VALUES (?, ?)",
                    ("Roads", "2026-03-01T00:00:00"),
                )
                connection.execute(
                    "INSERT INTO departments (name, created_at) VALUES (?, ?)",
                    ("roads", "2026-03-02T00:00:00"),
                )
            connection.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO complaint_assignment_history
                        (complaint_id, assigned_at)
                    VALUES (9999, '2026-03-01T00:00:00')
                    """
                )
            connection.rollback()

    def test_active_officer_migration_preserves_existing_custom_notification_types(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "ALTER TABLE notifications ADD COLUMN notification_type "
                "TEXT NOT NULL DEFAULT 'general'"
            )
            connection.execute(
                "UPDATE notifications SET notification_type = 'complaint_status_updated' "
                "WHERE id = 23"
            )
            connection.commit()
        original_notifications = self._rows(
            "notifications",
            "id",
            "id, user_id, complaint_id, notification_type, title, message, "
            "created_at, is_read",
        )

        self.assertEqual(migrate_database(self.database_path), CURRENT_SCHEMA_VERSION)
        migrate_database(self.database_path)

        self.assertEqual(
            self._rows(
                "notifications",
                "id",
                "id, user_id, complaint_id, notification_type, title, message, "
                "created_at, is_read",
            ),
            original_notifications,
        )
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT is_active FROM users WHERE id = 9"
                ).fetchone(),
                (1,),
            )
            connection.execute("UPDATE users SET is_active = 0 WHERE id = 9")
            connection.commit()
            self.assertEqual(
                connection.execute(
                    "SELECT is_active FROM users WHERE id = 9"
                ).fetchone(),
                (0,),
            )

    def test_notifications_can_be_general_and_ai_runs_keep_optional_confidence(self):
        migrate_database(self.database_path)
        with closing(connect_db()) as connection:
            connection.execute(
                """
                INSERT INTO notifications
                    (user_id, complaint_id, notification_type, title, message,
                     created_at)
                VALUES (7, NULL, 'account', 'Account update', 'Profile changed',
                        '2026-03-01T00:00:00')
                """
            )
            connection.executemany(
                """
                INSERT INTO ai_analysis_results
                    (complaint_id, analysis_type, model_name, result_json,
                     confidence, error_message, created_at)
                VALUES (42, 'text_classification', ?, ?, NULL, ?, ?)
                """,
                [
                    (
                        "classifier-v1",
                        '{"category":"Roads"}',
                        None,
                        "2026-03-01T00:00:00",
                    ),
                    (
                        "classifier-v2",
                        "{}",
                        "Model returned an invalid label",
                        "2026-03-02T00:00:00",
                    ),
                ],
            )
            connection.commit()
            self.assertEqual(
                connection.execute(
                    """
                    SELECT complaint_id, notification_type
                    FROM notifications WHERE title = 'Account update'
                    """
                ).fetchone(),
                (None, "account"),
            )
            self.assertEqual(
                connection.execute(
                    """
                    SELECT COUNT(*), COUNT(confidence), COUNT(error_message)
                    FROM ai_analysis_results WHERE complaint_id = 42
                    """
                ).fetchone(),
                (2, 0, 1),
            )
            self.assertEqual(
                connection.execute("PRAGMA foreign_key_check").fetchall(),
                [],
            )

    def test_backup_is_verified_and_never_overwrites_existing_file(self):
        backup_path = self.root / "backups" / "complaints.before.sqlite3"
        created_backup = create_backup(self.database_path, backup_path)
        self.assertEqual(created_backup, backup_path.resolve())
        with closing(sqlite3.connect(created_backup)) as connection:
            self.assertEqual(
                connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
            )
            self.assertEqual(
                connection.execute("SELECT id FROM complaints").fetchall(), [(42,)]
            )
        with self.assertRaises(FileExistsError):
            create_backup(self.database_path, backup_path)

    def test_migration_rejects_preexisting_foreign_key_violations(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                INSERT INTO complaints
                    (id, text, category, priority, timestamp, user_id)
                VALUES (99, 'Orphan', 'Roads', 'Low', '2026-03-01T00:00:00', 999)
                """
            )
            connection.commit()

        with self.assertRaisesRegex(RuntimeError, "foreign-key violations"):
            migrate_database(self.database_path)

        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertIsNone(
                connection.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'schema_migrations'"
                ).fetchone()
            )

    def test_legacy_complaints_receive_no_inferred_owner_assignment_or_history(self):
        legacy_path = self.root / "older-complaints.db"
        with closing(sqlite3.connect(legacy_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'citizen',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE complaints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    file TEXT,
                    lat REAL,
                    lon REAL,
                    status TEXT DEFAULT 'Pending',
                    timestamp TEXT NOT NULL
                );
                INSERT INTO users
                    (id, name, email, password_hash, role, created_at)
                VALUES
                    (1, 'Citizen', 'citizen@example.com', 'bcrypt-hash', 'citizen',
                     '2026-01-01T10:00:00');
                INSERT INTO complaints
                    (id, text, category, priority, file, status, timestamp)
                VALUES
                    (88, 'Unlinked legacy complaint', 'Roads', 'Low',
                     'C:\\legacy\\old.jpg', 'Resolved', '2025-12-01T12:00:00');
                """
            )
            connection.commit()

        self.assertEqual(migrate_database(legacy_path), CURRENT_SCHEMA_VERSION)
        with closing(sqlite3.connect(legacy_path)) as connection:
            self.assertEqual(
                connection.execute(
                    """
                    SELECT id, status, timestamp, file, user_id, officer_id,
                           assigned_at, resolution_date, resolution_remarks
                    FROM complaints
                    """
                ).fetchone(),
                (
                    88,
                    "Resolved",
                    "2025-12-01T12:00:00",
                    "C:\\legacy\\old.jpg",
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM complaint_status_history"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM complaint_assignment_history"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM ai_analysis_results"
                ).fetchone()[0],
                0,
            )


if __name__ == "__main__":
    unittest.main()
