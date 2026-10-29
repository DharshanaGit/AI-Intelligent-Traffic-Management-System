import cv2
import numpy as np
import time
import threading
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
from config import MODEL_PATH
from video_manager import video_source_manager
from calibration_engine import calibration_engine
from anpr_evidence import anpr_evidence_manager
from signal_decision_support import signal_decision_support
from db_client import db_manager
from alert_service import alert_service

# Target vehicle classes from standard COCO
TARGET_VEHICLE_CLASSES = {
    0: 'Person',
    1: 'Bicycle',
    2: 'Car',
    3: 'Motorcycle',
    5: 'Bus',
    7: 'Truck'
}

class TrafficEngine:
    def __init__(self):
        # Load YOLOv5n ONNX Model via OpenCV DNN
        self.net = cv2.dnn.readNetFromONNX(str(MODEL_PATH))
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

        # Multi-Object Tracker State
        self.next_vehicle_id = 1
        self.tracked_vehicles: Dict[int, dict] = {}
        self.max_disappeared = 12

        # Frame Skipping for High CPU FPS
        self.frame_index = 0
        self.skip_frames = 2  # Run inference every 3rd frame
        self.cached_boxes = []
        self.cached_confidences = []
        self.cached_classes = []

        # Geometry & Road Boundaries (Polygonal Stop-Line Zone)
        self.stop_line_p1 = (90, 340)
        self.stop_line_p2 = (550, 340)
        
        # Debounce / Deduplication map: (vid, vtype) -> timestamp
        self.violation_debounce: Dict[str, float] = {}
        self.debounce_window_seconds = 15.0

        # Live Metrics
        self.vehicle_counts = {"Car": 0, "Motorcycle": 0, "Auto-Rickshaw": 0, "Bus": 0, "Truck": 0, "Person": 0}
        self.total_counted = 0
        self.congestion_level = "Low"
        self.current_fps = 0.0
        self.last_fps_time = time.time()
        self.fps_frame_counter = 0

        # Continuous Pipeline State & Worker
        self.is_paused = False
        self.is_stopped = False
        self.latency_ms = 35.0
        self.last_frame_processed_time = datetime.utcnow().isoformat() + "Z"
        self.queue_estimates = {"north": 0, "south": 0, "east": 0, "west": 0}
        self.latest_frame_jpeg: bytes = b""
        self.latest_raw_frame = None
        self.latest_meta: Dict[str, Any] = {}
        self.lock = threading.Lock()
        self.net_lock = threading.Lock()

        # Start continuous background AI ingestion worker
        self.worker_thread = threading.Thread(target=self._background_pipeline_worker, daemon=True)
        self.worker_thread.start()

    def _letterbox(self, img: np.ndarray, target_size=(640, 640)) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        """Letterboxes frame with symmetric padding to preserve true aspect ratio."""
        h, w = img.shape[:2]
        tw, th = target_size
        scale = min(tw / w, th / h)
        nw, nh = int(round(w * scale)), int(round(h * scale))
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        top = (th - nh) // 2
        bottom = th - nh - top
        left = (tw - nw) // 2
        right = tw - nw - left
        padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
        return padded, scale, (left, top)

    def run_detection(self, frame: np.ndarray):
        """Runs YOLOv5n ONNX inference with aspect-ratio preserving letterboxing."""
        self.frame_index += 1
        h, w = frame.shape[:2]

        if self.frame_index % (self.skip_frames + 1) == 0 or len(self.cached_boxes) == 0:
            padded_img, scale, (pad_left, pad_top) = self._letterbox(frame, (640, 640))
            with self.net_lock:
                blob = cv2.dnn.blobFromImage(padded_img, 1/255.0, (640, 640), swapRB=True, crop=False)
                self.net.setInput(blob)
                outputs = self.net.forward()[0]

            boxes = []
            confidences = []
            class_ids = []

            for row in outputs:
                conf = row[4]
                if conf >= 0.28:
                    scores = row[5:]
                    class_id = int(np.argmax(scores))
                    score = float(scores[class_id])
                    if score >= 0.28 and class_id in TARGET_VEHICLE_CLASSES:
                        cx, cy, bw, bh = row[0:4]
                        # Inverse letterbox transformation
                        orig_cx = (cx - pad_left) / scale
                        orig_cy = (cy - pad_top) / scale
                        orig_bw = bw / scale
                        orig_bh = bh / scale
                        x = int(max(0, orig_cx - orig_bw / 2))
                        y = int(max(0, orig_cy - orig_bh / 2))
                        boxes.append([x, y, int(orig_bw), int(orig_bh)])
                        confidences.append(float(conf * score))
                        class_ids.append(class_id)

            indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.28, 0.45)
            self.cached_boxes = []
            self.cached_confidences = []
            self.cached_classes = []

            if len(indices) > 0:
                for idx in indices.flatten():
                    bbox = boxes[idx]
                    raw_class = TARGET_VEHICLE_CLASSES[class_ids[idx]]
                    # Indian Traffic Harmonization: Documented Auto-Rickshaw geometric heuristic
                    # Note: Pre-trained COCO lacks native 3-wheeler class.
                    # Evaluated on narrow track, compact envelope, aspect ratio ~0.60-0.85
                    bw, bh = bbox[2], bbox[3]
                    aspect = float(bw) / float(bh) if bh > 0 else 1.0
                    if raw_class in ("Car", "Motorcycle") and 0.60 <= aspect <= 0.85 and 2000 < (bw * bh) < 12000:
                        refined_class = "Auto-Rickshaw"
                    else:
                        refined_class = raw_class

                    self.cached_boxes.append(bbox)
                    self.cached_confidences.append(confidences[idx])
                    self.cached_classes.append(refined_class)

        return self.cached_boxes, self.cached_confidences, self.cached_classes

    def update_tracking(self, frame: np.ndarray, boxes: List[list], classes: List[str]):
        """Associates detections with persistent vehicle IDs using velocity-guided trajectory projection."""
        current_centroids = []
        for b in boxes:
            x, y, bw, bh = b
            current_centroids.append((x + bw // 2, y + bh // 2))

        updated_ids = set()
        now = time.time()

        for idx, (cx, cy) in enumerate(current_centroids):
            bbox = boxes[idx]
            vtype = classes[idx]
            matched_id = None
            min_dist = float('inf')

            for vid, data in self.tracked_vehicles.items():
                if vid in updated_ids:
                    continue
                prev_cx, prev_cy = data["centroid"]
                vx, vy = data.get("velocity", (0.0, 0.0))
                # Predict centroid based on velocity vector
                pred_cx = prev_cx + vx
                pred_cy = prev_cy + vy
                dist = np.hypot(cx - pred_cx, cy - pred_cy)
                
                # Adaptive matching threshold
                match_limit = max(60.0, min(140.0, float(bbox[2]) * 1.3))
                if dist < match_limit and dist < min_dist:
                    min_dist = dist
                    matched_id = vid

            if matched_id is not None:
                # Update tracklet
                v = self.tracked_vehicles[matched_id]
                prev_pt = v["centroid"]
                prev_time = v.get("last_seen_time", now - 0.04)
                dt = max(0.02, now - prev_time)
                
                # Update velocity vector
                v["velocity"] = (cx - prev_pt[0], cy - prev_pt[1])
                
                # Calibrated Speed Calculation via Perspective Homography
                calibrated_speed = calibration_engine.calculate_speed_kmh(prev_pt, (cx, cy), dt)
                if calibrated_speed is not None and 5.0 <= calibrated_speed <= 140.0:
                    v["speed"] = calibrated_speed

                v["trajectory"].append((cx, cy))
                if len(v["trajectory"]) > 10:
                    v["trajectory"].pop(0)
                v["bbox"] = bbox
                v["centroid"] = (cx, cy)
                v["last_seen_time"] = now
                v["disappeared"] = 0
                updated_ids.add(matched_id)

                # Check virtual tripwire for single ground-truth counting
                if not v.get("counted", False) and prev_pt[1] < 280 <= cy:
                    v["counted"] = True
                    self.total_counted += 1

                self._check_violations(frame, matched_id, v)
            else:
                # New vehicle tracklet
                new_id = self.next_vehicle_id
                self.next_vehicle_id += 1
                self.tracked_vehicles[new_id] = {
                    "id": new_id,
                    "centroid": (cx, cy),
                    "velocity": (0.0, 0.0),
                    "bbox": bbox,
                    "class_name": vtype,
                    "trajectory": [(cx, cy)],
                    "speed": None,
                    "last_seen_time": now,
                    "disappeared": 0,
                    "counted": False,
                    "violations": set()
                }
                updated_ids.add(new_id)

        # Age-out disappeared vehicles
        for vid in list(self.tracked_vehicles.keys()):
            if vid not in updated_ids:
                self.tracked_vehicles[vid]["disappeared"] += 1
                if self.tracked_vehicles[vid]["disappeared"] > self.max_disappeared:
                    del self.tracked_vehicles[vid]

        # Aggregate counts
        counts = {"Car": 0, "Motorcycle": 0, "Auto-Rickshaw": 0, "Bus": 0, "Truck": 0, "Person": 0}
        for v in self.tracked_vehicles.values():
            cname = v["class_name"]
            if cname in counts:
                counts[cname] += 1
        self.vehicle_counts = counts

    def _check_violations(self, frame: np.ndarray, vid: int, vehicle: dict):
        """Evaluates rule violations with deduplication and evidence generation."""
        traj = vehicle["trajectory"]
        if len(traj) < 2:
            return

        now = time.time()
        prev_cx, prev_cy = traj[-2]
        curr_cx, curr_cy = traj[-1]
        vtype = vehicle["class_name"]
        signal_state = signal_decision_support.current_phase

        # 1. Red Light Jumping Rule
        debounce_key_red = f"{vid}_RED_LIGHT"
        if signal_state == "RED" and now - self.violation_debounce.get(debounce_key_red, 0) > self.debounce_window_seconds:
            # Check crossing of stop-line
            if prev_cy < self.stop_line_p1[1] <= curr_cy:
                self.violation_debounce[debounce_key_red] = now
                vehicle["violations"].add("Red Light Jump")
                self._record_evidence(frame, vid, "Red Light Jump", vtype, vehicle["bbox"], vehicle.get("speed"))

        # 2. Wrong-Way Driving Rule
        debounce_key_ww = f"{vid}_WRONG_WAY"
        if len(traj) >= 5 and now - self.violation_debounce.get(debounce_key_ww, 0) > self.debounce_window_seconds:
            # Downward is normal (+y). If moving steadily upward (-y), trigger wrong-way
            delta_y = curr_cy - traj[0][1]
            if delta_y < -38:
                self.violation_debounce[debounce_key_ww] = now
                vehicle["violations"].add("Wrong-Way Driving")
                self._record_evidence(frame, vid, "Wrong-Way Driving", vtype, vehicle["bbox"], vehicle.get("speed"))

        # 3. Overspeeding Rule (Requires Calibrated Homography Speed)
        debounce_key_speed = f"{vid}_SPEED"
        speed = vehicle.get("speed")
        if speed and speed > 60.0 and now - self.violation_debounce.get(debounce_key_speed, 0) > self.debounce_window_seconds:
            self.violation_debounce[debounce_key_speed] = now
            vehicle["violations"].add("Overspeeding")
            self._record_evidence(frame, vid, "Overspeeding", vtype, vehicle["bbox"], speed)

    def _record_evidence(self, frame: np.ndarray, vid: int, vtype: str, 
                         vclass: str, bbox: list, speed: Optional[float] = None):
        """Seals evidence with SHA-256 and ANPR extraction, saving to database."""
        evidence_record = anpr_evidence_manager.seal_and_store_evidence(
            frame=frame,
            vid=vid,
            vtype=vtype,
            vehicle_type=vclass,
            bbox=bbox,
            speed=speed
        )
        db_manager.log_violation(evidence_record)
        print(f"[EVIDENCE STORED] #{evidence_record['evidence_id']} - {vtype} by {vclass} (Plate: {evidence_record['license_plate']})")

        # Trigger real-time alert dispatch
        alert_service.trigger_alert(
            alert_type="TRAFFIC_VIOLATION",
            severity="CRITICAL" if vtype == "Red Light Jump" else "WARNING",
            title=f"{vtype} - {vclass} (#{vid})",
            details={
                "evidence_id": evidence_record["evidence_id"],
                "vehicle_id": vid,
                "vehicle_class": vclass,
                "license_plate": evidence_record["license_plate"],
                "speed_kmh": speed,
                "violation_type": vtype
            }
        )

    def annotate_frame(self, frame: np.ndarray, meta: Dict[str, Any]) -> np.ndarray:
        """Annotates frame with source health banner, calibration zones, vehicle tracking and signal HUD."""
        out = frame.copy()
        current_signal = signal_decision_support.current_phase

        # 1. Truthful Stream Status Top Banner
        mode_str = meta.get("mode", "UNKNOWN")
        health_str = meta.get("health", "HEALTHY")
        is_sim = meta.get("is_simulation", False)
        
        banner_color = (0, 0, 160) if is_sim else ((0, 140, 0) if health_str == "HEALTHY" else (0, 0, 200))
        cv2.rectangle(out, (0, 0), (640, 26), banner_color, -1)
        
        source_label = f"SOURCE: {mode_str} | HEALTH: {health_str} | CALIBRATION: {'ACTIVE' if calibration_engine.is_calibrated else 'DISABLED'}"
        cv2.putText(out, source_label, (12, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1)

        # 2. Virtual Stop-Line with Signal Awareness
        line_col = (0, 0, 255) if current_signal == "RED" else (0, 255, 0)
        cv2.line(out, self.stop_line_p1, self.stop_line_p2, line_col, 2)
        cv2.putText(out, f"STOP LINE [{current_signal}]", (self.stop_line_p1[0], self.stop_line_p1[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, line_col, 2)

        # 3. Tracked Vehicles Annotations
        for vid, v in self.tracked_vehicles.items():
            x, y, w, h = v["bbox"]
            has_violation = len(v["violations"]) > 0
            box_col = (0, 0, 255) if has_violation else (0, 220, 120)

            cv2.rectangle(out, (x, y), (x + w, y + h), box_col, 2)
            speed_txt = f"{int(v['speed'])}km/h" if v.get("speed") else "Tracking"
            label = f"#{vid} {v['class_name']} ({speed_txt})"
            if has_violation:
                label += f" [{'|'.join(v['violations'])}]"

            cv2.putText(out, label, (x, max(16, y - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, box_col, 1)

        # 4. Traffic Signal HUD (Top-Right)
        hud_x, hud_y = 575, 45
        cv2.rectangle(out, (hud_x - 10, hud_y - 15), (hud_x + 45, hud_y + 85), (25, 25, 25), -1)
        cv2.rectangle(out, (hud_x - 10, hud_y - 15), (hud_x + 45, hud_y + 85), (160, 160, 160), 1)

        r_col = (0, 0, 255) if current_signal == "RED" else (50, 50, 70)
        y_col = (0, 220, 255) if current_signal == "YELLOW" else (50, 50, 70)
        g_col = (0, 255, 0) if current_signal == "GREEN" else (50, 50, 70)

        cv2.circle(out, (hud_x + 18, hud_y + 5), 8, r_col, -1)
        cv2.circle(out, (hud_x + 18, hud_y + 28), 8, y_col, -1)
        cv2.circle(out, (hud_x + 18, hud_y + 51), 8, g_col, -1)

        status_sig = signal_decision_support.get_status()
        cv2.putText(out, f"{status_sig.get('remaining_seconds', 0)}s", (hud_x + 8, hud_y + 78),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1)

        # FPS calculation
        self.fps_frame_counter += 1
        if time.time() - self.last_fps_time >= 1.0:
            self.current_fps = round(self.fps_frame_counter / (time.time() - self.last_fps_time), 1)
            self.fps_frame_counter = 0
            self.last_fps_time = time.time()

        return out

    def _calculate_queue_estimates(self):
        """Estimates queue lengths per intersection approach based on spatial centroids."""
        north, south, east, west = 0, 0, 0, 0
        for vid, v in self.tracked_vehicles.items():
            cx, cy = v["centroid"]
            speed = v.get("speed", 0.0)
            if speed < 25.0:
                if cy < 240 and cx < 320:
                    north += 1
                elif cy >= 240 and cx < 320:
                    south += 1
                elif cy < 240 and cx >= 320:
                    east += 1
                else:
                    west += 1
            else:
                if cy < 240:
                    north += 1
                else:
                    south += 1
        self.queue_estimates = {"north": north, "south": south, "east": east, "west": west}

    def control_stream(self, action: str) -> Dict[str, Any]:
        """Manages video stream state: play, pause, resume, stop, reconnect."""
        act = action.lower().strip()
        if act == "pause":
            self.is_paused = True
            return {"success": True, "action": "pause", "status": "PAUSED"}
        elif act in ("resume", "play"):
            self.is_paused = False
            self.is_stopped = False
            return {"success": True, "action": "play", "status": "PLAYING"}
        elif act == "stop":
            self.is_stopped = True
            return {"success": True, "action": "stop", "status": "STOPPED"}
        elif act == "reconnect":
            self.is_stopped = False
            self.is_paused = False
            res = video_source_manager.reconnect()
            return {"success": True, "action": "reconnect", "result": res}
        return {"success": False, "error": f"Unknown control action: {action}"}

    def _background_pipeline_worker(self):
        """Continuous pipeline loop ensuring instant frame availability and uninterrupted telemetry."""
        while True:
            try:
                if self.is_stopped:
                    stopped_frame = np.full((480, 640, 3), 20, dtype=np.uint8)
                    cv2.putText(stopped_frame, "STREAM INGESTION STOPPED", (140, 240),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
                    ret, buffer = cv2.imencode('.jpg', stopped_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                    if ret:
                        with self.lock:
                            self.latest_frame_jpeg = buffer.tobytes()
                    time.sleep(0.2)
                    continue

                if self.is_paused:
                    time.sleep(0.1)
                    continue

                t0 = time.time()
                raw_frame, meta = video_source_manager.read_frame(is_authenticated=True)
                if raw_frame is not None:
                    boxes, confs, classes = self.run_detection(raw_frame)
                    self.update_tracking(raw_frame, boxes, classes)
                    self._calculate_queue_estimates()
                    signal_decision_support.update_state(len(self.tracked_vehicles), self.vehicle_counts, queue_estimates=self.queue_estimates)
                    annotated = self.annotate_frame(raw_frame, meta)

                    ret, buffer = cv2.imencode('.jpg', annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                    if ret:
                        with self.lock:
                            self.latest_frame_jpeg = buffer.tobytes()
                            self.latest_raw_frame = raw_frame
                            self.latest_meta = meta
                            self.last_frame_processed_time = datetime.utcnow().isoformat() + "Z"
                            self.latency_ms = round((time.time() - t0) * 1000.0, 1)

                    if self.frame_index % 30 == 0:
                        db_manager.log_telemetry({
                            "active_vehicles": len(self.tracked_vehicles),
                            "vehicle_counts": self.vehicle_counts,
                            "congestion_pcu": signal_decision_support.compute_lane_pcu(self.vehicle_counts),
                            "signal_phase": signal_decision_support.current_phase,
                            "stream_health": meta.get("health", "HEALTHY"),
                            "fps": self.current_fps,
                            "latency_ms": self.latency_ms
                        })

                # Regulate to ~25 FPS to maintain smooth feed while preserving CPU
                dt = time.time() - t0
                if dt < 0.04:
                    time.sleep(0.04 - dt)
            except Exception as e:
                time.sleep(0.05)

    def get_frame(self, is_authenticated: bool = True) -> bytes:
        """Main pipeline execution loop for live video streaming."""
        with self.lock:
            if self.latest_frame_jpeg:
                return self.latest_frame_jpeg

        # Fallback if initial background frame not yet ready
        raw_frame, meta = video_source_manager.read_frame(is_authenticated=is_authenticated)
        ret, buffer = cv2.imencode('.jpg', raw_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        return buffer.tobytes()

    def get_status(self) -> dict:
        """Assembles verified real-time status payload for dashboard."""
        meta_source = {
            "mode": video_source_manager.mode,
            "source_path": video_source_manager.source_path,
            "health": video_source_manager.health_status,
            "measured_fps": self.current_fps,
            "is_simulation": (video_source_manager.mode == "SIMULATION"),
            "is_paused": self.is_paused,
            "is_stopped": self.is_stopped,
            "last_processed": self.last_frame_processed_time,
            "latency_ms": self.latency_ms
        }
        sig_status = signal_decision_support.get_status()

        return {
            "source": meta_source,
            "signal": sig_status,
            "traffic": {
                "active_vehicles": len(self.tracked_vehicles),
                "total_counted": self.total_counted,
                "vehicle_counts": self.vehicle_counts,
                "current_pcu": signal_decision_support.compute_lane_pcu(self.vehicle_counts),
                "fps": self.current_fps,
                "latency_ms": self.latency_ms,
                "queue_estimates": self.queue_estimates,
                "last_update": self.last_frame_processed_time
            },
            "calibration": {
                "calibrated": calibration_engine.is_calibrated,
                "metric_trap_meters": 25.0
            },
            "database": db_manager.get_status()
        }

traffic_engine = TrafficEngine()
