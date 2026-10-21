import os
import re


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP_DATA_DIR = os.environ.get(
    "APP_DATA_DIR",
    os.path.join(BASE_DIR, "data"),
)
UPLOADS_DIR = os.path.join(APP_DATA_DIR, "uploads")
DATABASE_DIR = os.path.join(BASE_DIR, "database")

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def load_backend_environment():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.isfile(env_path):
        return

    with open(env_path, encoding="utf-8") as env_file:
        for line in env_file:
            key, separator, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if separator and key and not key.startswith("#"):
                os.environ.setdefault(key, value)
