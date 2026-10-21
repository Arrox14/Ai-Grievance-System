import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import bcrypt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reset_admin_password import reset_admin_password


class ResetAdminPasswordTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    token_version INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO users (id, email, password_hash, role, token_version)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (1, "admin@example.com", "old-admin-hash", "admin", 0),
                    (2, "citizen@example.com", "citizen-hash", "citizen", 0),
                ],
            )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resets_existing_admin_password_and_invalidates_tokens(self):
        reset_admin_password(
            self.database_path,
            " ADMIN@EXAMPLE.COM ",
            "a-new-strong-password",
        )

        with closing(sqlite3.connect(self.database_path)) as connection:
            admin = connection.execute(
                "SELECT password_hash, role, token_version FROM users WHERE id = 1"
            ).fetchone()
            citizen = connection.execute(
                "SELECT password_hash, role, token_version FROM users WHERE id = 2"
            ).fetchone()

        self.assertTrue(
            bcrypt.checkpw(b"a-new-strong-password", admin[0].encode("utf-8"))
        )
        self.assertEqual(admin[1:], ("admin", 1))
        self.assertEqual(citizen, ("citizen-hash", "citizen", 0))

    def test_refuses_unknown_or_non_admin_email(self):
        for email in ("missing@example.com", "citizen@example.com"):
            with self.subTest(email=email):
                with self.assertRaisesRegex(ValueError, "No administrator account"):
                    reset_admin_password(
                        self.database_path,
                        email,
                        "a-new-strong-password",
                    )

    def test_rejects_password_outside_backend_limits(self):
        for password in ("short", "é" * 37):
            with self.subTest(password_length=len(password)):
                with self.assertRaises(ValueError):
                    reset_admin_password(self.database_path, "admin@example.com", password)


if __name__ == "__main__":
    unittest.main()
