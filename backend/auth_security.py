import hashlib
import hmac
import time
import json
import base64
from functools import wraps
from flask import request, jsonify, g
from datetime import datetime
from config import BASE_DIR

SECRET_KEY = "TRAFFIC_SECURE_KEY_LOCAL_DEV_2026_DO_NOT_EXPOSE"
AUDIT_LOG_FILE = BASE_DIR / "backend" / "audit_trail.log"

# Pre-defined Role Accounts for Demonstration & Security
# Passwords hashed with SHA-256 + Salt
USERS = {
    "admin": {
        "password_hash": hashlib.sha256(b"admin_traffic_2026_salt_123").hexdigest(),
        "role": "ADMIN",
        "name": "System Administrator"
    },
    "operator": {
        "password_hash": hashlib.sha256(b"operator_2026_salt_123").hexdigest(),
        "role": "OPERATOR",
        "name": "Traffic Control Officer"
    },
    "auditor": {
        "password_hash": hashlib.sha256(b"auditor_2026_salt_123").hexdigest(),
        "role": "AUDITOR",
        "name": "Compliance Inspector"
    }
}

class SecurityManager:
    def __init__(self):
        self.rate_limit_window = 60  # seconds
        self.max_requests_per_window = 120
        self.request_counts = {}  # ip -> [(timestamp, count)]

    def generate_token(self, username: str, role: str) -> str:
        """Generates cryptographically signed HMAC-SHA256 session token."""
        header = base64.b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode()
        payload_data = {
            "sub": username,
            "role": role,
            "iat": int(time.time()),
            "exp": int(time.time() + 3600 * 12)  # 12 hours
        }
        payload = base64.b64encode(json.dumps(payload_data).encode()).decode()
        signature = hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).hexdigest()
        return f"{header}.{payload}.{signature}"

    def verify_token(self, token: str) -> dict:
        """Verifies integrity and expiry of authentication token."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header, payload, sig = parts
            expected_sig = hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return None

            data = json.loads(base64.b64decode(payload.encode()).decode())
            if data.get("exp", 0) < time.time():
                return None
            return data
        except Exception:
            return None

    def check_rate_limit(self, client_ip: str) -> bool:
        """Sliding window in-memory rate limiter."""
        now = time.time()
        requests = self.request_counts.get(client_ip, [])
        # Filter requests within current window
        recent = [t for t in requests if now - t < self.rate_limit_window]
        recent.append(now)
        self.request_counts[client_ip] = recent
        return len(recent) <= self.max_requests_per_window

    def log_audit(self, action: str, username: str, role: str, details: dict):
        """Appends immutable audit log entry for regulatory compliance."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "user": username,
            "role": role,
            "ip": request.remote_addr if request else "127.0.0.1",
            "details": details
        }
        try:
            with open(str(AUDIT_LOG_FILE), "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"[SECURITY LOG ERROR] Could not write audit log: {e}")

security_manager = SecurityManager()

def require_auth(roles=None):
    """Decorator to enforce authentication and RBAC."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Check rate limit
            client_ip = request.remote_addr or "127.0.0.1"
            if not security_manager.check_rate_limit(client_ip):
                return jsonify({"error": "Too many requests. Rate limit exceeded."}), 429

            # Check Authorization Header
            auth_header = request.headers.get("Authorization", "")
            token = ""
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

            # If no token passed, allow guest read-only for public metrics
            if not token and (request.method == "GET" and request.endpoint in ('video_feed', 'get_status', 'get_analytics', 'serve_frontend_assets', 'index')):
                g.user = {"sub": "guest", "role": "GUEST"}
                return f(*args, **kwargs)

            user_data = security_manager.verify_token(token)
            if not user_data:
                # If guest accessing protected mutation endpoint
                if roles:
                    return jsonify({"error": "Authentication required. Invalid or expired token."}), 401
                g.user = {"sub": "guest", "role": "GUEST"}
                return f(*args, **kwargs)

            g.user = user_data
            if roles and user_data.get("role") not in roles:
                return jsonify({"error": f"Access forbidden. Requires role in {roles}."}), 403

            return f(*args, **kwargs)
        return decorated
    return decorator
