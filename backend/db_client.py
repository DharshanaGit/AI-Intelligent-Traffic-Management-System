import os
import time
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure, ConfigurationError
from config import MONGO_URI, DB_NAME

class DatabaseManager:
    def __init__(self):
        self.connected = False
        self.client = None
        self.db = None
        self.violations_col = None
        self.telemetry_col = None
        self.local_violations = []
        self.local_telemetry = []
        self._init_connection()

    def _init_connection(self):
        # Defensively check if password placeholder is still present
        if not MONGO_URI or "<db_password>" in MONGO_URI:
            print("[INFO] MongoDB Atlas URI contains placeholder '<db_password>'.")
            print("[INFO] To sync with your remote MongoDB cluster, replace '<db_password>' in your .env file.")
            print("[INFO] Operating in high-speed local memory/cache mode without errors.")
            return

        try:
            # Set short timeout so server startup is never delayed if offline
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[DB_NAME]
            self.violations_col = self.db["violations"]
            self.telemetry_col = self.db["traffic_telemetry"]
            self.connected = True
            print("[SUCCESS] Connected securely to MongoDB Atlas database:", DB_NAME)
        except (ConnectionFailure, OperationFailure, ConfigurationError) as err:
            self.connected = False
            print("[WARNING] Could not establish MongoDB Atlas connection. Running in local fallback mode.")
            print(f"[REASON] {type(err).__name__}")
        except Exception as e:
            self.connected = False
            print(f"[WARNING] MongoDB fallback active: {type(e).__name__}")

    def log_violation(self, violation: dict):
        violation["timestamp"] = datetime.utcnow().isoformat() + "Z"
        if self.connected and self.violations_col is not None:
            try:
                result = self.violations_col.insert_one(violation.copy())
                violation["_id"] = str(result.inserted_id)
                return violation
            except Exception as e:
                print(f"[ERROR] Failed writing violation to MongoDB: {e}")
        
        # Local fallback
        violation["_id"] = f"local_{int(time.time()*1000)}"
        self.local_violations.insert(0, violation)
        # Cap local violations to last 100 to save memory
        if len(self.local_violations) > 100:
            self.local_violations = self.local_violations[:100]
        return violation

    def get_recent_violations(self, limit: int = 25):
        if self.connected and self.violations_col is not None:
            try:
                records = list(self.violations_col.find().sort("_id", -1).limit(limit))
                for r in records:
                    r["_id"] = str(r["_id"])
                return records
            except Exception as e:
                print(f"[ERROR] Error fetching violations from MongoDB: {e}")
        return self.local_violations[:limit]

    def log_telemetry(self, telemetry: dict):
        telemetry["timestamp"] = datetime.utcnow().isoformat() + "Z"
        if self.connected and self.telemetry_col is not None:
            try:
                self.telemetry_col.insert_one(telemetry.copy())
            except Exception:
                pass
        
        self.local_telemetry.append(telemetry)
        if len(self.local_telemetry) > 60:
            self.local_telemetry = self.local_telemetry[-60:]

    def get_telemetry_history(self, limit: int = 30):
        if self.connected and self.telemetry_col is not None:
            try:
                records = list(self.telemetry_col.find().sort("_id", -1).limit(limit))
                for r in records:
                    r["_id"] = str(r["_id"])
                return records[::-1]
            except Exception:
                pass
        return self.local_telemetry[-limit:]

    def get_status(self):
        return {
            "connected": self.connected,
            "database": DB_NAME if self.connected else "local_memory_cache",
            "type": "MongoDB Atlas" if self.connected else "Offline Buffer"
        }

db_manager = DatabaseManager()
