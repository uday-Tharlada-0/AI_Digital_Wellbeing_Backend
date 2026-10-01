import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_DIR = os.path.join(BASE_DIR, "models_store")
DB_PATH = os.path.join(DATA_DIR, "scolect.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# Local: SQLite
# Production (Render): PostgreSQL through DATABASE_URL
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Compatibility with older postgres:// URLs
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql://",
            1
        )
else:
    DATABASE_URL = f"sqlite:///{DB_PATH}"


class Config:
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "change-this-development-secret"
    )

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

    DATA_DIR = DATA_DIR
    MODEL_DIR = MODEL_DIR
    DB_PATH = DB_PATH