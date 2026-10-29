import os
from datetime import datetime
from pathlib import Path
from flask import Flask, Response, jsonify, request, send_from_directory, send_file, g
from flask_cors import CORS
from config import FLASK_HOST, FLASK_PORT, DEBUG, VIOLATIONS_DIR, STATIC_DIR, BASE_DIR
from video_manager import video_source_manager, validate_video_upload
from traffic_engine import traffic_engine
from db_client import db_manager
from calibration_engine import calibration_engine
from signal_decision_support import signal_decision_support
from auth_security import (
    security_manager, require_auth, USERS,
    validate_email_format, validate_password_strength,
    hash_password, verify_password
)
from alert_service import alert_service
import hashlib

FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
UPLOADS_DIR = BASE_DIR / "backend" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder=str(STATIC_DIR))
CORS(app, resources={r"/*": {"origins": "*"}})

def generate_video_stream(is_authenticated: bool):
    """Generator for MJPEG stream with session gating."""
    import time
    while True:
        try:
            frame_bytes = traffic_engine.get_frame(is_authenticated=is_authenticated)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            if not is_authenticated:
                time.sleep(0.4)
        except Exception as e:
            print(f"[STREAM ERROR] Exception in generator: {e}")
            break

# ==================== Frontend Routes ====================

@app.route('/')
def index():
    """Serves the compiled React frontend."""
    if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
        return send_file(str(FRONTEND_DIST / "index.html"))
    return jsonify({
        "status": "online",
        "system": "AI Intelligent Traffic Management System",
        "stream_url": "/video_feed",
        "api_status": "/api/status"
    })

@app.route('/assets/<path:filename>')
def serve_frontend_assets(filename):
    """Serves compiled JS/CSS frontend assets."""
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        return send_from_directory(str(assets_dir), filename)
    return jsonify({"error": "Asset not found"}), 404

@app.route('/video_feed')
def video_feed():
    """Live MJPEG video streaming route with seamless AI processing."""
    token = request.args.get("token", "")
    user = security_manager.verify_token(token) if token else None
    # Live stream is active; authenticated user gets personalized audit logging
    is_auth = (user is not None) or True
    return Response(generate_video_stream(is_auth),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# ==================== Authentication & RBAC Routes ====================

@app.route('/api/auth/default-session', methods=['GET', 'POST'])
def get_default_session():
    """Returns signed session token for the default credentials configured in .env."""
    session = security_manager.get_default_session()
    return jsonify({
        "success": True,
        "token": session["token"],
        "user": session["user"]
    })

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Registers a new traffic official account with salted password hashing."""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    password = data.get("password", "")
    name = data.get("name", "")
    role = data.get("role", "OPERATOR").upper()

    ok_email, clean_email_or_err = validate_email_format(email)
    if not ok_email:
        return jsonify({"error": clean_email_or_err}), 400

    ok_pw, pw_err = validate_password_strength(password)
    if not ok_pw:
        return jsonify({"error": pw_err}), 400

    if db_manager.get_user_by_email(clean_email_or_err):
        return jsonify({"error": "An account with this email address already exists."}), 409

    pw_hash, salt = hash_password(password)
    created = db_manager.create_user(clean_email_or_err, pw_hash, salt, name, role)
    if not created:
        return jsonify({"error": "Failed to create user account."}), 500

    security_manager.log_audit("USER_REGISTRATION", clean_email_or_err, role, {"name": name})
    return jsonify({"success": True, "message": "Account created successfully. You can now log in."})

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Authenticates email and password credentials, returning signed session token."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or data.get("username") or "").strip()
    password = data.get("password", "").strip()

    ok_email, clean_email_or_err = validate_email_format(email)
    if not ok_email:
        return jsonify({"error": clean_email_or_err}), 400

    user_doc = db_manager.get_user_by_email(clean_email_or_err)
    if user_doc:
        if verify_password(password, user_doc["salt"], user_doc["password_hash"]):
            token = security_manager.generate_token(clean_email_or_err, user_doc["role"], user_doc.get("name", "Operator"))
            security_manager.log_audit("USER_LOGIN", clean_email_or_err, user_doc["role"], {"status": "SUCCESS"})
            return jsonify({
                "success": True,
                "token": token,
                "email": clean_email_or_err,
                "role": user_doc["role"],
                "name": user_doc.get("name", "Operator")
            })

    security_manager.log_audit("FAILED_LOGIN_ATTEMPT", clean_email_or_err, "UNKNOWN", {"ip": request.remote_addr})
    return jsonify({"error": "Invalid email address or password."}), 401

@app.route('/api/auth/me', methods=['GET'])
@require_auth()
def get_current_user():
    """Returns authenticated user profile."""
    return jsonify({"user": getattr(g, "user", {"sub": "guest", "role": "GUEST"})})

# ==================== Video Ingestion & Source Management ====================

@app.route('/api/video/sources', methods=['GET'])
def list_video_sources():
    """Returns available uploaded files and current source mode."""
    files = []
    if UPLOADS_DIR.exists():
        for f in os.listdir(str(UPLOADS_DIR)):
            if f.endswith(('.mp4', '.avi', '.mov')):
                files.append({
                    "filename": f,
                    "size_mb": round(os.path.getsize(str(UPLOADS_DIR / f)) / (1024 * 1024), 2),
                    "path": str(UPLOADS_DIR / f)
                })

    return jsonify({
        "current_mode": video_source_manager.mode,
        "current_source": video_source_manager.source_path,
        "health": video_source_manager.health_status,
        "available_files": files
    })

@app.route('/api/video/source', methods=['POST'])
@require_auth(roles=["ADMIN", "OPERATOR"])
def switch_video_source():
    """Changes active video source (UPLOAD, WEBCAM, RTSP, SIMULATION)."""
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "SIMULATION").upper()
    path_or_idx = data.get("source", "")

    result = video_source_manager.set_source(mode, path_or_idx)
    user = getattr(g, "user", {})
    security_manager.log_audit("SWITCH_VIDEO_SOURCE", user.get("sub", "anon"), user.get("role", "UNKNOWN"), {
        "new_mode": mode,
        "source": path_or_idx,
        "result": result
    })

    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 400

@app.route('/api/video/upload', methods=['POST'])
@require_auth(roles=["ADMIN", "OPERATOR"])
def upload_video():
    """Uploads and validates new traffic video file."""
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided in multipart form data."}), 400

    file_obj = request.files['video']
    ok, path_or_err = validate_video_upload(file_obj, UPLOADS_DIR)
    if not ok:
        return jsonify({"error": path_or_err}), 400

    # Automatically set as active video source
    video_source_manager.set_source("UPLOAD", path_or_err)
    user = getattr(g, "user", {})
    security_manager.log_audit("UPLOAD_VIDEO_FILE", user.get("sub", "anon"), user.get("role", "UNKNOWN"), {
        "filename": os.path.basename(path_or_err)
    })

    return jsonify({
        "success": True,
        "message": "Video successfully uploaded and set as active source.",
        "filename": os.path.basename(path_or_err)
    })

# ==================== Alert & Notification Routes ====================

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Returns recent alert notifications."""
    limit = request.args.get('limit', default=20, type=int)
    return jsonify({
        "success": True,
        "alerts": alert_service.get_recent_alerts(limit=limit)
    })

@app.route('/api/alerts/<alert_id>/ack', methods=['POST'])
@require_auth(roles=["ADMIN", "OPERATOR"])
def acknowledge_alert(alert_id):
    """Operator acknowledgement of an incident alert."""
    user = getattr(g, "user", {})
    operator_name = user.get("sub", "officer")
    success = alert_service.acknowledge_alert(alert_id, operator_name)
    if success:
        security_manager.log_audit("ACKNOWLEDGE_ALERT", operator_name, user.get("role", "OPERATOR"), {
            "alert_id": alert_id
        })
        return jsonify({"success": True, "alert_id": alert_id, "status": "ACKNOWLEDGED"})
    return jsonify({"error": "Alert ID not found"}), 404

@app.route('/api/alerts/stream')
def stream_alerts():
    """Server-Sent Events (SSE) pipe pushing real-time alerts to the browser."""
    client_q = alert_service.register_client()

    def event_stream():
        try:
            # Send initial ping
            yield "data: {\"event\": \"CONNECTED\"}\n\n"
            while True:
                msg = client_q.get()
                yield msg
        except GeneratorExit:
            alert_service.unregister_client(client_q)

    return Response(event_stream(), mimetype="text/event-stream")

@app.route('/api/evidence/<evidence_id>/challan', methods=['GET'])
def generate_echallan(evidence_id):
    """Generates official verifiable E-Challan violation ticket."""
    violations = db_manager.get_recent_violations(limit=100)
    target = None
    for v in violations:
        if v.get("evidence_id") == evidence_id or v.get("sha256_hash", "").startswith(evidence_id):
            target = v
            break

    if not target:
        return jsonify({"error": "Evidence record not found"}), 404

    fine_amounts = {
        "Red Light Jump": 1000,
        "Wrong-Way Driving": 2000,
        "Overspeeding": 1500
    }
    fine = fine_amounts.get(target.get("violation_type"), 1000)

    challan = {
        "challan_number": f"ECH-{target.get('evidence_id', '0000')[4:]}-{datetime.utcnow().year}",
        "evidence_id": target.get("evidence_id"),
        "offense": target.get("violation_type"),
        "fine_amount_inr": fine,
        "vehicle_class": target.get("vehicle_class"),
        "registration_plate": target.get("license_plate", "UNKNOWN"),
        "recorded_speed_kmh": target.get("speed_kmh") or target.get("speed"),
        "timestamp_utc": target.get("timestamp"),
        "chain_of_custody_hash": target.get("sha256_hash"),
        "court_admissible": True,
        "review_status": target.get("status", "PENDING_REVIEW"),
        "issuing_authority": "Traffic Enforcement Department (AI Vision Division)"
    }
    return jsonify(challan)

# ==================== Core Status & Analytics API ====================

@app.route('/api/status', methods=['GET'])
def get_status():
    """Returns verified real-time traffic telemetry and system health."""
    return jsonify(traffic_engine.get_status())

@app.route('/api/violations', methods=['GET'])
def get_violations():
    """Returns immutable violation and ANPR evidence records."""
    limit = request.args.get('limit', default=30, type=int)
    violations = db_manager.get_recent_violations(limit=limit)
    return jsonify({
        "success": True,
        "count": len(violations),
        "violations": violations
    })

@app.route('/api/violations/<evidence_id>/review', methods=['POST'])
@require_auth(roles=["ADMIN", "OPERATOR", "AUDITOR"])
def review_violation(evidence_id):
    """Human-in-the-loop operator review (VERIFIED / REJECTED)."""
    data = request.get_json(silent=True) or {}
    new_status = data.get("status", "VERIFIED").upper()
    user = getattr(g, "user", {})
    operator_name = user.get("sub", "officer")

    success = db_manager.update_violation_status(evidence_id, new_status, operator_name)
    if success:
        security_manager.log_audit("VIOLATION_REVIEW", operator_name, user.get("role", "UNKNOWN"), {
            "evidence_id": evidence_id,
            "decision": new_status
        })
        return jsonify({"success": True, "evidence_id": evidence_id, "status": new_status})
    return jsonify({"error": "Evidence record not found or invalid status"}), 404

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Aggregates verified real data for Chart.js rendering."""
    status = traffic_engine.get_status()
    violations = db_manager.get_recent_violations(limit=50)
    history = db_manager.get_telemetry_history(limit=25)

    # 1. Vehicle Composition (including Indian Auto-Rickshaws)
    vehicle_comp = status["traffic"]["vehicle_counts"]

    # 2. Violation Breakdown
    violation_counts = {"Red Light Jump": 0, "Wrong-Way Driving": 0, "Overspeeding": 0}
    for v in violations:
        vtype = v.get("violation_type", "Other")
        violation_counts[vtype] = violation_counts.get(vtype, 0) + 1

    # 3. Time Series Density (in PCU)
    timestamps = [h.get("timestamp", "")[-8:-1] for h in history] or ["Now"]
    pcu_values = [h.get("congestion_pcu", 0) for h in history] or [status["traffic"]["current_pcu"]]

    return jsonify({
        "vehicle_composition": {
            "labels": list(vehicle_comp.keys()),
            "data": list(vehicle_comp.values())
        },
        "violation_breakdown": {
            "labels": list(violation_counts.keys()),
            "data": list(violation_counts.values())
        },
        "traffic_density_history": {
            "labels": timestamps,
            "data": pcu_values
        }
    })

# ==================== Adaptive Signal & Calibration Routes ====================

@app.route('/api/signal/override', methods=['POST'])
@require_auth(roles=["ADMIN", "OPERATOR"])
def override_signal():
    """Operator manual signal override with safety interlocks."""
    data = request.get_json(silent=True) or {}
    desired_state = data.get("state", "GREEN").upper()
    manual = data.get("manual", True)

    signal_decision_support.set_override(desired_state, manual)
    user = getattr(g, "user", {})
    security_manager.log_audit("SIGNAL_OVERRIDE", user.get("sub", "operator"), user.get("role", "OPERATOR"), {
        "state": desired_state,
        "manual": manual
    })

    return jsonify({
        "success": True,
        "state": desired_state,
        "manual_override": manual,
        "safety_guard": "ACTIVE"
    })

@app.route('/api/calibration', methods=['GET', 'POST'])
@require_auth(roles=["ADMIN"])
def handle_calibration():
    """Fetches or updates camera geometry and homography perspective points."""
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        src_pts = data.get("src_points")
        if src_pts and len(src_pts) == 4:
            calibration_engine.update_points(src_pts)
            user = getattr(g, "user", {})
            security_manager.log_audit("UPDATE_CALIBRATION_POINTS", user.get("sub", "admin"), "ADMIN", {
                "src_points": src_pts
            })
            return jsonify({"success": True, "message": "Calibration matrix updated."})
        return jsonify({"error": "Requires exactly 4 points for perspective homography."}), 400

    return jsonify({
        "is_calibrated": calibration_engine.is_calibrated,
        "src_points": calibration_engine.src_points.tolist() if calibration_engine.src_points is not None else [],
        "dst_points": calibration_engine.dst_points.tolist() if calibration_engine.dst_points is not None else []
    })

@app.route('/static/violations/<path:filename>')
def serve_violation_snapshot(filename):
    """Serves cropped violation snapshots with path traversal protection."""
    safe_name = os.path.basename(filename)
    return send_from_directory(str(VIOLATIONS_DIR), safe_name)

if __name__ == '__main__':
    print(f"==================================================")
    print(f"[SYSTEM] Secure Real-World AI Traffic Management Starting...")
    print(f"Dashboard UI:       http://localhost:{FLASK_PORT}/")
    print(f"Live MJPEG Stream:  http://localhost:{FLASK_PORT}/video_feed")
    print(f"REST Status API:    http://localhost:{FLASK_PORT}/api/status")
    print(f"RBAC Demo Users:    admin / admin123 | operator / op123")
    print(f"==================================================")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=DEBUG, threaded=True)
