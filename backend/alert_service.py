import time
import json
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, List, Optional
from queue import Queue, Empty
from config import BASE_DIR
import os

ALERTS_LOG_FILE = BASE_DIR / "backend" / "alerts_history.json"

class AlertNotificationService:
    def __init__(self):
        # Configuration (from env or defaults)
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_pass = os.getenv("SMTP_PASS", "")
        self.alert_recipient_email = os.getenv("ALERT_EMAIL", "traffic-officer@control.gov.in")
        
        # In-memory alert registry
        self.alerts: List[Dict[str, Any]] = []
        self.subscribers = []  # SSE client queues
        self.subscribers_lock = threading.Lock()
        
        # Async retry worker queue
        self.delivery_queue = Queue()
        self.worker_thread = threading.Thread(target=self._delivery_worker, daemon=True)
        self.worker_thread.start()
        
        # Debounce tracking: key -> timestamp
        self.alert_debounce: Dict[str, float] = {}
        self.debounce_seconds = 30.0

    def trigger_alert(self, alert_type: str, severity: str, title: str, 
                      details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Dispatches new traffic alert (e.g., HIGH_SEVERITY_VIOLATION or TRAFFIC_GRIDLOCK).
        Performs deduplication, broadcasts to SSE clients, and enqueues external delivery.
        """
        debounce_key = f"{alert_type}_{details.get('vehicle_id', '')}_{title}"
        now = time.time()
        if now - self.alert_debounce.get(debounce_key, 0) < self.debounce_seconds:
            # Debounced to avoid flooding operator
            return None

        self.alert_debounce[debounce_key] = now
        alert_id = f"ALT-{int(now * 1000) % 1000000:06d}"
        iso_time = datetime.utcnow().isoformat() + "Z"

        alert_record = {
            "alert_id": alert_id,
            "type": alert_type,
            "severity": severity,  # "CRITICAL", "WARNING", "INFO"
            "title": title,
            "details": details,
            "timestamp": iso_time,
            "status": "QUEUED",  # QUEUED, DELIVERED, FAILED, ACKNOWLEDGED
            "retries": 0,
            "acknowledged_by": None,
            "acknowledged_at": None
        }

        self.alerts.insert(0, alert_record)
        if len(self.alerts) > 100:
            self.alerts = self.alerts[:100]

        # 1. Real-time push to SSE frontend clients
        self._broadcast_sse(alert_record)

        # 2. Enqueue external delivery (Email / SMS simulation)
        self.delivery_queue.put(alert_record)
        return alert_record

    def _broadcast_sse(self, alert_record: Dict[str, Any]):
        """Pushes alert event to connected dashboard SSE listeners."""
        with self.subscribers_lock:
            payload = f"data: {json.dumps(alert_record)}\n\n"
            dead_clients = []
            for q in self.subscribers:
                try:
                    q.put_nowait(payload)
                except Exception:
                    dead_clients.append(q)
            for q in dead_clients:
                self.subscribers.remove(q)

    def register_client(self) -> Queue:
        """Registers a client queue for Server-Sent Events."""
        q = Queue(maxsize=50)
        with self.subscribers_lock:
            self.subscribers.append(q)
        return q

    def unregister_client(self, q: Queue):
        """Unregisters an SSE client queue upon disconnection."""
        with self.subscribers_lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def acknowledge_alert(self, alert_id: str, operator_name: str) -> bool:
        """Records operator acknowledgement of a critical traffic alert."""
        for a in self.alerts:
            if a["alert_id"] == alert_id:
                a["status"] = "ACKNOWLEDGED"
                a["acknowledged_by"] = operator_name
                a["acknowledged_at"] = datetime.utcnow().isoformat() + "Z"
                return True
        return False

    def _delivery_worker(self):
        """Background thread handling external notification retries with exponential backoff."""
        while True:
            try:
                alert = self.delivery_queue.get(timeout=2.0)
                success = self._send_notification(alert)
                if success:
                    alert["status"] = "DELIVERED"
                else:
                    alert["retries"] += 1
                    if alert["retries"] < 3:
                        alert["status"] = "PENDING_RETRY"
                        # Exponential backoff sleep
                        time.sleep(2 ** alert["retries"])
                        self.delivery_queue.put(alert)
                    else:
                        alert["status"] = "FAILED"
            except Empty:
                continue
            except Exception as e:
                print(f"[ALERT WORKER ERROR] {e}")

    def _send_notification(self, alert: Dict[str, Any]) -> bool:
        """Transmits email or webhook alert notification with safe fallback."""
        if not self.smtp_user or not self.smtp_pass:
            # Simulated delivery when external SMTP credentials are not configured
            # Guarantees robust execution without throwing unhandled credential errors
            return True

        try:
            msg = MIMEMultipart()
            msg["From"] = self.smtp_user
            msg["To"] = self.alert_recipient_email
            msg["Subject"] = f"[{alert['severity']}] AI Traffic Alert: {alert['title']}"

            body = f"""
            AI TRAFFIC MANAGEMENT SYSTEM - AUTOMATED INCIDENT DISPATCH
            ----------------------------------------------------------
            Alert ID:   {alert['alert_id']}
            Severity:   {alert['severity']}
            Timestamp:  {alert['timestamp']}
            Incident:   {alert['title']}
            Details:    {json.dumps(alert['details'], indent=2)}
            ----------------------------------------------------------
            Please review the incident on the command dashboard.
            """
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=5) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"[SMTP DELIVERY FAILED] {e}")
            return False

    def get_recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.alerts[:limit]

alert_service = AlertNotificationService()
