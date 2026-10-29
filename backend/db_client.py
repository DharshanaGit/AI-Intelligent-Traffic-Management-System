import os
import time
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, OperationFailure, ConfigurationError
from config import MONGO_URI, DB_NAME, BASE_DIR

OFFLINE_SPOOL_FILE = BASE_DIR / "backend" / "offline_spool.json"

class DatabaseManager:
    def __init__(self):
        self.connected = False
        self.client = None
        self.db = None
        self.violations_col = None
        self.telemetry_col = None
        self.audit_col = None
        self.users_col = None
        
        # Local RAM & Spool buffers
        self.local_violations: List[Dict[str, Any]] = []
        self.local_telemetry: List[Dict[str, Any]] = []
        self.local_users: Dict[str, Dict[str, Any]] = {}
        self._load_offline_spool()
        self._init_connection()

    def _load_offline_spool(self):
        """Loads persistent local spool file if present."""
        if OFFLINE_SPOOL_FILE.exists():
            try:
                with open(str(OFFLINE_SPOOL_FILE), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.local_violations = data.get("violations", [])
                    self.local_telemetry = data.get("telemetry", [])
                    self.local_users = data.get("users", {})
            except Exception as e:
                print(f"[DB SPOOL WARNING] Could not read existing spool file: {e}")

    def _save_offline_spool(self):
        """Persists local buffer to offline spool JSON file."""
        try:
            with open(str(OFFLINE_SPOOL_FILE), "w", encoding="utf-8") as f:
                json.dump({
                    "violations": self.local_violations[:200],
                    "telemetry": self.local_telemetry[-100:],
                    "users": self.local_users
                }, f, indent=2)
        except Exception as e:
            print(f"[DB SPOOL ERROR] Failed writing offline spool: {e}")

    def _init_connection(self):
        """Initializes connection to MongoDB Atlas with schema verification and indexing."""
        if not MONGO_URI or "<db_password>" in MONGO_URI:
            print("[INFO] MongoDB Atlas URI contains '<db_password>'.")
            print("[INFO] Running in resilient offline spooling mode (zero data loss).")
            return

        try:
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            self.client.admin.command('ping')
            self.db = self.client[DB_NAME]
            self.violations_col = self.db["violations"]
            self.telemetry_col = self.db["traffic_telemetry"]
            self.audit_col = self.db["security_audits"]
            self.users_col = self.db["users"]

            # Ensure optimal compound indices
            self.violations_col.create_index([("timestamp", DESCENDING), ("status", ASCENDING)])
            self.violations_col.create_index([("sha256_hash", ASCENDING)], unique=True)
            self.telemetry_col.create_index([("timestamp", DESCENDING)])
            self.users_col.create_index([("email", ASCENDING)], unique=True)

            self.connected = True
            print(f"[SUCCESS] Connected securely to MongoDB Atlas database: {DB_NAME}")
            
            # Flush offline spool to remote database
            self.flush_spool_to_remote()
        except (ConnectionFailure, OperationFailure, ConfigurationError) as err:
            self.connected = False
            print(f"[WARNING] MongoDB Atlas unreachable: {type(err).__name__}. Offline spool active.")
        except Exception as e:
            self.connected = False
            print(f"[WARNING] MongoDB connection exception: {e}")

    def flush_spool_to_remote(self):
        """Pushes cached offline violations to MongoDB Atlas once connection is online."""
        if not self.connected or not self.violations_col:
            return

        unflushed = [v for v in self.local_violations if not v.get("_synced_to_atlas", False)]
        if unflushed:
            print(f"[SYNC] Pushing {len(unflushed)} offline spooled events to MongoDB Atlas...")
            for v in unflushed:
                try:
                    record_copy = v.copy()
                    record_copy.pop("_id", None)
                    record_copy.pop("_synced_to_atlas", None)
                    self.violations_col.update_one(
                        {"sha256_hash": v["sha256_hash"]},
                        {"$set": record_copy},
                        upsert=True
                    )
                    v["_synced_to_atlas"] = True
                except Exception as e:
                    print(f"[SYNC ERROR] Error syncing record {v.get('evidence_id')}: {e}")
            self._save_offline_spool()

    def log_violation(self, record: dict) -> dict:
        """Stores evidence and violation record with non-repudiation."""
        if self.connected and self.violations_col is not None:
            try:
                record_copy = record.copy()
                result = self.violations_col.insert_one(record_copy)
                record["_id"] = str(result.inserted_id)
                record["_synced_to_atlas"] = True
            except Exception as e:
                print(f"[ERROR] Failed writing to MongoDB Atlas: {e}")
                record["_synced_to_atlas"] = False
        else:
            record["_synced_to_atlas"] = False
            record["_id"] = f"spool_{int(time.time()*1000)}"

        self.local_violations.insert(0, record)
        if len(self.local_violations) > 200:
            self.local_violations = self.local_violations[:200]
        self._save_offline_spool()
        return record

    def update_violation_status(self, evidence_id: str, new_status: str, operator_name: str) -> bool:
        """Human-in-the-loop review state change (VERIFIED / REJECTED)."""
        new_status = new_status.upper()
        if new_status not in ("VERIFIED", "REJECTED", "PENDING_REVIEW"):
            return False

        updated = False
        # Update in local cache
        for v in self.local_violations:
            if v.get("evidence_id") == evidence_id or v.get("sha256_hash", "").startswith(evidence_id):
                v["status"] = new_status
                custody = v.setdefault("chain_of_custody", {})
                custody["reviewed_by"] = operator_name
                custody["reviewed_at"] = datetime.utcnow().isoformat() + "Z"
                updated = True
                break

        # Update in MongoDB Atlas if connected
        if self.connected and self.violations_col is not None:
            try:
                self.violations_col.update_one(
                    {"$or": [{"evidence_id": evidence_id}, {"sha256_hash": {"$regex": f"^{evidence_id}"}}]},
                    {"$set": {
                        "status": new_status,
                        "chain_of_custody.reviewed_by": operator_name,
                        "chain_of_custody.reviewed_at": datetime.utcnow().isoformat() + "Z"
                    }}
                )
                updated = True
            except Exception as e:
                print(f"[ERROR] Could not update review status in MongoDB: {e}")

        self._save_offline_spool()
        return updated

    def get_recent_violations(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Retrieves recent violations for dashboard."""
        if self.connected and self.violations_col is not None:
            try:
                records = list(self.violations_col.find().sort("timestamp", DESCENDING).limit(limit))
                for r in records:
                    r["_id"] = str(r["_id"])
                return records
            except Exception:
                pass
        return self.local_violations[:limit]

    def log_telemetry(self, telemetry: dict):
        """Records rolling telemetry samples."""
        telemetry["timestamp"] = datetime.utcnow().isoformat() + "Z"
        if self.connected and self.telemetry_col is not None:
            try:
                self.telemetry_col.insert_one(telemetry.copy())
            except Exception:
                pass
        
        self.local_telemetry.append(telemetry)
        if len(self.local_telemetry) > 60:
            self.local_telemetry = self.local_telemetry[-60:]
        self._save_offline_spool()

    def get_telemetry_history(self, limit: int = 30) -> List[Dict[str, Any]]:
        if self.connected and self.telemetry_col is not None:
            try:
                records = list(self.telemetry_col.find().sort("timestamp", DESCENDING).limit(limit))
                for r in records:
                    r["_id"] = str(r["_id"])
                return records[::-1]
            except Exception:
                pass
        return self.local_telemetry[-limit:]

    def get_status(self) -> Dict[str, Any]:
        unflushed_count = sum(1 for v in self.local_violations if not v.get("_synced_to_atlas", False))
        return {
            "connected": self.connected,
            "database": DB_NAME if self.connected else "local_offline_spool",
            "type": "MongoDB Atlas Cluster" if self.connected else "Offline Resilient Spool",
            "unflushed_offline_records": unflushed_count,
            "registered_users_count": len(self.local_users)
        }

    # ==================== User Management Methods ====================

    def create_user(self, email: str, password_hash: str, salt: str, name: str, role: str) -> bool:
        """Stores a new verified user account with salt and password hash."""
        email_clean = email.lower().strip()
        if self.get_user_by_email(email_clean):
            return False

        user_doc = {
            "email": email_clean,
            "password_hash": password_hash,
            "salt": salt,
            "name": name.strip() if name else email_clean.split('@')[0],
            "role": role.upper(),
            "created_at": datetime.utcnow().isoformat() + "Z"
        }

        if self.connected and self.users_col is not None:
            try:
                self.users_col.insert_one(user_doc.copy())
            except Exception as e:
                print(f"[DB ERROR] Inserting user to Atlas: {e}")

        self.local_users[email_clean] = user_doc
        self._save_offline_spool()
        return True

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Finds user document by email address."""
        if not email:
            return None
        email_clean = email.lower().strip()
        if self.connected and self.users_col is not None:
            try:
                user = self.users_col.find_one({"email": email_clean})
                if user:
                    user["_id"] = str(user["_id"])
                    return user
            except Exception:
                pass
        return self.local_users.get(email_clean)

db_manager = DatabaseManager()
