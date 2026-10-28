"""
AI-Powered Traffic Management System
Root Launcher Script
"""

import sys
import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"

def main():
    print("=" * 60)
    print("[SYSTEM] Launching AI-Powered Traffic Management System...")
    print("=" * 60)
    print(" - Computer Vision Engine: OpenCV DNN + YOLOv5n")
    print(" - Dynamic Signal Controller: Webster Heuristic")
    print(" - Database: MongoDB Atlas (configurable via .env)")
    print(" - Dashboard UI: React + Chart.js")
    print("-" * 60)
    print(" Dashboard URL:     http://localhost:5000/")
    print(" Live Video Stream: http://localhost:5000/video_feed")
    print(" Status API:        http://localhost:5000/api/status")
    print("=" * 60)

    # Launch Flask application
    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))
    from app import app
    from config import FLASK_HOST, FLASK_PORT, DEBUG

    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=DEBUG, threaded=True)

if __name__ == "__main__":
    main()
