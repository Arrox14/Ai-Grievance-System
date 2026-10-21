import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from app.core import config


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "complaints.db"
        self.connection = sqlite3.connect(self.database_path)
        self.connection.execute(
            """
            CREATE TABLE users (
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
        self.connection.commit()
        self.connection.close()
        self.base_dir_patch = patch.object(config, "BASE_DIR", self.temp_dir.name)
        self.base_dir_patch.start()
        self.environment_patch = patch.dict(
            os.environ, {"JWT_SECRET": "test-jwt-secret-that-is-at-least-32-characters"}
        )
        self.environment_patch.start()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.environment_patch.stop()
        self.base_dir_patch.stop()
        self.temp_dir.cleanup()

    def register_citizen(self, email="citizen@example.com", password="citizen-password"):
        return self.client.post(
            "/register",
            json={"name": "Test Citizen", "email": email, "password": password},
        )

    def test_register_and_valid_login_store_only_password_hash(self):
        registration = self.register_citizen()
        self.assertEqual(registration.status_code, 200, registration.text)
        registered = registration.json()
        self.assertEqual(registered["user"]["role"], "citizen")
        self.assertNotIn("password", registered["user"])
        self.assertNotIn("password_hash", registered["user"])

        conn = sqlite3.connect(self.database_path)
        password_hash, role = conn.execute(
            "SELECT password_hash, role FROM users WHERE email = ?",
            ("citizen@example.com",),
        ).fetchone()
        conn.close()
        self.assertNotEqual(password_hash, "citizen-password")
        self.assertTrue(password_hash.startswith("$2"))
        self.assertEqual(role, "citizen")

        login = self.client.post(
            "/login",
            json={"email": " CITIZEN@example.com ", "password": "citizen-password"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.json()["user"]["role"], "citizen")

    def test_registration_rejects_client_supplied_role_and_user_id(self):
        response = self.client.post(
            "/register",
            json={
                "name": "Test Citizen",
                "email": "role@example.com",
                "password": "citizen-password",
                "role": "admin",
                "user_id": 1,
            },
        )
        self.assertEqual(response.status_code, 422)

        conn = sqlite3.connect(self.database_path)
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

    def test_invalid_login_is_rejected(self):
        self.assertEqual(self.register_citizen().status_code, 200)
        response = self.client.post(
            "/login",
            json={"email": "citizen@example.com", "password": "incorrect-password"},
        )
        self.assertEqual(response.status_code, 401)

    def test_officer_and_admin_login_return_database_roles_and_reject_other_roles(self):
        conn = sqlite3.connect(self.database_path)
        conn.executemany(
            """
            INSERT INTO users (name, email, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    "Officer Test",
                    "officer@example.com",
                    main.hash_password("officer-password"),
                    "officer",
                    "2026-01-01",
                ),
                (
                    "Admin Test",
                    "admin@example.com",
                    main.hash_password("admin-password"),
                    "admin",
                    "2026-01-01",
                ),
            ],
        )
        conn.commit()
        conn.close()

        officer_login = self.client.post(
            "/login",
            json={"email": "OFFICER@example.com", "password": "officer-password"},
        )
        self.assertEqual(officer_login.status_code, 200, officer_login.text)
        self.assertEqual(officer_login.json()["user"]["role"], "officer")
        officer_me = self.client.get(
            "/me",
            headers={
                "Authorization": f"Bearer {officer_login.json()['access_token']}"
            },
        )
        self.assertEqual(officer_me.status_code, 200, officer_me.text)
        self.assertEqual(officer_me.json()["role"], "officer")
        self.assertEqual(
            self.client.get(
                "/admin/officers",
                headers={
                    "Authorization": f"Bearer {officer_login.json()['access_token']}"
                },
            ).status_code,
            403,
        )

        admin_login = self.client.post(
            "/login",
            json={"email": "admin@example.com", "password": "admin-password"},
        )
        self.assertEqual(admin_login.status_code, 200, admin_login.text)
        self.assertEqual(admin_login.json()["user"]["role"], "admin")
        self.assertEqual(
            self.client.post(
                "/login",
                json={"email": "officer@example.com", "password": "incorrect"},
            ).status_code,
            401,
        )

        citizen_login = self.register_citizen().json()
        self.assertEqual(
            self.client.get(
                "/officer/complaints",
                headers={
                    "Authorization": f"Bearer {citizen_login['access_token']}"
                },
            ).status_code,
            403,
        )

    def test_missing_invalid_and_expired_credentials_are_rejected(self):
        self.assertEqual(self.register_citizen().status_code, 200)
        self.assertEqual(self.client.get("/me").status_code, 401)
        self.assertEqual(
            self.client.get("/me", headers={"Authorization": "Bearer invalid"}).status_code,
            401,
        )

        expired_token = jwt.encode(
            {
                "sub": "1",
                "sv": 0,
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            os.environ["JWT_SECRET"],
            algorithm=main.JWT_ALGORITHM,
        )
        response = self.client.get(
            "/me", headers={"Authorization": f"Bearer {expired_token}"}
        )
        self.assertEqual(response.status_code, 401)

    def test_logout_invalidates_the_existing_token(self):
        response = self.register_citizen()
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        logout_response = self.client.post("/logout", headers=headers)
        self.assertEqual(logout_response.status_code, 200, logout_response.text)
        self.assertEqual(self.client.get("/me", headers=headers).status_code, 401)

    def test_authentication_requires_configured_jwt_secret(self):
        with patch.dict(os.environ, {"JWT_SECRET": ""}):
            response = self.register_citizen()
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
