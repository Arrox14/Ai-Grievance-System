import os
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from app.core import config
from app.database import db_transaction
from app.migrations.runner import migrate_database
from app.services.complaints import (
    assign_complaint as persist_complaint_assignment,
    transition_complaint_status,
)


class RoleAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir_patch = patch.object(config, "BASE_DIR", self.temp_dir.name)
        self.base_dir_patch.start()
        self.uploads_dir = Path(self.temp_dir.name) / "uploads"
        self.uploads_dir.mkdir()
        self.uploads_patch = patch.object(main, "UPLOADS_DIR", str(self.uploads_dir))
        self.uploads_patch.start()
        self.environment_patch = patch.dict(
            os.environ, {"JWT_SECRET": "test-jwt-secret-that-is-at-least-32-characters"}
        )
        self.environment_patch.start()

        migrate_database(main.get_db_path())
        self.connection = sqlite3.connect(main.get_db_path())
        self.connection.executemany(
            """
            INSERT INTO users (id, name, email, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "Citizen One", "citizen@example.com", "unused", "citizen", "2026-01-01"),
                (2, "Citizen Two", "other@example.com", "unused", "citizen", "2026-01-01"),
                (3, "Officer One", "officer@example.com", "unused", "officer", "2026-01-01"),
                (4, "Admin One", "admin@example.com", "unused", "admin", "2026-01-01"),
                (5, "Officer Two", "officer-two@example.com", "unused", "officer", "2026-01-01"),
            ],
        )
        self.connection.executemany(
            """
            INSERT INTO officer_profiles (user_id, department_id, created_at)
            VALUES (?, NULL, ?)
            """,
            [(3, "2026-01-01"), (5, "2026-01-01")],
        )
        self.connection.executemany(
            """
            INSERT INTO complaints
                (id, text, category, priority, status, timestamp, user_id, officer_id, assigned_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (101, "Citizen one complaint", "Roads", "High", "Pending", "2026-01-02", 1, None, None),
                (102, "Citizen two complaint", "Water", "Low", "Pending", "2026-01-03", 2, 3, "2026-01-04"),
            ],
        )
        self.connection.commit()
        self.client = TestClient(main.app)
        self.tokens = {
            role: main.create_access_token(user_id, f"{role}@example.com", role)
            for role, user_id in (
                ("citizen", 1),
                ("other_citizen", 2),
                ("officer", 3),
                ("admin", 4),
                ("other_officer", 5),
            )
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

    def _create_resolution_submission(self, complaint_id, path):
        self.connection.execute(
            "UPDATE complaints SET status = 'In Progress', officer_id = 3 WHERE id = ?",
            (complaint_id,),
        )
        self.connection.execute(
            """
            INSERT INTO complaint_resolution_submissions
                (complaint_id, officer_id, officer_name, findings, remarks,
                 resolution_date, file_path, original_filename, content_type,
                 file_size, submitted_at)
            VALUES (?, 3, 'Officer One', 'Repair verified',
                    'Repair completed and inspected.', '2026-10-14',
                    ?, 'resolution.pdf', 'application/pdf', 16,
                    '2026-10-14T10:00:00')
            """,
            (complaint_id, str(path)),
        )
        self.connection.commit()
        return self.connection.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_admin_approves_resolution_and_records_review_without_changing_original_evidence(self):
        original_evidence = self.uploads_dir / "original-evidence.png"
        original_evidence.write_bytes(b"\x89PNG\r\n\x1a\noriginal")
        self.connection.execute(
            "UPDATE complaints SET file = ? WHERE id = 101",
            (str(original_evidence),),
        )
        self.connection.commit()

        assignment = self.client.put(
            "/admin/complaints/101/assignment",
            headers=self.headers("admin"),
            json={"officer_id": 3},
        )
        self.assertEqual(assignment.status_code, 200, assignment.text)
        started = self.client.put(
            "/update-status/101",
            headers=self.headers("admin"),
            json={"status": "In Progress", "remarks": "Work started"},
        )
        self.assertEqual(started.status_code, 200, started.text)
        submission_response = self.client.post(
            "/officer/complaints/101/resolution",
            headers=self.headers("officer"),
            data={
                "findings": "The road surface was repaired.",
                "remarks": "Repair completed and inspected.",
                "resolution_date": datetime.now(timezone.utc).date().isoformat(),
            },
            files={
                "file": (
                    "repair-report.pdf",
                    b"%PDF-1.4 resolution evidence",
                    "application/pdf",
                )
            },
        )
        self.assertEqual(
            submission_response.status_code,
            200,
            submission_response.text,
        )
        submission_id = submission_response.json()["id"]
        forbidden_reviews = [
            self.client.post(
                f"/admin/resolution-submissions/{submission_id}/approve",
                headers=self.headers(role),
                json={"remarks": "Reviewed"},
            )
            for role in ("citizen", "officer")
        ]
        self.assertEqual([response.status_code for response in forbidden_reviews], [403, 403])
        invalid_review = self.client.post(
            f"/admin/resolution-submissions/{submission_id}/approve",
            headers=self.headers("admin"),
            json={"remarks": "x" * 2001},
        )
        self.assertEqual(invalid_review.status_code, 422)

        approval = self.client.post(
            f"/admin/resolution-submissions/{submission_id}/approve",
            headers=self.headers("admin"),
            json={"remarks": "Evidence checked; work is complete."},
        )
        self.assertEqual(approval.status_code, 200, approval.text)
        self.assertEqual(approval.json()["status"], "Resolved")
        complaint = self.connection.execute(
            """
            SELECT text, file, status, resolution_remarks
            FROM complaints WHERE id = 101
            """
        ).fetchone()
        self.assertEqual(
            complaint,
            (
                "Citizen one complaint",
                str(original_evidence),
                "Resolved",
                "Repair completed and inspected.",
            ),
        )
        self.assertEqual(original_evidence.read_bytes(), b"\x89PNG\r\n\x1a\noriginal")
        review = self.connection.execute(
            """
            SELECT review_status, reviewed_by, reviewed_at, review_remarks
            FROM complaint_resolution_submissions WHERE id = ?
            """,
            (submission_id,),
        ).fetchone()
        self.assertEqual(review[0:2], ("approved", 4))
        self.assertTrue(review[2])
        self.assertEqual(review[3], "Evidence checked; work is complete.")
        transition = self.connection.execute(
            """
            SELECT previous_status, status, actor_id, changed_at, remarks
            FROM complaint_status_history
            WHERE complaint_id = 101 AND status = 'Resolved'
            """
        ).fetchone()
        self.assertEqual(transition[:3], ("In Progress", "Resolved", 4))
        self.assertEqual(transition[3], review[2])
        self.assertIn("Repair completed and inspected.", transition[4])
        self.assertIn("Evidence checked; work is complete.", transition[4])

        admin_details = self.client.get(
            "/admin/complaints/101", headers=self.headers("admin")
        )
        citizen_details = self.client.get(
            "/my-complaints/101", headers=self.headers("citizen")
        )
        self.assertEqual(admin_details.status_code, 200, admin_details.text)
        self.assertEqual(citizen_details.status_code, 200, citizen_details.text)
        for details in (admin_details.json(), citizen_details.json()):
            self.assertEqual(details["status"], "Resolved")
            self.assertEqual(details["resolution"]["completed_by"], "Admin One")
            self.assertEqual(
                details["resolution"]["administrator_remarks"],
                "Evidence checked; work is complete.",
            )
            self.assertEqual(details["resolution"]["completed_at"], review[2])
        file_url = citizen_details.json()["resolution"]["attachment_url"]
        downloaded = self.client.get(file_url, headers=self.headers("citizen"))
        denied = self.client.get(file_url, headers=self.headers("other_citizen"))
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, b"%PDF-1.4 resolution evidence")
        self.assertEqual(denied.status_code, 404)

    def test_admin_rejection_is_audited_without_resolving_complaint(self):
        resolution_path = self.uploads_dir / "rejected-resolution.pdf"
        resolution_path.write_bytes(b"%PDF-1.4 rejection evidence")
        submission_id = self._create_resolution_submission(101, resolution_path)
        history_before = self.connection.execute(
            "SELECT COUNT(*) FROM complaint_status_history WHERE complaint_id = 101"
        ).fetchone()[0]

        response = self.client.post(
            f"/admin/resolution-submissions/{submission_id}/reject",
            headers=self.headers("admin"),
            json={"remarks": "Evidence does not confirm completion."},
        )
        self.assertEqual(response.status_code, 200, response.text)
        review = self.connection.execute(
            """
            SELECT review_status, reviewed_by, reviewed_at, review_remarks
            FROM complaint_resolution_submissions WHERE id = ?
            """,
            (submission_id,),
        ).fetchone()
        self.assertEqual(review[0:2], ("rejected", 4))
        self.assertTrue(review[2])
        self.assertEqual(review[3], "Evidence does not confirm completion.")
        self.assertEqual(
            self.connection.execute(
                "SELECT status, resolution_date, resolution_remarks FROM complaints WHERE id = 101"
            ).fetchone(),
            ("In Progress", None, None),
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM complaint_status_history WHERE complaint_id = 101"
            ).fetchone()[0],
            history_before,
        )
        details = self.client.get(
            "/admin/complaints/101", headers=self.headers("admin")
        )
        self.assertEqual(details.status_code, 200, details.text)
        self.assertIsNone(details.json()["resolution"])
        self.assertEqual(details.json()["resolution_review"]["status"], "rejected")
        self.assertEqual(
            details.json()["resolution_review"]["reviewed_by"], "Admin One"
        )
        citizen_details = self.client.get(
            "/my-complaints/101", headers=self.headers("citizen")
        )
        self.assertEqual(citizen_details.status_code, 200, citizen_details.text)
        self.assertIsNone(citizen_details.json()["resolution"])

    def test_resolution_submission_validates_dates_authorization_and_missing_reviews(self):
        future_date = (
            datetime.now(timezone.utc).date() + timedelta(days=1)
        ).isoformat()
        future_resolution = self.client.post(
            "/officer/complaints/102/resolution",
            headers=self.headers("officer"),
            data={
                "findings": "Future work",
                "remarks": "Cannot complete in the future",
                "resolution_date": future_date,
            },
            files={"file": ("report.pdf", b"%PDF-1.4 valid", "application/pdf")},
        )
        unauthorized_submission = self.client.post(
            "/officer/complaints/102/resolution",
            headers=self.headers("admin"),
            data={
                "findings": "Attempt",
                "remarks": "Not authorized",
                "resolution_date": "2026-10-14",
            },
            files={"file": ("report.pdf", b"%PDF-1.4 valid", "application/pdf")},
        )
        missing_submission = self.client.post(
            "/admin/resolution-submissions/999/approve",
            headers=self.headers("admin"),
            json={"remarks": "Reviewed"},
        )
        self.assertEqual(future_resolution.status_code, 422)
        self.assertEqual(unauthorized_submission.status_code, 403)
        self.assertEqual(missing_submission.status_code, 404)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM complaint_resolution_submissions"
            ).fetchone()[0],
            0,
        )

    def test_citizen_can_only_list_and_view_owned_complaints(self):
        own_list = self.client.get("/my-complaints", headers=self.headers("citizen"))
        self.assertEqual(own_list.status_code, 200, own_list.text)
        self.assertEqual([item["id"] for item in own_list.json()["items"]], ["101"])

        own_details = self.client.get(
            "/my-complaints/101", headers=self.headers("citizen")
        )
        self.assertEqual(own_details.status_code, 200, own_details.text)

        other_details = self.client.get(
            "/my-complaints/102", headers=self.headers("citizen")
        )
        self.assertEqual(other_details.status_code, 404)

    def test_complaint_owner_comes_from_authenticated_citizen_not_request_data(self):
        class Vectorizer:
            @staticmethod
            def transform(_texts):
                return object()

        class Classifier:
            @staticmethod
            def predict(_vectors):
                return [0]

        class LabelEncoder:
            @staticmethod
            def inverse_transform(_labels):
                return ["Roads"]

        with ExitStack() as patch_stack:
            patch_stack.enter_context(patch.object(main, "vectorizer", Vectorizer()))
            patch_stack.enter_context(patch.object(main, "model_category", Classifier()))
            patch_stack.enter_context(patch.object(main, "model_priority", Classifier()))
            patch_stack.enter_context(patch.object(main, "le_category", LabelEncoder()))
            patch_stack.enter_context(patch.object(main, "le_priority", LabelEncoder()))
            response = self.client.post(
                "/submit-complaint",
                headers=self.headers("citizen"),
                data={"text": "A road needs repair", "user_id": "2"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        complaint_id = int(response.json()["id"])
        owner_id = self.connection.execute(
            "SELECT user_id FROM complaints WHERE id = ?", (complaint_id,)
        ).fetchone()[0]
        self.assertEqual(owner_id, 1)
        analysis = self.connection.execute(
            """
            SELECT analysis_type, model_name, result_json
            FROM ai_analysis_results WHERE complaint_id = ?
            """,
            (complaint_id,),
        ).fetchone()
        self.assertEqual(analysis[0:2], ("text_classification", "tfidf_svm_category_priority"))
        self.assertEqual(json.loads(analysis[2]), {"category": "Roads", "priority": "Roads"})

    def test_assignment_and_reassignment_are_recorded_without_changing_response_shape(self):
        initial = self.client.put(
            "/admin/complaints/101/assignment",
            headers=self.headers("admin"),
            json={"officer_id": 3},
        )
        self.assertEqual(initial.status_code, 200, initial.text)
        self.assertEqual(
            set(initial.json()),
            {"message", "complaint_id", "officer_id", "assigned_at"},
        )
        reassignment = self.client.put(
            "/admin/complaints/101/assignment",
            headers=self.headers("admin"),
            json={"officer_id": 5},
        )
        self.assertEqual(reassignment.status_code, 200, reassignment.text)
        repeated_assignment = self.client.put(
            "/admin/complaints/101/assignment",
            headers=self.headers("admin"),
            json={"officer_id": 5},
        )
        self.assertEqual(repeated_assignment.status_code, 200, repeated_assignment.text)

        history = self.connection.execute(
            """
            SELECT previous_officer_id, new_officer_id, assigned_by, assigned_at
            FROM complaint_assignment_history
            WHERE complaint_id = 101 ORDER BY id
            """
        ).fetchall()
        self.assertEqual(
            [(row[0], row[1], row[2]) for row in history],
            [(None, 3, 4), (3, 5, 4)],
        )
        self.assertTrue(all(row[3] for row in history))
        current_assignment = self.connection.execute(
            "SELECT officer_id, assigned_at FROM complaints WHERE id = 101"
        ).fetchone()
        self.assertEqual(current_assignment[0], 5)
        self.assertEqual(current_assignment[1], history[-1][3])
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM notifications WHERE complaint_id = 101"
            ).fetchone()[0],
            2,
        )

    def test_assignment_rejects_inactive_ineligible_and_missing_officers(self):
        self.connection.execute(
            "INSERT INTO departments (id, name, is_active, created_at) "
            "VALUES (1, 'Inactive department', 0, '2026-01-01')"
        )
        self.connection.execute(
            "UPDATE officer_profiles SET department_id = 1 WHERE user_id = 5"
        )
        self.connection.execute(
            "UPDATE users SET is_active = 0 WHERE id = 3"
        )
        self.connection.commit()

        missing = self.client.put(
            "/admin/complaints/101/assignment",
            headers=self.headers("admin"),
            json={"officer_id": 999},
        )
        inactive = self.client.put(
            "/admin/complaints/101/assignment",
            headers=self.headers("admin"),
            json={"officer_id": 3},
        )
        department_inactive = self.client.put(
            "/admin/complaints/101/assignment",
            headers=self.headers("admin"),
            json={"officer_id": 5},
        )
        not_an_officer = self.client.put(
            "/admin/complaints/101/assignment",
            headers=self.headers("admin"),
            json={"officer_id": 1},
        )
        invalid_id = self.client.put(
            "/admin/complaints/101/assignment",
            headers=self.headers("admin"),
            json={"officer_id": 0},
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(inactive.status_code, 422)
        self.assertEqual(department_inactive.status_code, 422)
        self.assertEqual(not_an_officer.status_code, 422)
        self.assertEqual(invalid_id.status_code, 422)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM complaint_assignment_history WHERE complaint_id = 101"
            ).fetchone()[0],
            0,
        )
        eligible_officers = self.client.get(
            "/admin/officers", headers=self.headers("admin")
        )
        self.assertEqual(eligible_officers.status_code, 200)
        self.assertEqual(eligible_officers.json(), [])

    def test_status_transition_records_actor_and_ignores_repeated_status(self):
        first = self.client.put(
            "/update-status/101",
            headers=self.headers("admin"),
            json={"status": "In Progress", "remarks": "Reviewed by dispatch"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        repeated = self.client.put(
            "/update-status/101",
            headers=self.headers("admin"),
            json={"status": "In Progress", "remarks": "Repeated request"},
        )
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(repeated.json()["message"], "Status is unchanged")

        history = self.connection.execute(
            """
            SELECT previous_status, status, actor_id, changed_at, remarks
            FROM complaint_status_history WHERE complaint_id = 101
            ORDER BY id
            """
        ).fetchall()
        self.assertEqual(len(history), 1)
        self.assertEqual(
            history[0][:3], ("Pending", "In Progress", 4)
        )
        self.assertTrue(history[0][3])
        self.assertEqual(history[0][4], "Reviewed by dispatch")
        self.assertEqual(
            self.connection.execute(
                "SELECT status FROM complaints WHERE id = 101"
            ).fetchone()[0],
            "In Progress",
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM notifications WHERE complaint_id = 101"
            ).fetchone()[0],
            1,
        )

    def test_status_history_insert_failure_rolls_back_status_update(self):
        self.connection.execute(
            """
            CREATE TRIGGER reject_status_notification
            BEFORE INSERT ON notifications
            BEGIN
                SELECT RAISE(ABORT, 'forced notification failure');
            END
            """
        )
        self.connection.commit()
        actor = {
            "id": 4,
            "name": "Admin One",
            "email": "admin@example.com",
        }
        with self.assertRaises(sqlite3.IntegrityError):
            with db_transaction() as connection:
                connection.execute("BEGIN IMMEDIATE")
                transition_complaint_status(
                    connection,
                    101,
                    "In Progress",
                    actor,
                    "Test",
                )
                connection.execute(
                    """
                    INSERT INTO notifications
                        (user_id, complaint_id, title, message, created_at)
                    VALUES (1, 101, 'Status changed', 'Test', '2026-01-05')
                    """
                )
        self.assertEqual(
            self.connection.execute(
                "SELECT status FROM complaints WHERE id = 101"
            ).fetchone()[0],
            "Pending",
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM complaint_status_history WHERE complaint_id = 101"
            ).fetchone()[0],
            0,
        )

    def test_admin_status_transitions_reject_invalid_and_final_status_changes(self):
        invalid_status = self.client.put(
            "/update-status/101",
            headers=self.headers("admin"),
            json={"status": "In Review"},
        )
        missing_complaint = self.client.put(
            "/update-status/999",
            headers=self.headers("admin"),
            json={"status": "In Progress"},
        )
        direct_resolve = self.client.put(
            "/update-status/101",
            headers=self.headers("admin"),
            json={"status": "Resolved"},
        )
        self.assertEqual(invalid_status.status_code, 422)
        self.assertEqual(missing_complaint.status_code, 404)
        self.assertEqual(direct_resolve.status_code, 409)

        self.connection.execute(
            "UPDATE complaints SET status = 'Resolved' WHERE id = 101"
        )
        self.connection.commit()
        history_before = self.connection.execute(
            "SELECT COUNT(*) FROM complaint_status_history WHERE complaint_id = 101"
        ).fetchone()[0]
        reopen = self.client.put(
            "/update-status/101",
            headers=self.headers("admin"),
            json={"status": "In Progress", "remarks": "Attempt to reopen"},
        )
        self.assertEqual(reopen.status_code, 409)
        self.assertEqual(
            self.connection.execute(
                "SELECT status FROM complaints WHERE id = 101"
            ).fetchone()[0],
            "Resolved",
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM complaint_status_history WHERE complaint_id = 101"
            ).fetchone()[0],
            history_before,
        )

    def test_assignment_history_insert_failure_rolls_back_assignment(self):
        self.connection.execute(
            """
            CREATE TRIGGER reject_assignment_notification
            BEFORE INSERT ON notifications
            BEGIN
                SELECT RAISE(ABORT, 'forced notification failure');
            END
            """
        )
        self.connection.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            with db_transaction() as connection:
                connection.execute("BEGIN IMMEDIATE")
                assignment = persist_complaint_assignment(
                    connection,
                    101,
                    3,
                    4,
                )
                connection.execute(
                    """
                    INSERT INTO notifications
                        (user_id, complaint_id, title, message, created_at)
                    VALUES (?, 101, 'Complaint assigned', 'Test', ?)
                    """,
                    (assignment["owner_id"], assignment["assigned_at"]),
                )
        self.assertEqual(
            self.connection.execute(
                "SELECT officer_id, assigned_at FROM complaints WHERE id = 101"
            ).fetchone(),
            (None, None),
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM complaint_assignment_history WHERE complaint_id = 101"
            ).fetchone()[0],
            0,
        )

    def test_upload_rejects_bad_mime_signatures_and_oversized_files(self):
        responses = [
            self.client.post(
                "/upload",
                headers=self.headers("citizen"),
                files={"file": ("evidence.jpg", b"not an image", "image/jpeg")},
            ),
            self.client.post(
                "/upload",
                headers=self.headers("citizen"),
                files={"file": ("evidence.jpg", b"\xff\xd8\xffdata", "image/png")},
            ),
            self.client.post(
                "/upload",
                headers=self.headers("citizen"),
                files={
                    "file": (
                        "evidence.jpg",
                        b"\xff\xd8\xff" + b"x" * (10 * 1024 * 1024),
                        "image/jpeg",
                    )
                },
            ),
        ]
        self.assertEqual([response.status_code for response in responses], [400, 400, 413])
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM uploaded_files").fetchone()[0],
            0,
        )
        self.assertEqual(list(self.uploads_dir.iterdir()), [])

    def test_officer_can_only_view_complaints_assigned_to_them(self):
        assigned = self.client.get(
            "/officer/complaints", headers=self.headers("officer")
        )
        self.assertEqual(assigned.status_code, 200, assigned.text)
        self.assertEqual([item["id"] for item in assigned.json()], ["102"])
        self.assertEqual(
            {
                key: assigned.json()[0][key]
                for key in ("description", "category", "priority", "submitted_at", "status")
            },
            {
                "description": "Citizen two complaint",
                "category": "Water",
                "priority": "Low",
                "submitted_at": "2026-01-03",
                "status": "Pending",
            },
        )
        self.assertEqual(assigned.json()[0]["assigned_at"], "2026-01-04")

        assigned_details = self.client.get(
            "/officer/complaints/102", headers=self.headers("officer")
        )
        self.assertEqual(assigned_details.status_code, 200, assigned_details.text)

        unassigned_details = self.client.get(
            "/officer/complaints/101", headers=self.headers("officer")
        )
        self.assertEqual(unassigned_details.status_code, 404)

    def test_other_users_cannot_access_private_files_or_notifications(self):
        evidence_path = self.uploads_dir / "private-evidence.png"
        evidence_path.write_bytes(b"citizen evidence")
        resolution_path = self.uploads_dir / "private-resolution.pdf"
        resolution_path.write_bytes(b"%PDF-1.4 test")
        self.connection.execute(
            "UPDATE complaints SET file = ? WHERE id = ?",
            (str(evidence_path), 102),
        )
        self.connection.execute(
            """
            INSERT INTO notifications (user_id, complaint_id, title, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (2, 102, "Private update", "For citizen two", "2026-01-05"),
        )
        notification_id = self.connection.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        self.connection.execute(
            """
            INSERT INTO notifications
                (user_id, complaint_id, notification_type, title, message, created_at)
            VALUES (2, NULL, 'account', 'Account update', 'Profile changed', '2026-01-06')
            """
        )
        self.connection.execute(
            """
            INSERT INTO complaint_resolution_submissions
                (complaint_id, officer_id, officer_name, findings, remarks,
                 resolution_date, file_path, original_filename, content_type,
                 file_size, submitted_at, review_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved')
            """,
            (
                102,
                3,
                "Officer One",
                "Findings",
                "Resolved",
                "2026-01-05",
                str(resolution_path),
                resolution_path.name,
                "application/pdf",
                resolution_path.stat().st_size,
                "2026-01-05",
            ),
        )
        submission_id = self.connection.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        self.connection.commit()

        self.assertEqual(
            self.client.get("/my-complaints/102/evidence").status_code,
            401,
        )
        self.assertEqual(
            self.client.get(
                "/my-complaints/102/evidence", headers=self.headers("citizen")
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                "/analyze-image",
                params={"file_path": str(evidence_path)},
                headers=self.headers("citizen"),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/resolution-submissions/{submission_id}/file",
                headers=self.headers("citizen"),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.patch(
                f"/notifications/{notification_id}/read",
                headers=self.headers("citizen"),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT is_read FROM notifications WHERE id = ?", (notification_id,)
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.client.patch(
                f"/notifications/{notification_id}/read",
                headers=self.headers("other_citizen"),
            ).status_code,
            200,
        )
        notification_list = self.client.get(
            "/notifications", headers=self.headers("other_citizen")
        )
        self.assertEqual(notification_list.status_code, 200, notification_list.text)
        generic_notification = next(
            item
            for item in notification_list.json()["notifications"]
            if item["title"] == "Account update"
        )
        self.assertIsNone(generic_notification["complaint_id"])
        self.assertEqual(generic_notification["notification_type"], "account")

        self.assertEqual(
            self.client.get(
                "/my-complaints/102/evidence", headers=self.headers("other_citizen")
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                f"/resolution-submissions/{submission_id}/file",
                headers=self.headers("other_citizen"),
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                f"/resolution-submissions/{submission_id}/file",
                headers=self.headers("other_officer"),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/resolution-submissions/{submission_id}/file",
                headers=self.headers("officer"),
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                "/officer/complaints/102/evidence",
                headers=self.headers("other_officer"),
            ).status_code,
            404,
        )

    def test_roles_cannot_use_other_roles_operations_or_other_officer_assignments(self):
        initial_history_count = self.connection.execute(
            "SELECT COUNT(*) FROM complaint_status_history"
        ).fetchone()[0]
        initial_assignment_history_count = self.connection.execute(
            "SELECT COUNT(*) FROM complaint_assignment_history"
        ).fetchone()[0]
        unauthorized_responses = [
            self.client.get("/admin/officers", headers=self.headers("citizen")),
            self.client.put(
                "/admin/complaints/101/assignment",
                headers=self.headers("officer"),
                json={"officer_id": 3},
            ),
            self.client.put(
                "/update-status/101",
                headers=self.headers("citizen"),
                json={"status": "In Progress"},
            ),
            self.client.put(
                "/officer/complaints/102/status",
                headers=self.headers("citizen"),
                json={"status": "In Progress"},
            ),
            self.client.get(
                "/officer/complaints/102",
                headers=self.headers("other_officer"),
            ),
            self.client.put(
                "/officer/complaints/102/status",
                headers=self.headers("other_officer"),
                json={"status": "In Progress"},
            ),
        ]
        self.assertEqual(
            [response.status_code for response in unauthorized_responses],
            [403, 403, 403, 403, 404, 404],
        )
        status = self.connection.execute(
            "SELECT status FROM complaints WHERE id = 102"
        ).fetchone()[0]
        self.assertEqual(status, "Pending")
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM complaint_status_history"
            ).fetchone()[0],
            initial_history_count,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM complaint_assignment_history"
            ).fetchone()[0],
            initial_assignment_history_count,
        )

        allowed = self.client.put(
            "/officer/complaints/102/status",
            headers=self.headers("officer"),
            json={"status": "In Progress"},
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)
        status_event = self.connection.execute(
            """
            SELECT previous_status, status, actor_id
            FROM complaint_status_history WHERE complaint_id = 102
            """
        ).fetchone()
        self.assertEqual(status_event, ("Pending", "In Progress", 3))

    def test_admin_can_access_admin_lists_but_not_citizen_or_officer_routes(self):
        complaints = self.client.get("/complaints", headers=self.headers("admin"))
        self.assertEqual(complaints.status_code, 200, complaints.text)
        self.assertEqual({item["id"] for item in complaints.json()}, {"101", "102"})

        officers = self.client.get("/admin/officers", headers=self.headers("admin"))
        self.assertEqual(officers.status_code, 200, officers.text)
        self.assertEqual([item["id"] for item in officers.json()], [3, 5])

        self.assertEqual(
            self.client.get("/my-complaints", headers=self.headers("admin")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/officer/complaints", headers=self.headers("admin")).status_code,
            403,
        )
        status_update = self.client.put(
            "/update-status/101",
            headers=self.headers("admin"),
            json={"status": "In Progress"},
        )
        self.assertEqual(status_update.status_code, 200, status_update.text)

    def test_forbidden_role_actions_return_403_and_missing_auth_returns_401(self):
        self.assertEqual(self.client.get("/complaints").status_code, 401)
        self.assertEqual(
            self.client.get("/admin/officers", headers=self.headers("citizen")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/admin/officers", headers=self.headers("officer")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/officer/complaints", headers=self.headers("citizen")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/my-complaints", headers=self.headers("officer")).status_code,
            403,
        )

    def test_database_role_overrides_any_role_claim_in_a_signed_token(self):
        token = jwt.encode(
            {
                "sub": "1",
                "role": "admin",
                "sv": 0,
                "exp": datetime.now(timezone.utc).timestamp() + 300,
            },
            os.environ["JWT_SECRET"],
            algorithm=main.JWT_ALGORITHM,
        )
        response = self.client.get(
            "/complaints", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_officers_but_cannot_assign_another_role(self):
        created = self.client.post(
            "/admin/officers",
            headers=self.headers("admin"),
            json={
                "name": "New Officer",
                "email": "new-officer@example.com",
                "password": "valid-password",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["role"], "officer")

        escalation = self.client.post(
            "/admin/officers",
            headers=self.headers("admin"),
            json={
                "name": "Escalation Attempt",
                "email": "escalation@example.com",
                "password": "valid-password",
                "role": "admin",
            },
        )
        self.assertEqual(escalation.status_code, 422)

        forbidden = self.client.post(
            "/admin/officers",
            headers=self.headers("citizen"),
            json={
                "name": "Unauthorized Officer",
                "email": "unauthorized@example.com",
                "password": "valid-password",
            },
        )
        self.assertEqual(forbidden.status_code, 403)

        role = self.connection.execute(
            "SELECT role FROM users WHERE email = ?",
            ("escalation@example.com",),
        ).fetchone()
        self.assertIsNone(role)


if __name__ == "__main__":
    unittest.main()
