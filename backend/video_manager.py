import cv2
import numpy as np
import time
import os
import threading
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from werkzeug.utils import secure_filename
from config import BASE_DIR

ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv'}
MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB

# Block internal IP ranges for SSRF protection on RTSP
BLOCKED_RTSP_HOSTS = {'127.0.0.1', 'localhost', '0.0.0.0', '169.254.169.254'}

class VideoSourceManager:
    def __init__(self):
        self.mode = "SIMULATION"  # "UPLOAD", "WEBCAM", "RTSP", "SIMULATION"
        self.source_path = ""
        self.cap: Optional[cv2.VideoCapture] = None
        self.lock = threading.Lock()
        
        # Health & Watchdog Metrics
        self.health_status = "HEALTHY"  # HEALTHY, FROZEN, DISCONNECTED, RECONNECTING, SIMULATED
        self.last_frame_time = time.time()
        self.last_frame_hash = None
        self.frozen_counter = 0
        self.frame_index = 0
        self.measured_fps = 0.0
        self._fps_counter = 0
        self._fps_timer = time.time()
        
        # Threaded acquisition
        self.running = True
        self.current_frame = None
        self.worker_thread = None
        
        # Procedural simulation generator
        self.sim_vehicles = []
        self._init_simulation_state()
        
        # Set default to sample uploaded traffic if available, else simulation
        sample_path = BASE_DIR / "backend" / "uploads" / "sample_traffic.mp4"
        if sample_path.exists():
            self.set_source("UPLOAD", str(sample_path))
        else:
            self.set_source("SIMULATION", "")

    def _init_simulation_state(self):
        """Initializes state for the separate procedural simulator mode."""
        lanes = [140, 260, 380, 500]
        types = [
            ("Car", (45, 80), (220, 160, 50), 3.0),
            ("Bus", (60, 140), (40, 180, 40), 2.2),
            ("Truck", (60, 120), (50, 100, 220), 2.0),
            ("Motorcycle", (25, 45), (180, 50, 200), 3.8),
            ("Auto-Rickshaw", (40, 65), (20, 200, 220), 2.8)
        ]
        self.sim_vehicles = []
        for i in range(8):
            lane_x = lanes[i % len(lanes)]
            vtype, size, color, speed = types[i % len(types)]
            self.sim_vehicles.append({
                "x": lane_x - size[0] // 2,
                "y": np.random.randint(20, 420),
                "w": size[0],
                "h": size[1],
                "color": color,
                "speed": speed + np.random.uniform(-0.4, 0.6),
                "type": vtype,
                "wrong_way": (i == 5)
            })

    def set_source(self, mode: str, path_or_index: str) -> Dict[str, Any]:
        """Switches video source safely with validation."""
        mode = mode.upper()
        if mode not in ("UPLOAD", "WEBCAM", "RTSP", "SIMULATION"):
            return {"success": False, "error": f"Invalid source mode: {mode}"}

        with self.lock:
            # Release previous capture if open
            if self.cap is not None:
                self.cap.release()
                self.cap = None

            self.mode = mode
            self.source_path = path_or_index
            self.frame_index = 0
            self.frozen_counter = 0

            if mode == "SIMULATION":
                self.health_status = "SIMULATED"
                print("[VIDEO MANAGER] Switched to procedural SIMULATION mode.")
                return {"success": True, "mode": self.mode, "status": self.health_status}

            elif mode == "UPLOAD":
                resolved_path = Path(path_or_index)
                if not resolved_path.is_absolute():
                    # Try resolving relative to BASE_DIR and relative to cwd
                    cand1 = BASE_DIR / path_or_index
                    cand2 = Path.cwd() / path_or_index
                    if cand1.exists():
                        resolved_path = cand1
                    elif cand2.exists():
                        resolved_path = cand2

                if not resolved_path.exists():
                    self.health_status = "DISCONNECTED"
                    return {"success": False, "error": f"Video file does not exist on disk: {path_or_index}"}
                self.cap = cv2.VideoCapture(str(resolved_path))
                if not self.cap.isOpened():
                    self.health_status = "DISCONNECTED"
                    return {"success": False, "error": "Failed to open video file."}
                self.health_status = "HEALTHY"
                self.source_path = str(resolved_path)
                print(f"[VIDEO MANAGER] Playing video file: {resolved_path}")
                return {"success": True, "mode": self.mode, "source": resolved_path.name, "status": self.health_status}

            elif mode == "WEBCAM":
                try:
                    idx = int(path_or_index) if str(path_or_index).isdigit() else 0
                    self.cap = cv2.VideoCapture(idx)
                    if not self.cap.isOpened():
                        self.health_status = "DISCONNECTED"
                        return {"success": False, "error": f"Webcam index {idx} not accessible."}
                    self.health_status = "HEALTHY"
                    print(f"[VIDEO MANAGER] Connected to webcam #{idx}")
                    return {"success": True, "mode": self.mode, "source": f"Webcam #{idx}", "status": self.health_status}
                except Exception as e:
                    self.health_status = "DISCONNECTED"
                    return {"success": False, "error": str(e)}

            elif mode == "RTSP":
                # Validate RTSP host for SSRF protection
                for blocked in BLOCKED_RTSP_HOSTS:
                    if blocked in path_or_index:
                        return {"success": False, "error": f"Access to internal network host {blocked} is forbidden."}
                
                self.cap = cv2.VideoCapture(path_or_index)
                if not self.cap.isOpened():
                    self.health_status = "DISCONNECTED"
                    return {"success": False, "error": "Unable to connect to RTSP stream."}
                self.health_status = "HEALTHY"
                print(f"[VIDEO MANAGER] Connected to RTSP camera stream.")
                return {"success": True, "mode": self.mode, "source": "RTSP Stream", "status": self.health_status}

        return {"success": False, "error": "Unknown configuration."}

    def read_frame(self, is_authenticated: bool = True) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reads next frame and performs stream health analysis."""
        with self.lock:
            metadata = {
                "mode": self.mode,
                "health": self.health_status,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "frame_index": self.frame_index,
                "fps": self.measured_fps,
                "is_simulation": (self.mode == "SIMULATION"),
                "is_authenticated": is_authenticated
            }

            # If user is not authenticated, do not burn CPU playing/processing video
            if not is_authenticated:
                frame = self._render_standby_frame()
                metadata["health"] = "STANDBY"
                return frame, metadata

            if self.mode == "SIMULATION" or self.cap is None:
                frame = self._render_simulation_frame()
                self.health_status = "SIMULATED"
                metadata["health"] = self.health_status
                return frame, metadata

            # Read from real capture device or file
            ret, raw_frame = self.cap.read()
            if not ret or raw_frame is None:
                # If reading from file, loop back to start
                if self.mode == "UPLOAD" and self.cap is not None:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, raw_frame = self.cap.read()

                if not ret or raw_frame is None:
                    self.health_status = "DISCONNECTED"
                    metadata["health"] = self.health_status
                    frame = self._render_disconnected_fallback()
                    return frame, metadata

            # Resize to standard 640x480 for consistent processing
            frame = cv2.resize(raw_frame, (640, 480))
            self.frame_index += 1

            # Check for Frozen Stream
            self._check_frozen_health(frame)
            metadata["health"] = self.health_status

            # Calculate FPS
            self._fps_counter += 1
            now = time.time()
            if now - self._fps_timer >= 1.0:
                self.measured_fps = round(self._fps_counter / (now - self._fps_timer), 1)
                self._fps_counter = 0
                self._fps_timer = now
            metadata["fps"] = self.measured_fps

            return frame, metadata

    def _render_standby_frame(self) -> np.ndarray:
        """Standby display when no operator is authenticated."""
        frame = np.full((480, 640, 3), 15, dtype=np.uint8)
        cv2.rectangle(frame, (50, 130), (590, 340), (24, 30, 44), -1)
        cv2.rectangle(frame, (50, 130), (590, 340), (99, 102, 241), 2)
        cv2.putText(frame, "OPERATIONAL STANDBY - AUTH REQUIRED", (75, 200),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(frame, "Sign in or create an account to activate live AI pipeline", (80, 245),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (148, 163, 184), 1)
        cv2.putText(frame, "AI Intelligent Traffic Management System", (140, 290),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (129, 140, 248), 1)
        return frame

    def _check_frozen_health(self, frame: np.ndarray):
        """Detects if incoming video stream is stuck/frozen."""
        small_gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (64, 48))
        if self.last_frame_hash is not None:
            # Calculate pixel mean squared difference
            mse = np.mean((small_gray.astype("float") - self.last_frame_hash.astype("float")) ** 2)
            if mse < 0.2:
                self.frozen_counter += 1
                if self.frozen_counter > 50:  # ~2.5 seconds of static frames
                    self.health_status = "FROZEN"
            else:
                self.frozen_counter = 0
                if self.health_status == "FROZEN":
                    self.health_status = "HEALTHY"
        self.last_frame_hash = small_gray

    def _render_simulation_frame(self) -> np.ndarray:
        """Renders procedural traffic in simulation mode."""
        frame = np.full((480, 640, 3), 40, dtype=np.uint8)
        cv2.rectangle(frame, (80, 0), (560, 480), (55, 55, 55), -1)
        cv2.line(frame, (80, 0), (80, 480), (240, 240, 240), 3)
        cv2.line(frame, (560, 0), (560, 480), (240, 240, 240), 3)

        for x in (200, 320, 440):
            for y in range(0, 480, 40):
                cv2.line(frame, (x, y), (x, y + 20), (200, 200, 200), 2)

        for v in self.sim_vehicles:
            if v["wrong_way"]:
                v["y"] -= int(v["speed"])
                if v["y"] < -v["h"]:
                    v["y"] = 480 + 20
            else:
                v["y"] += int(v["speed"])
                if v["y"] > 480:
                    v["y"] = -v["h"] - np.random.randint(20, 80)

            x, y, w, h = int(v["x"]), int(v["y"]), int(v["w"]), int(v["h"])
            cv2.rectangle(frame, (x, y), (x + w, y + h), v["color"], -1)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), 1)

        # Prominent watermark stating simulation mode
        cv2.rectangle(frame, (0, 0), (640, 28), (0, 0, 180), -1)
        cv2.putText(frame, "[DEMO ONLY] SIMULATION MODE ACTIVE - NOT REAL CAMERA FEED",
                    (45, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        return frame

    def _render_disconnected_fallback(self) -> np.ndarray:
        """Fallback visual when a camera or stream is disconnected."""
        frame = np.full((480, 640, 3), 20, dtype=np.uint8)
        cv2.putText(frame, "STREAM DISCONNECTED / SIGNAL LOST", (90, 230),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.putText(frame, f"Source: {self.source_path or self.mode}", (160, 270),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        return frame

def validate_video_upload(file_storage, dest_folder: Path) -> Tuple[bool, str]:
    """Validates uploaded video file for magic bytes, extension, size and OpenCV decode."""
    filename = secure_filename(file_storage.filename)
    if not filename:
        return False, "Invalid filename."

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File extension '{ext}' not allowed. Must be MP4, AVI, or MOV."

    dest_path = dest_folder / filename
    file_storage.save(str(dest_path))

    size = os.path.getsize(str(dest_path))
    if size > MAX_UPLOAD_SIZE_BYTES:
        os.remove(str(dest_path))
        return False, f"File size exceeds 100MB limit ({size // (1024*1024)}MB)."

    # Verify video decoding with OpenCV
    test_cap = cv2.VideoCapture(str(dest_path))
    opened = test_cap.isOpened()
    ret, test_frame = test_cap.read() if opened else (False, None)
    test_cap.release()

    if not opened or not ret or test_frame is None:
        # Fallback binary header check
        try:
            with open(str(dest_path), 'rb') as f:
                header = f.read(256)
                valid_magic = any(sig in header for sig in [b'ftyp', b'moov', b'mdat', b'RIFF', b'\x1aE\xdf\xa3', b'wide'])
                if not valid_magic:
                    os.remove(str(dest_path))
                    return False, "Uploaded file failed video verification (unsupported codec or corrupt video)."
        except Exception as e:
            if dest_path.exists():
                os.remove(str(dest_path))
            return False, f"Error validating video file: {e}"

    return True, str(dest_path)

video_source_manager = VideoSourceManager()
