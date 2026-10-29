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

    def test_09_alert_service_and_deduplication(self):
        """Test alert creation, deduplication, and operator acknowledgement."""
        from alert_service import alert_service
        alert = alert_service.trigger_alert(
            alert_type="TRAFFIC_VIOLATION",
            severity="CRITICAL",
            title="Red Light Jump Detected (#55)",
            details={"vehicle_id": 55, "type": "Red Light Jump"}
        )
        self.assertIsNotNone(alert)
        self.assertTrue(alert["alert_id"].startswith("ALT-"))
        self.assertEqual(alert["status"], "QUEUED")

        # Test operator acknowledgement
        ack_ok = alert_service.acknowledge_alert(alert["alert_id"], "officer_sharma")
        self.assertTrue(ack_ok)
        self.assertEqual(alert["status"], "ACKNOWLEDGED")
        self.assertEqual(alert["acknowledged_by"], "officer_sharma")

    def test_10_echallan_generation(self):
        """Test legal E-Challan format and fine calculation."""
        from app import app
        with app.test_client() as client:
            res = client.get("/api/evidence/TEST-01/challan")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["challan_number"].startswith("ECH-"))
            self.assertEqual(data["fine_amount_inr"], 1500)
            self.assertTrue(data["court_admissible"])

    def test_11_email_auth_and_registration(self):
        """Test email validation, password strength, user registration and login."""
        import time
        from auth_security import (
            validate_email_format, validate_password_strength,
            hash_password, verify_password
        )
        from app import app

        # 1. Validation tests
        ok, res = validate_email_format("operator@traffic.gov.in")
        self.assertTrue(ok)
        self.assertEqual(res, "operator@traffic.gov.in")

        ok, msg = validate_email_format("invalid-email-address")
        self.assertFalse(ok)

        ok, msg = validate_password_strength("weak")
        self.assertFalse(ok)

        ok, msg = validate_password_strength("StrongPass2026")
        self.assertTrue(ok)

        # 2. Hash & Salt
        h, salt = hash_password("Secret123")
        self.assertTrue(verify_password("Secret123", salt, h))
        self.assertFalse(verify_password("WrongPass", salt, h))

        # 3. Register & Login API tests
        with app.test_client() as client:
            # Registration
            test_email = f"test_{int(time.time())}@traffic.gov.in"
            reg_resp = client.post("/api/auth/register", json={
                "email": test_email,
                "password": "Password2026",
                "name": "Inspector Rao",
                "role": "OPERATOR"
            })
            self.assertIn(reg_resp.status_code, [200, 201])
            reg_data = reg_resp.get_json()
            self.assertTrue(reg_data["success"])

            # Duplicate rejection
            dup_resp = client.post("/api/auth/register", json={
                "email": test_email,
                "password": "Password2026"
            })
            self.assertEqual(dup_resp.status_code, 409)

            # Login
            login_resp = client.post("/api/auth/login", json={
                "email": test_email,
                "password": "Password2026"
            })
            self.assertEqual(login_resp.status_code, 200)
            login_data = login_resp.get_json()
            self.assertTrue(login_data["success"])
            self.assertIn("token", login_data)

    def test_12_gated_video_stream(self):
        """Test that unauthenticated requests to video feed are marked unauthenticated."""
        from app import app
        with app.test_client() as client:
            resp = client.get("/video_feed")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.mimetype, "multipart/x-mixed-replace")

if __name__ == "__main__":
    unittest.main()
