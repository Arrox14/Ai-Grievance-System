import os
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from importlib.metadata import version as package_version
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from app.core import config
from app.migrations.runner import migrate_database
from app.services import vision
from app.services.vision import MAX_VIDEO_SAMPLED_FRAMES


class FakeBoxes:
    xyxy = [[10.5, 20.0, 70.0, 60.5], [-3.0, 1.0, 120.0, 100.0]]
    cls = [2, 5]
    conf = [0.91, 0.72]


class FakeResult:
    boxes = FakeBoxes()
    names = {2: "car", 5: "bus"}

    def __init__(self, image):
        self.image = image

    def plot(self):
        return np.full_like(self.image, 127)


class FakeModel:
    def __init__(self):
        self.calls = []

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        return [FakeResult(kwargs["source"])]


class EmptyBoxes:
    xyxy = []
    cls = []
    conf = []


class EmptyResult(FakeResult):
    boxes = EmptyBoxes()


class EmptyModel(FakeModel):
    def predict(self, **kwargs):
        self.calls.append(kwargs)
        return [EmptyResult(kwargs["source"])]


class FailingModel(FakeModel):
    def predict(self, **kwargs):
        raise RuntimeError("inference failed")


class FakeVideoCapture:
    def __init__(self, _path=None, frames=None, fps=10.0, declared_frames=None, opened=True):
        self.frames = frames or [
            np.zeros((40, 60, 3), dtype=np.uint8) for _ in range(5)
        ]
        self.fps = fps
        self.declared_frames = (
            declared_frames if declared_frames is not None else len(self.frames)
        )
        self.opened = opened
        self.position = 0
        self.released = False

    def isOpened(self):
        return self.opened

    def get(self, property_id):
        return {
            cv2.CAP_PROP_FPS: self.fps,
            cv2.CAP_PROP_FRAME_COUNT: self.declared_frames,
            cv2.CAP_PROP_FRAME_WIDTH: 60,
            cv2.CAP_PROP_FRAME_HEIGHT: 40,
        }.get(property_id, 0)

    def read(self):
        if self.position >= len(self.frames):
            return False, None
        frame = self.frames[self.position]
        self.position += 1
        return True, frame

    def release(self):
        self.released = True


class FakeVideoWriter:
    instances = []

    def __init__(self, path, _fourcc, fps, size):
        self.path = path
        self.fps = fps
        self.size = size
        self.frames = []
        self.opened = True
        self.released = False
        self.instances.append(self)

    def isOpened(self):
        return self.opened

    def write(self, frame):
        self.frames.append(frame.copy())

    def release(self):
        self.released = True
        if self.opened:
            Path(self.path).write_bytes(b"fake-mp4-output")


class ImageDetectionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.base_dir_patch = patch.object(config, "BASE_DIR", str(self.root))
        self.base_dir_patch.start()
        self.uploads_dir = self.root / "uploads"
        self.uploads_dir.mkdir()
        self.uploads_patch = patch.object(main, "UPLOADS_DIR", str(self.uploads_dir))
        self.uploads_patch.start()
        self.annotated_dir = self.uploads_dir / "annotated"
        self.annotated_dir.mkdir()
        self.annotated_patch = patch.object(
            main, "ANNOTATED_DIR", str(self.annotated_dir)
        )
        self.annotated_patch.start()
        self.annotated_video_dir = self.annotated_dir / "videos"
        self.annotated_video_patch = patch.object(
            main, "ANNOTATED_VIDEO_DIR", str(self.annotated_video_dir)
        )
        self.annotated_video_patch.start()
        self.environment_patch = patch.dict(
            os.environ,
            {"JWT_SECRET": "test-jwt-secret-that-is-at-least-32-characters"},
        )
        self.environment_patch.start()

        migrate_database(self.root / "complaints.db")
        image = np.zeros((80, 100, 3), dtype=np.uint8)
        success, encoded = cv2.imencode(".png", image)
        self.assertTrue(success)
        self.image_path = self.uploads_dir / "citizen-image.png"
        self.image_path.write_bytes(encoded.tobytes())
        self.video_path = self.uploads_dir / "citizen-video.mp4"
        self.video_path.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"x" * 24)
        with closing(sqlite3.connect(self.root / "complaints.db")) as connection:
            connection.executemany(
                """
                INSERT INTO users (id, name, email, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, 'citizen', '2026-01-01')
                """,
                [
                    (1, "Image Owner", "owner@example.com", "hash"),
                    (2, "Other Citizen", "other@example.com", "hash"),
                ],
            )
            connection.execute(
                """
                INSERT INTO uploaded_files (file_path, owner_id, created_at)
                VALUES (?, 1, '2026-01-01')
                """,
                (str(self.image_path.resolve()),),
            )
            connection.execute(
                """
                INSERT INTO uploaded_files (file_path, owner_id, created_at)
                VALUES (?, 1, '2026-01-01')
                """,
                (str(self.video_path.resolve()),),
            )
            connection.commit()
        self.tokens = {
            user_id: main.create_access_token(
                user_id,
                f"{'owner' if user_id == 1 else 'other'}@example.com",
                "citizen",
            )
            for user_id in (1, 2)
        }
        main.live_inference_limiter = vision.LiveInferenceLimiter(
            minimum_interval=0
        )
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.environment_patch.stop()
        self.annotated_video_patch.stop()
        self.annotated_patch.stop()
        self.uploads_patch.stop()
        self.base_dir_patch.stop()
        self.temp_dir.cleanup()

    def headers(self, user_id=1):
        return {"Authorization": f"Bearer {self.tokens[user_id]}"}

    def test_returns_all_detections_dimensions_thresholds_and_private_annotation(self):
        original_bytes = self.image_path.read_bytes()
        with closing(sqlite3.connect(self.root / "complaints.db")) as connection:
            connection.execute(
                """
                INSERT INTO complaints
                    (id, text, category, priority, file, status, timestamp, user_id)
                VALUES (301, 'Image evidence complaint', 'Roads', 'High', ?, 'Pending',
                        '2026-01-02', 1)
                """,
                (str(self.image_path.resolve()),),
            )
            connection.commit()
        model = FakeModel()
        with patch.object(main, "yolo_model", model):
            response = self.client.post(
                "/analyze-image",
                params={
                    "file_path": str(self.image_path),
                    "confidence": 0.65,
                    "iou": 0.4,
                },
                headers=self.headers(),
            )

        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["image_dimensions"], {"width": 100, "height": 80})
        self.assertEqual(result["complaint_id"], 301)
        self.assertTrue(result["analysis_persisted"])
        self.assertEqual(result["total_objects"], 2)
        self.assertEqual(
            [(item["class_id"], item["class_name"]) for item in result["detections"]],
            [(2, "car"), (5, "bus")],
        )
        self.assertEqual(result["detections"][0]["confidence"], 0.91)
        self.assertEqual(
            result["detections"][1]["bounding_box"],
            {"x_min": 0.0, "y_min": 1.0, "x_max": 100.0, "y_max": 80.0},
        )
        self.assertEqual(model.calls[0]["conf"], 0.65)
        self.assertEqual(model.calls[0]["iou"], 0.4)
        self.assertEqual(self.image_path.read_bytes(), original_bytes)

        annotation = result["annotated_result"]
        self.assertRegex(annotation["id"], r"^[0-9a-f]{32}$")
        annotated_path = self.annotated_dir / f"{annotation['id']}.jpg"
        self.assertTrue(annotated_path.is_file())
        self.assertTrue(
            Path(annotation["download_url"].split("/")[-1]).name == annotation["id"]
        )
        download = self.client.get(
            annotation["download_url"],
            headers=self.headers(),
        )
        self.assertEqual(download.status_code, 200, download.text)
        annotated = cv2.imdecode(
            np.frombuffer(download.content, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        self.assertEqual(annotated.shape, (80, 100, 3))
        self.assertTrue(np.all(annotated == 127))

        forbidden = self.client.get(
            annotation["download_url"],
            headers=self.headers(2),
        )
        self.assertEqual(forbidden.status_code, 404)
        with closing(sqlite3.connect(self.root / "complaints.db")) as connection:
            stored_file = connection.execute(
                "SELECT file_path, owner_id FROM uploaded_files WHERE file_path = ?",
                (str(annotated_path.resolve()),),
            ).fetchone()
            self.assertEqual(stored_file, (str(annotated_path.resolve()), 1))
            analysis = connection.execute(
                """
                SELECT complaint_id, analysis_type, model_name, model_version,
                       result_json, confidence, created_at
                FROM ai_analysis_results WHERE complaint_id = 301
                """
            ).fetchone()
        self.assertEqual(analysis[0:4], (
            301,
            "image_object_detection",
            main.YOLO_MODEL_NAME,
            f"ultralytics-{package_version('ultralytics')}",
        ))
        self.assertIsNone(analysis[5])
        self.assertTrue(analysis[6])
        metadata = json.loads(analysis[4])
        self.assertEqual(metadata["detection_count"], 2)
        self.assertEqual(metadata["confidence_scores"], [0.91, 0.72])
        self.assertEqual(metadata["annotated_image_id"], annotation["id"])
        self.assertEqual(len(metadata["detections"]), 2)

    def test_empty_detections_return_success_and_annotated_output(self):
        with patch.object(main, "yolo_model", EmptyModel()):
            response = self.client.post(
                "/analyze-image",
                params={"file_path": str(self.image_path)},
                headers=self.headers(),
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["detections"], [])
        self.assertEqual(response.json()["total_objects"], 0)
        self.assertFalse(response.json()["analysis_persisted"])
        self.assertIsNone(response.json()["complaint_id"])
        self.assertTrue(
            (self.annotated_dir / f"{response.json()['annotated_result']['id']}.jpg").is_file()
        )

    def test_analysis_history_and_annotation_roll_back_together(self):
        with closing(sqlite3.connect(self.root / "complaints.db")) as connection:
            connection.execute(
                """
                INSERT INTO complaints
                    (id, text, category, priority, file, status, timestamp, user_id)
                VALUES (302, 'Image evidence complaint', 'Roads', 'High', ?, 'Pending',
                        '2026-01-02', 1)
                """,
                (str(self.image_path.resolve()),),
            )
            connection.execute(
                """
                CREATE TRIGGER reject_image_analysis
                BEFORE INSERT ON ai_analysis_results
                BEGIN
                    SELECT RAISE(ABORT, 'forced analysis persistence failure');
                END
                """
            )
            connection.commit()

        with patch.object(main, "yolo_model", FakeModel()):
            response = self.client.post(
                "/analyze-image",
                params={"file_path": str(self.image_path)},
                headers=self.headers(),
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(list(self.annotated_dir.iterdir()), [])
        with closing(sqlite3.connect(self.root / "complaints.db")) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM uploaded_files WHERE file_path LIKE ?",
                    (str(self.annotated_dir / "%"),),
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM ai_analysis_results WHERE complaint_id = 302"
                ).fetchone()[0],
                0,
            )

    def test_invalid_image_formats_and_decode_errors_are_rejected(self):
        video_path = self.uploads_dir / "invalid-video.mp4"
        video_path.write_bytes(b"not a video")
        corrupt_path = self.uploads_dir / "corrupt.png"
        corrupt_path.write_bytes(b"\x89PNG\r\n\x1a\ncorrupt")
        mismatch_path = self.uploads_dir / "mismatched.png"
        success, jpeg = cv2.imencode(
            ".jpg", np.zeros((10, 10, 3), dtype=np.uint8)
        )
        self.assertTrue(success)
        mismatch_path.write_bytes(jpeg.tobytes())
        with closing(sqlite3.connect(self.root / "complaints.db")) as connection:
            connection.executemany(
                """
                INSERT INTO uploaded_files (file_path, owner_id, created_at)
                VALUES (?, 1, '2026-01-01')
                """,
                [
                    (str(video_path.resolve()),),
                    (str(corrupt_path.resolve()),),
                    (str(mismatch_path.resolve()),),
                ],
            )
            connection.commit()

        with patch.object(main, "yolo_model", FakeModel()):
            video_response = self.client.post(
                "/analyze-image",
                params={"file_path": str(video_path)},
                headers=self.headers(),
            )
            corrupt_response = self.client.post(
                "/analyze-image",
                params={"file_path": str(corrupt_path)},
                headers=self.headers(),
            )
            mismatch_response = self.client.post(
                "/analyze-image",
                params={"file_path": str(mismatch_path)},
                headers=self.headers(),
            )
        self.assertEqual(video_response.status_code, 400)
        self.assertEqual(corrupt_response.status_code, 400)
        self.assertEqual(mismatch_response.status_code, 400)

    def test_missing_model_authentication_and_threshold_limits(self):
        with patch.object(main, "yolo_model", None):
            missing_model = self.client.post(
                "/analyze-image",
                params={"file_path": str(self.image_path)},
                headers=self.headers(),
            )
        self.assertEqual(missing_model.status_code, 503)
        self.assertEqual(
            self.client.post(
                "/analyze-image",
                params={"file_path": str(self.image_path)},
            ).status_code,
            401,
        )
        with patch.object(main, "yolo_model", FakeModel()):
            invalid_threshold = self.client.post(
                "/analyze-image",
                params={"file_path": str(self.image_path), "confidence": 0.99},
                headers=self.headers(),
            )
        self.assertEqual(invalid_threshold.status_code, 422)

    def test_live_detection_requires_auth_and_returns_unpersisted_annotation(self):
        success, encoded = cv2.imencode(
            ".jpg", np.zeros((80, 100, 3), dtype=np.uint8)
        )
        self.assertTrue(success)
        frame = encoded.tobytes()
        with patch.object(main, "yolo_model", FakeModel()):
            unauthorized = self.client.post(
                "/live-detect",
                files={"file": ("frame.jpg", frame, "image/jpeg")},
            )
            response = self.client.post(
                "/live-detect",
                files={"file": ("untrusted-name.jpg", frame, "image/jpeg")},
                headers=self.headers(),
            )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["image_dimensions"], {"width": 100, "height": 80})
        self.assertEqual([item["class_name"] for item in result["detections"]], ["car", "bus"])
        self.assertTrue(result["annotated_frame"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(list(self.annotated_dir.iterdir()), [])
        with closing(sqlite3.connect(self.root / "complaints.db")) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM ai_analysis_results").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uploaded_files").fetchone()[0], 2)
            connection.execute("UPDATE users SET role = 'officer' WHERE id = 1")
            connection.commit()
        role_denied = self.client.post(
            "/live-detect",
            files={"file": ("frame.jpg", frame, "image/jpeg")},
            headers=self.headers(),
        )
        self.assertEqual(role_denied.status_code, 403)

    def test_live_detection_rejects_invalid_oversized_and_large_dimension_frames(self):
        with patch.object(main, "yolo_model", FakeModel()):
            invalid_type = self.client.post(
                "/live-detect",
                files={"file": ("frame.png", b"not an image", "image/png")},
                headers=self.headers(),
            )
            invalid_data = self.client.post(
                "/live-detect",
                files={"file": ("frame.jpg", b"not a jpeg", "image/jpeg")},
                headers=self.headers(),
            )
            oversized = self.client.post(
                "/live-detect",
                files={
                    "file": (
                        "frame.jpg",
                        b"x" * (vision.LIVE_FRAME_MAX_BYTES + 1),
                        "image/jpeg",
                    )
                },
                headers=self.headers(),
            )
            success, large_frame = cv2.imencode(
                ".jpg", np.zeros((481, 640, 3), dtype=np.uint8)
            )
            self.assertTrue(success)
            large_dimensions = self.client.post(
                "/live-detect",
                files={"file": ("frame.jpg", large_frame.tobytes(), "image/jpeg")},
                headers=self.headers(),
            )

        self.assertEqual(invalid_type.status_code, 415)
        self.assertEqual(invalid_data.status_code, 400)
        self.assertEqual(oversized.status_code, 413)
        self.assertEqual(large_dimensions.status_code, 400)

    def test_live_detection_limits_rate_and_releases_inference_slot_after_error(self):
        main.live_inference_limiter = vision.LiveInferenceLimiter(
            minimum_interval=30
        )
        success, encoded = cv2.imencode(
            ".jpg", np.zeros((80, 100, 3), dtype=np.uint8)
        )
        self.assertTrue(success)
        files = {"file": ("frame.jpg", encoded.tobytes(), "image/jpeg")}
        with patch.object(main, "yolo_model", FakeModel()):
            first = self.client.post(
                "/live-detect", files=files, headers=self.headers()
            )
            throttled = self.client.post(
                "/live-detect", files=files, headers=self.headers()
            )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(throttled.status_code, 429)
        self.assertEqual(throttled.headers["Retry-After"], "1")

        main.live_inference_limiter = vision.LiveInferenceLimiter(
            minimum_interval=0
        )
        with patch.object(main, "yolo_model", FailingModel()):
            failed = self.client.post(
                "/live-detect", files=files, headers=self.headers()
            )
        with patch.object(main, "yolo_model", FakeModel()):
            recovered = self.client.post(
                "/live-detect", files=files, headers=self.headers()
            )
        self.assertEqual(failed.status_code, 500)
        self.assertEqual(recovered.status_code, 200, recovered.text)

    def test_analysis_rejects_another_users_file(self):
        response = self.client.post(
            "/analyze-image",
            params={"file_path": str(self.image_path)},
            headers=self.headers(2),
        )
        self.assertEqual(response.status_code, 404)

    def test_oversized_image_and_inference_errors_are_reported(self):
        large_path = self.uploads_dir / "large.jpg"
        large_path.write_bytes(b"\xff\xd8\xff" + b"x" * (10 * 1024 * 1024))
        with closing(sqlite3.connect(self.root / "complaints.db")) as connection:
            connection.execute(
                """
                INSERT INTO uploaded_files (file_path, owner_id, created_at)
                VALUES (?, 1, '2026-01-01')
                """,
                (str(large_path.resolve()),),
            )
            connection.commit()

        with patch.object(main, "yolo_model", FakeModel()):
            oversized = self.client.post(
                "/analyze-image",
                params={"file_path": str(large_path)},
                headers=self.headers(),
            )
        self.assertEqual(oversized.status_code, 413)

        with patch.object(main, "yolo_model", FailingModel()):
            inference_error = self.client.post(
                "/analyze-image",
                params={"file_path": str(self.image_path)},
                headers=self.headers(),
            )
        self.assertEqual(inference_error.status_code, 500)
        self.assertEqual(inference_error.json()["detail"], "Image analysis failed")

    def test_short_video_sampling_aggregation_annotation_and_history(self):
        frames = [
            np.full((40, 60, 3), value, dtype=np.uint8)
            for value in (10, 20, 30, 40, 50)
        ]
        capture = FakeVideoCapture(frames, fps=10, declared_frames=5)
        FakeVideoWriter.instances.clear()
        with closing(sqlite3.connect(self.root / "complaints.db")) as connection:
            connection.execute(
                """
                INSERT INTO complaints
                    (id, text, category, priority, file, status, timestamp, user_id)
                VALUES (401, 'Video evidence complaint', 'Roads', 'High', ?, 'Pending',
                        '2026-01-02', 1)
                """,
                (str(self.video_path.resolve()),),
            )
            connection.commit()

        with (
            patch.object(vision.cv2, "VideoCapture", return_value=capture),
            patch.object(vision.cv2, "VideoWriter", FakeVideoWriter),
            patch.object(vision.cv2, "VideoWriter_fourcc", return_value=1),
            patch.object(main, "yolo_model", FakeModel()),
        ):
            response = self.client.post(
                "/analyze-video",
                params={
                    "file_path": str(self.video_path),
                    "frame_interval": 2,
                    "include_frame_detections": "true",
                    "annotate_video": "true",
                },
                headers=self.headers(),
            )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["processing_status"], "completed")
        self.assertEqual(body["frames_processed"], 5)
        self.assertEqual(body["frames_sampled"], 3)
        self.assertEqual(body["total_detections"], 6)
        self.assertEqual(
            body["detection_counts"],
            [
                {"class_id": 2, "class_name": "car", "count": 3},
                {"class_id": 5, "class_name": "bus", "count": 3},
            ],
        )
        self.assertEqual(
            [item["frame_index"] for item in body["frame_detections"]],
            [0, 2, 4],
        )
        self.assertEqual(body["complaint_id"], 401)
        self.assertTrue(body["analysis_persisted"])
        self.assertTrue(capture.released)

        annotated = body["annotated_video"]
        self.assertRegex(annotated["id"], r"^[0-9a-f]{32}$")
        video_output = self.annotated_dir / "videos" / f"{annotated['id']}.mp4"
        self.assertTrue(video_output.is_file())
        self.assertEqual(len(FakeVideoWriter.instances), 1)
        self.assertEqual(len(FakeVideoWriter.instances[0].frames), 5)
        self.assertTrue(FakeVideoWriter.instances[0].released)
        self.assertEqual(list(self.annotated_video_dir.glob(".video-analysis-*")), [])
        download = self.client.get(
            annotated["download_url"],
            headers=self.headers(),
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, b"fake-mp4-output")
        self.assertEqual(
            self.client.get(
                annotated["download_url"],
                headers=self.headers(2),
            ).status_code,
            404,
        )
        with closing(sqlite3.connect(self.root / "complaints.db")) as connection:
            saved = connection.execute(
                """
                SELECT file_path, owner_id FROM uploaded_files
                WHERE file_path = ?
                """,
                (str(video_output.resolve()),),
            ).fetchone()
            history = connection.execute(
                """
                SELECT analysis_type, model_name, model_version, result_json,
                       created_at
                FROM ai_analysis_results WHERE complaint_id = 401
                """
            ).fetchone()
        self.assertEqual(saved, (str(video_output.resolve()), 1))
        self.assertEqual(history[0:3], (
            "video_object_detection",
            main.YOLO_MODEL_NAME,
            main.YOLO_MODEL_VERSION,
        ))
        history_metadata = json.loads(history[3])
        self.assertEqual(history_metadata["detection_count"], 6)
        self.assertEqual(
            history_metadata["confidence_scores"],
            [0.91, 0.72] * 3,
        )
        self.assertEqual(history_metadata["annotated_video_id"], annotated["id"])
        self.assertTrue(history[4])

    def test_video_no_detections_and_without_annotation(self):
        capture = FakeVideoCapture(
            [np.zeros((40, 60, 3), dtype=np.uint8) for _ in range(4)],
            fps=10,
            declared_frames=4,
        )
        with (
            patch.object(vision.cv2, "VideoCapture", return_value=capture),
            patch.object(main, "yolo_model", EmptyModel()),
        ):
            response = self.client.post(
                "/analyze-video",
                params={"file_path": str(self.video_path), "frame_interval": 2},
                headers=self.headers(),
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["detection_counts"], [])
        self.assertEqual(response.json()["total_detections"], 0)
        self.assertIsNone(response.json()["annotated_video"])
        self.assertEqual(list((self.annotated_dir / "videos").glob("*.mp4")), [])

    def test_invalid_unsupported_video_and_frame_sampling_limit(self):
        bad_path = self.uploads_dir / "bad-video.mp4"
        bad_path.write_bytes(b"not an mp4 container")
        unsupported_path = self.uploads_dir / "unsupported.mp4"
        unsupported_path.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"x" * 24)
        with closing(sqlite3.connect(self.root / "complaints.db")) as connection:
            connection.executemany(
                """
                INSERT INTO uploaded_files (file_path, owner_id, created_at)
                VALUES (?, 1, '2026-01-01')
                """,
                [
                    (str(bad_path.resolve()),),
                    (str(unsupported_path.resolve()),),
                ],
            )
            connection.commit()

        failed_capture = FakeVideoCapture(str(unsupported_path), opened=False)
        with (
            patch.object(vision.cv2, "VideoCapture", return_value=failed_capture),
            patch.object(main, "yolo_model", FakeModel()),
        ):
            invalid = self.client.post(
                "/analyze-video",
                params={"file_path": str(bad_path)},
                headers=self.headers(),
            )
            unsupported = self.client.post(
                "/analyze-video",
                params={"file_path": str(unsupported_path)},
                headers=self.headers(),
            )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(unsupported.status_code, 400)
        self.assertTrue(failed_capture.released)

        long_video_capture = FakeVideoCapture(
            str(self.video_path),
            fps=10,
            declared_frames=1201,
        )
        with (
            patch.object(vision.cv2, "VideoCapture", return_value=long_video_capture),
            patch.object(main, "yolo_model", FakeModel()),
        ):
            too_long = self.client.post(
                "/analyze-video",
                params={"file_path": str(self.video_path)},
                headers=self.headers(),
            )
        self.assertEqual(too_long.status_code, 413)
        self.assertTrue(long_video_capture.released)

        excessive_capture = FakeVideoCapture(
            str(self.video_path),
            fps=10,
            declared_frames=MAX_VIDEO_SAMPLED_FRAMES + 1,
        )
        with (
            patch.object(vision.cv2, "VideoCapture", return_value=excessive_capture),
            patch.object(main, "yolo_model", FakeModel()),
        ):
            too_many_frames = self.client.post(
                "/analyze-video",
                params={
                    "file_path": str(self.video_path),
                    "frame_interval": 1,
                },
                headers=self.headers(),
            )
        self.assertEqual(too_many_frames.status_code, 413)
        self.assertTrue(excessive_capture.released)

    def test_video_access_is_limited_to_the_upload_owner(self):
        with patch.object(main, "yolo_model", FakeModel()):
            forbidden = self.client.post(
                "/analyze-video",
                params={"file_path": str(self.video_path)},
                headers=self.headers(2),
            )
        self.assertEqual(forbidden.status_code, 404)
        self.assertEqual(
            self.client.post(
                "/analyze-video",
                params={"file_path": str(self.video_path)},
            ).status_code,
            401,
        )

    def test_video_inference_and_database_failures_remove_temporary_outputs(self):
        capture = FakeVideoCapture(
            str(self.video_path),
            [np.zeros((40, 60, 3), dtype=np.uint8) for _ in range(3)],
            fps=10,
            declared_frames=3,
        )
        FakeVideoWriter.instances.clear()
        with (
            patch.object(vision.cv2, "VideoCapture", return_value=capture),
            patch.object(vision.cv2, "VideoWriter", FakeVideoWriter),
            patch.object(vision.cv2, "VideoWriter_fourcc", return_value=1),
            patch.object(main, "yolo_model", FailingModel()),
        ):
            failed_inference = self.client.post(
                "/analyze-video",
                params={
                    "file_path": str(self.video_path),
                    "frame_interval": 1,
                    "annotate_video": "true",
                },
                headers=self.headers(),
            )
        self.assertEqual(failed_inference.status_code, 500)
        self.assertEqual(list((self.annotated_dir / "videos").iterdir()), [])

        with closing(sqlite3.connect(self.root / "complaints.db")) as connection:
            connection.execute(
                """
                INSERT INTO complaints
                    (id, text, category, priority, file, status, timestamp, user_id)
                VALUES (402, 'Video evidence complaint', 'Roads', 'High', ?, 'Pending',
                        '2026-01-02', 1)
                """,
                (str(self.video_path.resolve()),),
            )
            connection.execute(
                """
                CREATE TRIGGER reject_video_analysis
                BEFORE INSERT ON ai_analysis_results
                BEGIN
                    SELECT RAISE(ABORT, 'forced video persistence failure');
                END
                """
            )
            connection.commit()
        capture = FakeVideoCapture(
            str(self.video_path),
            [np.zeros((40, 60, 3), dtype=np.uint8) for _ in range(3)],
            fps=10,
            declared_frames=3,
        )
        with (
            patch.object(vision.cv2, "VideoCapture", return_value=capture),
            patch.object(vision.cv2, "VideoWriter", FakeVideoWriter),
            patch.object(vision.cv2, "VideoWriter_fourcc", return_value=1),
            patch.object(main, "yolo_model", FakeModel()),
        ):
            failed_persistence = self.client.post(
                "/analyze-video",
                params={
                    "file_path": str(self.video_path),
                    "frame_interval": 1,
                    "annotate_video": "true",
                },
                headers=self.headers(),
            )
        self.assertEqual(failed_persistence.status_code, 500)
        self.assertEqual(list((self.annotated_dir / "videos").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
