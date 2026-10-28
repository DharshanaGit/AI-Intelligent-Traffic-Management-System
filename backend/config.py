import os
from pathlib import Path
from dotenv import load_dotenv

# Locate and load root .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# MongoDB Settings
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("DB_NAME", "traffic_management_db")

# Server Settings
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

# Storage Paths
STATIC_DIR = BASE_DIR / "backend" / "static"
VIOLATIONS_DIR = STATIC_DIR / "violations"
MODEL_PATH = BASE_DIR / "backend" / "models" / "yolov5n.onnx"

VIOLATIONS_DIR.mkdir(parents=True, exist_ok=True)
