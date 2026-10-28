import unittest
import os
import sys
import numpy as np
from pathlib import Path

# Set backend in path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from video_manager import video_source_manager, validate_video_upload
from calibration_engine import calibration_engine
from anpr_evidence import anpr_evidence_manager
from signal_decision_support import signal_decision_support
from auth_security import security_manager
from db_client import db_manager
from traffic_engine import traffic_engine

class TestAITrafficSystem(unittest.TestCase):

    def test_01_video_ingestion_and_health(self):
        """Test video reading, resolution and health metadata."""
        frame, meta = video_source_manager.read_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (480, 640, 3))
        self.assertIn(meta["health"], ["HEALTHY", "SIMULATED", "FROZEN"])
        self.assertIn(meta["mode"], ["UPLOAD", "WEBCAM", "RTSP", "SIMULATION"])

    def test_02_frozen_stream_watchdog(self):
        """Test that static identical frames trigger frozen stream detection."""
        static_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Push 60 identical frames
        for _ in range(60):
            video_source_manager._check_frozen_health(static_frame)
        self.assertEqual(video_source_manager.health_status, "FROZEN")

    def test_03_ai_detection_and_inference(self):
        """Test YOLOv5n ONNX inference on sample frame."""
        sample_frame = np.full((480, 640, 3), 120, dtype=np.uint8)
        boxes, confs, classes = traffic_engine.run_detection(sample_frame)
        self.assertIsInstance(boxes, list)
        self.assertIsInstance(confs, list)
        self.assertIsInstance(classes, list)

    def test_04_perspective_calibration_speed(self):
        """Test homography metric distance and speed estimation."""
        pt1 = (320, 250)
        pt2 = (320, 350)
        dt = 0.5  # 0.5 seconds
        speed = calibration_engine.calculate_speed_kmh(pt1, pt2, dt)
        self.assertIsNotNone(speed)
        self.assertGreater(speed, 0.0)

    def test_05_anpr_and_sha256_evidence_seal(self):
        """Test cryptographic SHA-256 seal and evidence record integrity."""
        dummy_crop = np.zeros((100, 150, 3), dtype=np.uint8)
        rec = anpr_evidence_manager.seal_and_store_evidence(
            frame=dummy_crop,
            vid=99,
            vtype="Red Light Jump",
            vehicle_type="Auto-Rickshaw",
            bbox=[10, 10, 80, 60],
            speed=48.5
        )
        self.assertTrue(rec["evidence_id"].startswith("EVD-"))
        self.assertEqual(len(rec["sha256_hash"]), 64)
        self.assertEqual(rec["status"], "PENDING_REVIEW")
        self.assertEqual(rec["vehicle_class"], "Auto-Rickshaw")

    def test_06_adaptive_signal_decision_support(self):
        """Test Webster formula bounds and PCU calculation."""
        # Test Indian PCU
        counts = {"Car": 3, "Motorcycle": 4, "Auto-Rickshaw": 2, "Bus": 1, "Truck": 0}
        pcu = signal_decision_support.compute_lane_pcu(counts)
        # 3*1.0 + 4*0.5 + 2*0.8 + 1*2.5 = 3 + 2 + 1.6 + 2.5 = 9.1
        self.assertAlmostEqual(pcu, 9.1, places=1)

        # Test timing clamps
        decision = signal_decision_support.calculate_adaptive_timing(pcu)
        green = decision["recommended_green_seconds"]
        self.assertGreaterEqual(green, signal_decision_support.min_green)
        self.assertLessEqual(green, signal_decision_support.max_green)
        self.assertTrue(decision["safety_interlock_engaged"])

    def test_07_rbac_and_jwt_security(self):
        """Test authentication tokens, RBAC roles and verification."""
        token_admin = security_manager.generate_token("admin", "ADMIN")
        data = security_manager.verify_token(token_admin)
        self.assertIsNotNone(data)
        self.assertEqual(data["sub"], "admin")
        self.assertEqual(data["role"], "ADMIN")

        # Test invalid token rejection
        self.assertIsNone(security_manager.verify_token("tampered.token.value"))

    def test_08_database_offline_resilience(self):
        """Test that violations are queued to offline spool without crashing."""
        dummy_rec = {
            "evidence_id": "TEST-01",
            "sha256_hash": "a" * 64,
            "vehicle_id": 101,
            "violation_type": "Overspeeding",
            "timestamp": "2026-10-29T00:00:00Z"
        }
        res = db_manager.log_violation(dummy_rec)
        self.assertIsNotNone(res)
        self.assertTrue(len(db_manager.local_violations) > 0)

if __name__ == "__main__":
    unittest.main()
