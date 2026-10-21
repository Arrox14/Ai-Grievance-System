import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from app.core import config
from app.migrations.runner import migrate_database


class AdminDashboardApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.base_dir_patch = patch.object(config, "BASE_DIR", str(self.root))
        self.base_dir_patch.start()
        self.uploads_dir = self.root / "uploads"
        self.uploads_dir.mkdir()
        self.uploads_patch = patch.object(main, "UPLOADS_DIR", str(self.uploads_dir))
        self.uploads_patch.start()
        self.environment_patch = patch.dict(
            os.environ,
            {"JWT_SECRET": "test-jwt-secret-that-is-at-least-32-characters"},
        )
        self.environment_patch.start()

        migrate_database(self.root / "complaints.db")
        self.connection = sqlite3.connect(self.root / "complaints.db")
        self.connection.executemany(
            """
            INSERT INTO users (id, name, email, password_hash, role, created_at)
            VALUES (?, ?, ?, 'unused', ?, '2026-01-01')
            """,
            [
                (1, "Citizen One", "citizen@example.com", "citizen"),
                (3, "Road Officer", "roads@example.com", "officer"),
                (4, "Admin One", "admin@example.com", "admin"),
                (5, "Water Officer", "water@example.com", "officer"),
            ],
        )
        self.connection.executemany(
            "INSERT INTO departments (id, name, created_at) VALUES (?, ?, '2026-01-01')",
            [(1, "Roads"), (2, "Water")],
        )
        self.connection.executemany(
            "INSERT INTO officer_profiles (user_id, department_id, created_at) VALUES (?, ?, '2026-01-01')",
            [(3, 1), (5, 2)],
        )
        evidence_path = self.uploads_dir / "evidence.png"
        evidence_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        self.connection.executemany(
            """
            INSERT INTO complaints
                (id, text, category, priority, file, status, timestamp, user_id,
                 officer_id, assigned_at, resolution_date, resolution_remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            [
                (101, "Broken road near the park", "Roads", "High",
                 str(evidence_path.resolve()), "Pending", "2026-06-10T08:30:00",
                 3, "2026-06-10T09:00:00", None, None),
                (102, "Water pressure is low", "Water", "Low",
                 None, "Resolved", "2026-06-12T12:00:00",
                 None, None, "2026-06-13", "Water supply restored"),
                (103, "Road surface damaged", "Roads", "Medium",
                 None, "In Progress", "2026-06-11T09:00:00",
                 5, "2026-06-11T10:00:00", None, None),
            ],
        )
        self.connection.execute(
            """
            INSERT INTO complaint_status_history
                (complaint_id, previous_status, status, changed_at, actor_id,
                 actor_name, actor_email, remarks)
            VALUES (101, 'Pending', 'In Progress', '2026-06-10T10:00:00',
                    4, 'Admin One', 'admin@example.com', 'Work started')
            """
        )
        self.connection.execute(
            """
            INSERT INTO complaint_assignment_history
                (complaint_id, previous_officer_id, new_officer_id, department_id,
                 assigned_by, assigned_at, reason)
            VALUES (101, NULL, 3, 1, 4, '2026-06-10T09:00:00', 'Road repair')
            """
        )
        self.connection.commit()
        self.client = TestClient(main.app)
        self.tokens = {
            role: main.create_access_token(user_id, f"{role}@example.com", role)
            for role, user_id in (("admin", 4), ("citizen", 1), ("officer", 3))
        }

    def tearDown(self):
        self.client.close()
        self.connection.close()
        self.environment_patch.stop()
        self.uploads_patch.stop()
        self.base_dir_patch.stop()
        self.temp_dir.cleanup()

    def headers(self, role):
        return {"Authorization": f"Bearer {self.tokens[role]}"}

    def test_server_search_filters_and_pagination(self):
        search = self.client.get(
            "/admin/complaints",
            params={"search": "broken road"},
            headers=self.headers("admin"),
        )
        self.assertEqual(search.status_code, 200, search.text)
        self.assertEqual([row["id"] for row in search.json()["items"]], ["101"])

        filtered = self.client.get(
            "/admin/complaints",
            params={
                "category": "Roads",
                "priority": "High",
                "status": "Pending",
                "date_from": "2026-06-10",
                "date_to": "2026-06-11",
                "department_id": 1,
                "officer_id": 3,
            },
            headers=self.headers("admin"),
        )
        self.assertEqual(filtered.status_code, 200, filtered.text)
        self.assertEqual([row["id"] for row in filtered.json()["items"]], ["101"])

        paged = self.client.get(
            "/admin/complaints",
            params={"sort": "priority", "page": 2, "page_size": 1},
            headers=self.headers("admin"),
        )
        self.assertEqual(paged.status_code, 200, paged.text)
        self.assertEqual(paged.json()["items"][0]["id"], "103")
        self.assertEqual(paged.json()["total"], 3)
        self.assertEqual(paged.json()["stats"]["pending"], 1)

    def test_query_validation_and_admin_authorization(self):
        invalid_range = self.client.get(
            "/admin/complaints",
            params={"date_from": "2026-06-12", "date_to": "2026-06-10"},
            headers=self.headers("admin"),
        )
        invalid_sort = self.client.get(
            "/admin/complaints",
            params={"sort": "timestamp DESC; DROP TABLE complaints"},
            headers=self.headers("admin"),
        )
        citizen_request = self.client.get(
            "/admin/complaints", headers=self.headers("citizen")
        )
        self.assertEqual(invalid_range.status_code, 422)
        self.assertEqual(invalid_sort.status_code, 422)
        self.assertEqual(citizen_request.status_code, 403)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM complaints").fetchone()[0],
            3,
        )

    def test_admin_detail_includes_existing_history_resolution_and_secure_evidence(self):
        response = self.client.get(
            "/admin/complaints/101", headers=self.headers("admin")
        )
        self.assertEqual(response.status_code, 200, response.text)
        details = response.json()
        self.assertEqual(details["text"], "Broken road near the park")
        self.assertEqual(details["assignment"]["officer_name"], "Road Officer")
        self.assertEqual(details["assignment"]["history"][0]["reason"], "Road repair")
        self.assertEqual(details["history"][0]["previous_status"], "Pending")
        self.assertIsNone(details["resolution"])

        evidence = self.client.get(
            details["evidence_url"], headers=self.headers("admin")
        )
        denied_evidence = self.client.get(
            details["evidence_url"], headers=self.headers("citizen")
        )
        self.assertEqual(evidence.status_code, 200)
        self.assertEqual(denied_evidence.status_code, 403)

        resolved = self.client.get(
            "/admin/complaints/102", headers=self.headers("admin")
        )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(resolved.json()["resolution"]["remarks"], "Water supply restored")

    def test_missing_complaint_is_not_found(self):
        response = self.client.get(
            "/admin/complaints/999", headers=self.headers("admin")
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
