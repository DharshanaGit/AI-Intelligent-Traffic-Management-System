import hashlib
import hmac
import time
import json
import base64
import secrets
import re
from functools import wraps
from flask import request, jsonify, g
from datetime import datetime
from config import BASE_DIR, DEFAULT_EMAIL, DEFAULT_PASSWORD, DEFAULT_NAME, DEFAULT_ROLE
from db_client import db_manager

SECRET_KEY = "TRAFFIC_SECURE_KEY_LOCAL_DEV_2026_DO_NOT_EXPOSE"
AUDIT_LOG_FILE = BASE_DIR / "backend" / "audit_trail.log"

USERS = {
    "admin": {"role": "ADMIN", "name": "System Administrator"},
    "operator": {"role": "OPERATOR", "name": "Traffic Control Officer"},
    "auditor": {"role": "AUDITOR", "name": "Independent Auditor"}
}

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

def validate_email_format(email: str) -> tuple[bool, str]:
    """Validates that email follows standard format without uppercase characters."""
    if not email or not isinstance(email, str):
        return False, "Email address is required."
    clean = email.strip()
    if re.search(r'[A-Z]', clean):
        return False, "Uppercase letters are not allowed in email address. Please use only lowercase letters."
    if not EMAIL_REGEX.match(clean):
        return False, "Invalid email address format (e.g. officer@traffic.gov.in)."
    return True, clean.lower()

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Enforces password strength:
    - Minimum 8 characters
    - Must contain at least one letter and at least one number
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter."
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one numeric digit."
    return True, ""

def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Generates PBKDF2-HMAC-SHA256 hash with cryptographic salt."""
    if not salt:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return pw_hash, salt

def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Verifies candidate password against stored salt and expected hash."""
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return hmac.compare_digest(pw_hash, expected_hash)

# Seed default administrator accounts into database if empty
def _ensure_default_accounts():
    admin_email = (DEFAULT_EMAIL or "admin@traffic.gov.in").lower().strip()
    if not db_manager.get_user_by_email(admin_email):
        p_hash, s = hash_password(DEFAULT_PASSWORD or "Admin@2026")
        db_manager.create_user(admin_email, p_hash, s, DEFAULT_NAME or "System Administrator", DEFAULT_ROLE or "ADMIN")
    if not db_manager.get_user_by_email("officer@traffic.gov.in"):
        p_hash, s = hash_password("Officer@2026")
        db_manager.create_user("officer@traffic.gov.in", p_hash, s, "Traffic Control Officer", "OPERATOR")

_ensure_default_accounts()

class SecurityManager:
    def __init__(self):
        self.rate_limit_window = 60  # seconds
        self.max_requests_per_window = 120
        self.request_counts = {}  # ip -> [(timestamp, count)]
        self.revoked_tokens = set()

    def revoke_token(self, token: str):
        """Adds token to blacklist to enforce immediate revocation upon logout."""
        if token:
            self.revoked_tokens.add(token.strip())

    def generate_token(self, email: str, role: str, name: str = "Operator") -> str:
        """Generates cryptographically signed HMAC-SHA256 session token."""
        header = base64.b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode()
        payload_data = {
            "sub": email,
            "role": role,
            "name": name,
            "iat": int(time.time()),
            "exp": int(time.time() + 3600 * 12)  # 12 hours
        }
        payload = base64.b64encode(json.dumps(payload_data).encode()).decode()
        signature = hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).hexdigest()
        return f"{header}.{payload}.{signature}"

    def verify_token(self, token: str) -> dict:
        """Verifies integrity, revocation status and expiry of authentication token."""
        try:
            if not token or token in self.revoked_tokens:
                return None
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
        recent = [t for t in requests if now - t < self.rate_limit_window]
        recent.append(now)
        self.request_counts[client_ip] = recent
        return len(recent) <= self.max_requests_per_window

    def log_audit(self, action: str, email: str, role: str, details: dict):
        """Appends immutable audit log entry for regulatory compliance."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "user": email,
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
    """Decorator to enforce strict authentication and RBAC."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            client_ip = request.remote_addr or "127.0.0.1"
            if not security_manager.check_rate_limit(client_ip):
                return jsonify({"error": "Too many requests. Rate limit exceeded."}), 429

            auth_header = request.headers.get("Authorization", "")
            token = ""
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
            elif request.args.get("token"):
                token = request.args.get("token").strip()

            if not token:
                return jsonify({"error": "Authentication required. Please log in or sign up."}), 401

            user_data = security_manager.verify_token(token)
            if not user_data:
                return jsonify({"error": "Invalid or expired session token. Please log in again."}), 401

            g.user = user_data
            if roles and user_data.get("role") not in roles:
                return jsonify({"error": f"Access forbidden. Requires role in {roles}."}), 403

            return f(*args, **kwargs)
        return decorated
    return decorator
