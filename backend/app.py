import os
from pathlib import Path
from flask import Flask, Response, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
from config import FLASK_HOST, FLASK_PORT, DEBUG, VIOLATIONS_DIR, STATIC_DIR, BASE_DIR
from traffic_engine import traffic_engine
from db_client import db_manager

FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

app = Flask(__name__, static_folder=str(STATIC_DIR))
CORS(app)

def generate_video_stream():
    """Generator for MJPEG stream consumed by the React UI."""
    while True:
        try:
            frame_bytes = traffic_engine.get_frame()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except Exception as e:
            print(f"[ERROR] Stream generator exception: {e}")
            break

@app.route('/')
def index():
    """Serves the compiled React frontend if present."""
    if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
        return send_file(str(FRONTEND_DIST / "index.html"))
    return jsonify({
        "status": "online",
        "message": "AI Traffic Management Backend is operational.",
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
    """Live MJPEG video streaming route."""
    return Response(generate_video_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/status', methods=['GET'])
def get_status():
    """Returns current live system status."""
    return jsonify(traffic_engine.get_status())

@app.route('/api/violations', methods=['GET'])
def get_violations():
    """Returns recent traffic violation records."""
    limit = request.args.get('limit', default=25, type=int)
    violations = db_manager.get_recent_violations(limit=limit)
    return jsonify({
        "success": True,
        "count": len(violations),
        "violations": violations
    })

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Returns aggregated data prepared for Chart.js rendering."""
    status = traffic_engine.get_status()
    violations = db_manager.get_recent_violations(limit=50)
    history = db_manager.get_telemetry_history(limit=20)

    # 1. Vehicle Type Composition (for Doughnut Chart)
    vehicle_comp = status["traffic"]["vehicle_counts"]

    # 2. Violation Types Breakdown (for Bar Chart)
    violation_counts = {"Red Light Jump": 0, "Wrong-Way Driving": 0, "Overspeeding": 0}
    for v in violations:
        vtype = v.get("violation_type", "Other")
        if vtype in violation_counts:
            violation_counts[vtype] += 1
        else:
            violation_counts[vtype] = 1

    # 3. Time Series Density (for Line Chart)
    timestamps = [h.get("timestamp", "")[-8:-1] for h in history] or ["Now"]
    densities = [h.get("active_vehicles", 0) for h in history] or [status["traffic"]["active_vehicles"]]

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
            "data": densities
        }
    })

@app.route('/api/signal/override', methods=['POST'])
def override_signal():
    """Manual signal control endpoint for operators."""
    data = request.get_json(silent=True) or {}
    desired_state = data.get("state", "GREEN").upper()
    if desired_state in ("GREEN", "YELLOW", "RED"):
        traffic_engine.signal_state = desired_state
        traffic_engine.manual_override = data.get("manual", True)
        return jsonify({"success": True, "state": desired_state, "manual": traffic_engine.manual_override})
    return jsonify({"error": "Invalid state"}), 400

@app.route('/static/violations/<path:filename>')
def serve_violation_snapshot(filename):
    """Serves cropped violation snapshots."""
    return send_from_directory(str(VIOLATIONS_DIR), filename)

if __name__ == '__main__':
    print(f"==================================================")
    print(f"[SYSTEM] AI Traffic Management System Backend Starting...")
    print(f"Dashboard UI:       http://localhost:{FLASK_PORT}/")
    print(f"Live MJPEG Stream:  http://localhost:{FLASK_PORT}/video_feed")
    print(f"REST Status API:    http://localhost:{FLASK_PORT}/api/status")
    print(f"==================================================")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=DEBUG, threaded=True)
