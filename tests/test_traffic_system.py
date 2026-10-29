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
        """Test legal E-Challan format and fine calculation with authentication."""
        from app import app
        from auth_security import security_manager
        token = security_manager.generate_token("officer@traffic.gov.in", "OPERATOR", "Officer")
        headers = {"Authorization": f"Bearer {token}"}

        with app.test_client() as client:
            # Unauthenticated request must be rejected
            unauth_res = client.get("/api/evidence/TEST-01/challan")
            self.assertEqual(unauth_res.status_code, 401)

            # Authenticated request succeeds
            res = client.get("/api/evidence/TEST-01/challan", headers=headers)
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["challan_number"].startswith("ECH-"))
            self.assertEqual(data["fine_amount_inr"], 1500)
            self.assertTrue(data["court_admissible"])

    def test_11_email_auth_and_registration(self):
        """Test email validation, uppercase rejection, password strength, registration and login."""
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

        # Uppercase letters in email must be rejected
        ok_caps, msg_caps = validate_email_format("Admin@Traffic.Gov.In")
        self.assertFalse(ok_caps)
        self.assertIn("Uppercase", msg_caps)

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
            # Test uppercase rejection in API
            caps_resp = client.post("/api/auth/register", json={
                "email": "User@Traffic.Gov.In",
                "password": "Password2026"
            })
            self.assertEqual(caps_resp.status_code, 400)
            self.assertIn("Uppercase", caps_resp.get_json()["error"])

            # Test admin self-registration without authorization blocked (403)
            admin_reg_resp = client.post("/api/auth/register", json={
                "email": "hacker_admin@traffic.gov.in",
                "password": "Password2026",
                "role": "ADMIN"
            })
            self.assertEqual(admin_reg_resp.status_code, 403)

            # Legitimate operator registration
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
        """Test that unauthenticated requests to video feed are rejected (401) and authenticated pass (200)."""
        from app import app
        from auth_security import security_manager
        valid_token = security_manager.generate_token("officer@traffic.gov.in", "OPERATOR")

        with app.test_client() as client:
            # Unauthenticated request rejected with 401
            resp_unauth = client.get("/video_feed")
            self.assertEqual(resp_unauth.status_code, 401)

            # Authenticated stream request accepted with 200
            resp_auth = client.get(f"/video_feed?token={valid_token}")
            self.assertEqual(resp_auth.status_code, 200)
            self.assertEqual(resp_auth.mimetype, "multipart/x-mixed-replace")

    def test_13_token_revocation_and_unauthenticated_rejection(self):
        """Test strict auth: 401 on unauthenticated data endpoints and token revocation on logout."""
        from app import app
        from auth_security import security_manager
        token = security_manager.generate_token("officer@traffic.gov.in", "OPERATOR")
        auth_headers = {"Authorization": f"Bearer {token}"}

        with app.test_client() as client:
            # 1. Unauthenticated requests must return 401
            self.assertEqual(client.get("/api/status").status_code, 401)
            self.assertEqual(client.get("/api/violations").status_code, 401)
            self.assertEqual(client.get("/api/alerts").status_code, 401)
            self.assertEqual(client.get("/api/analytics").status_code, 401)
            self.assertEqual(client.get("/api/cameras").status_code, 401)

            # 2. Authenticated requests succeed
            self.assertEqual(client.get("/api/status", headers=auth_headers).status_code, 200)

            # 3. Logout revokes token
            logout_resp = client.post("/api/auth/logout", headers=auth_headers)
            self.assertEqual(logout_resp.status_code, 200)
            self.assertTrue(logout_resp.get_json()["success"])

            # 4. Revoked token is rejected with 401
            self.assertEqual(client.get("/api/status", headers=auth_headers).status_code, 401)

    def test_14_video_control_and_cameras(self):
        """Test video stream pause/resume/reconnect controls and camera management API."""
        from app import app
        from auth_security import security_manager
        token = security_manager.generate_token("admin@traffic.gov.in", "ADMIN", "Administrator")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        with app.test_client() as client:
            # Video control: pause
            res = client.post("/api/video/control", headers=headers, json={"action": "pause"})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.get_json()["status"], "PAUSED")

            # Video control: resume
            res = client.post("/api/video/control", headers=headers, json={"action": "resume"})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.get_json()["status"], "PLAYING")

            # Get cameras list
            res_cams = client.get("/api/cameras", headers=headers)
            self.assertEqual(res_cams.status_code, 200)
            cams = res_cams.get_json()["cameras"]
            self.assertGreaterEqual(len(cams), 1)

            # Register new camera
            new_cam_resp = client.post("/api/cameras", headers=headers, json={
                "name": "East Junction Unit",
                "location": "Corridor 4",
                "mode": "UPLOAD",
                "source": "backend/uploads/sample_traffic.mp4"
            })
            self.assertEqual(new_cam_resp.status_code, 201)
            new_cam = new_cam_resp.get_json()["camera"]
            self.assertTrue(new_cam["id"].startswith("CAM-"))

            # Activate camera
            act_resp = client.post(f"/api/cameras/{new_cam['id']}/activate", headers=headers)
            self.assertEqual(act_resp.status_code, 200)

            # Delete camera
            del_resp = client.delete(f"/api/cameras/{new_cam['id']}", headers=headers)
            self.assertEqual(del_resp.status_code, 200)
            self.assertTrue(del_resp.get_json()["success"])

    def test_15_system_health_and_audit(self):
        """Test detailed subsystem health diagnostics and audit trail log retrieval."""
        from app import app
        from auth_security import security_manager
        token = security_manager.generate_token("auditor@traffic.gov.in", "AUDITOR", "Auditor")
        headers = {"Authorization": f"Bearer {token}"}

        with app.test_client() as client:
            # System Health
            h_resp = client.get("/api/system/health", headers=headers)
            self.assertEqual(h_resp.status_code, 200)
            h_data = h_resp.get_json()
            self.assertEqual(h_data["status"], "HEALTHY")
            self.assertIn("ai_model", h_data)
            self.assertIn("video_pipeline", h_data)

            # Audit Logs
            audit_resp = client.get("/api/system/audit-logs", headers=headers)
            self.assertEqual(audit_resp.status_code, 200)
            audit_data = audit_resp.get_json()
            self.assertTrue(audit_data["success"])
            self.assertIsInstance(audit_data["logs"], list)

    def test_16_combined_telemetry_and_video_jobs(self):
        """Test unified telemetry polling endpoint and asynchronous video jobs registry."""
        from app import app
        from auth_security import security_manager
        token = security_manager.generate_token("officer@traffic.gov.in", "OPERATOR", "Officer")
        headers = {"Authorization": f"Bearer {token}"}

        with app.test_client() as client:
            # 1. Combined telemetry
            res = client.get("/api/telemetry/combined", headers=headers)
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertIn("status", data)
            self.assertIn("violations", data)
            self.assertIn("alerts", data)
            self.assertIn("cameras", data)
            self.assertIn("analytics", data)

            # 2. Video jobs registry
            jobs_res = client.get("/api/video/jobs", headers=headers)
            self.assertEqual(jobs_res.status_code, 200)
            jobs_data = jobs_res.get_json()
            self.assertTrue(jobs_data["success"])
            self.assertIsInstance(jobs_data["jobs"], list)

    def test_17_homography_polygon_bounds(self):
        """Test that perspective homography rejects points outside the calibrated road plane."""
        from calibration_engine import calibration_engine
        # Point inside calibration trap
        inside_pt = (320, 350)
        self.assertTrue(calibration_engine.is_inside_trap(inside_pt[0], inside_pt[1]))
        w_in = calibration_engine.pixel_to_world(inside_pt[0], inside_pt[1])
        self.assertIsNotNone(w_in)

        # Point in sky/outside trap (e.g. y = 50)
        outside_pt = (320, 50)
        self.assertFalse(calibration_engine.is_inside_trap(outside_pt[0], outside_pt[1]))
        w_out = calibration_engine.pixel_to_world(outside_pt[0], outside_pt[1])
        self.assertIsNone(w_out)

    def test_18_tiered_rate_limiting(self):
        """Test that high-frequency telemetry is permitted while auth endpoints enforce strict defense."""
        from auth_security import security_manager
        test_ip = "192.168.100.99"

        # Telemetry category allows up to 360 requests/min
        allowed_count = 0
        for _ in range(250):
            if security_manager.check_rate_limit(test_ip, category="telemetry"):
                allowed_count += 1
        self.assertEqual(allowed_count, 250)

        # Auth category rejects after 30 attempts
        auth_allowed = 0
        for _ in range(35):
            if security_manager.check_rate_limit(test_ip, category="auth"):
                auth_allowed += 1
        self.assertEqual(auth_allowed, 30)

if __name__ == "__main__":
    unittest.main()
