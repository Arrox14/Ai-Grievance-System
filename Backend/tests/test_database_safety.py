import asyncio
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile
from app.core import config
from app.database import connect_db, db_connection, db_transaction
from app.services.files import save_upload


class DatabaseSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir_patch = patch.object(config, "BASE_DIR", self.temp_dir.name)
        self.base_dir_patch.start()
        with db_transaction() as connection:
            connection.execute(
                "CREATE TABLE entries (id INTEGER PRIMARY KEY, value TEXT UNIQUE)"
            )

    def tearDown(self):
        self.base_dir_patch.stop()
        self.temp_dir.cleanup()

    def test_database_connections_are_isolated_and_enable_foreign_keys(self):
        first = connect_db()
        second = connect_db()
        try:
            self.assertIsNot(first, second)
            self.assertEqual(first.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(second.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        finally:
            first.close()
            second.close()

    def test_transaction_rolls_back_all_writes_on_failure(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with db_transaction() as connection:
                connection.execute("INSERT INTO entries (value) VALUES (?)", ("first",))
                connection.execute("INSERT INTO entries (value) VALUES (?)", ("first",))

        with db_connection() as connection:
            count = connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        self.assertEqual(count, 0)

    def test_file_write_failure_cleans_temporary_and_final_files(self):
        upload_dir = Path(self.temp_dir.name) / "uploads"
        upload = UploadFile(
            filename="evidence.jpg",
            file=io.BytesIO(b"\xff\xd8\xffvalid"),
            headers=Headers({"content-type": "image/jpeg"}),
        )
        with patch("app.services.files.os.replace", side_effect=OSError("write failed")):
            with self.assertRaises(OSError):
                asyncio.run(save_upload(upload, upload.filename, str(upload_dir)))
        self.assertEqual(list(upload_dir.iterdir()), [])

    def test_invalid_upload_metadata_does_not_create_file(self):
        upload_dir = Path(self.temp_dir.name) / "uploads"
        upload = UploadFile(
            filename="../../unsafe.exe",
            file=io.BytesIO(b"payload"),
            headers=Headers({"content-type": "application/octet-stream"}),
        )
        with self.assertRaises(HTTPException) as error:
            asyncio.run(save_upload(upload, upload.filename, str(upload_dir)))
        self.assertEqual(error.exception.status_code, 400)
        self.assertFalse(upload_dir.exists())


if __name__ == "__main__":
    unittest.main()
