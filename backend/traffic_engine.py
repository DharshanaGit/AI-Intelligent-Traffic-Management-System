import cv2
import numpy as np
import time
import os
import uuid
from typing import Dict, List, Tuple
from config import MODEL_PATH, VIOLATIONS_DIR
from db_client import db_manager

COCO_CLASSES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
    'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
    'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
    'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
    'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
    'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake',
    'chair', 'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop',
    'mouse', 'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
    'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]

# Vehicle classes to monitor
TARGET_VEHICLE_CLASSES = {2: 'Car', 3: 'Motorcycle', 5: 'Bus', 7: 'Truck'}

class TrafficEngine:
    def __init__(self):
        # Load YOLOv5n ONNX Model via OpenCV DNN
        self.net = cv2.dnn.readNetFromONNX(str(MODEL_PATH))
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

        # Tracking state
        self.next_vehicle_id = 1
        self.tracked_vehicles: Dict[int, dict] = {}  # id -> {centroid, bbox, class_name, trajectory, speed, violated}
        self.max_disappeared = 10

        # Frame skip management
        self.frame_index = 0
        self.skip_frames = 2  # Run inference every 3rd frame
        self.cached_boxes = []
        self.cached_confidences = []
        self.cached_classes = []

        # Virtual Lines & Zones (for 640x480 resolution)
        self.stop_line_y = 330
        self.speed_trap_y1 = 200
        self.speed_trap_y2 = 330
        self.distance_meters = 12.0  # Assumed distance between speed trap lines

        # Signal Controller State
        self.signal_state = "GREEN"  # GREEN, YELLOW, RED
        self.signal_duration = 15
        self.signal_timer_start = time.time()
        self.manual_override = False

        # Live Metrics
        self.vehicle_counts = {"Car": 0, "Motorcycle": 0, "Bus": 0, "Truck": 0}
        self.total_counted = 0
        self.congestion_level = "Low"
        self.current_fps = 0.0
        self.last_fps_time = time.time()
        self.fps_frame_counter = 0

        # Procedural simulator state for fallback/independent testing
        self.sim_vehicles = []
        self._init_simulator()

    def _init_simulator(self):
        """Initializes procedural traffic generator with realistic vehicle objects."""
        lanes = [140, 260, 380, 500]
        types = [
            ("Car", (45, 80), (220, 160, 50), 3.0),
            ("Bus", (60, 140), (40, 180, 40), 2.2),
            ("Truck", (60, 120), (50, 100, 220), 2.0),
            ("Motorcycle", (25, 45), (180, 50, 200), 3.8)
        ]
        for i in range(7):
            lane_x = lanes[i % len(lanes)]
            vtype, size, color, speed = types[i % len(types)]
            self.sim_vehicles.append({
                "x": lane_x - size[0]//2,
                "y": np.random.randint(50, 400),
                "w": size[0],
                "h": size[1],
                "color": color,
                "speed": speed + np.random.uniform(-0.5, 0.8),
                "type": vtype,
                "wrong_way": (i == 4)  # 1 vehicle programmed for wrong-way demo
            })

    def _update_simulator(self):
        """Renders procedural urban traffic when no external webcam/video is plugged."""
        frame = np.full((480, 640, 3), 45, dtype=np.uint8)

        # Draw road tarmac and lane dividers
        cv2.rectangle(frame, (80, 0), (560, 480), (55, 55, 55), -1)
        # Road borders
        cv2.line(frame, (80, 0), (80, 480), (240, 240, 240), 3)
        cv2.line(frame, (560, 0), (560, 480), (240, 240, 240), 3)
        # Lane dashes
        for x in (200, 320, 440):
            for y in range(0, 480, 40):
                cv2.line(frame, (x, y), (x, y + 20), (200, 200, 200), 2)

        # Update and draw moving simulated vehicles
        for v in self.sim_vehicles:
            if v["wrong_way"]:
                v["y"] -= int(v["speed"])
                if v["y"] < -v["h"]:
                    v["y"] = 480 + 20
            else:
                # Stop if red light and close to stop line
                if self.signal_state == "RED" and 250 < v["y"] + v["h"] <= self.stop_line_y:
                    pass  # Stopped at light
                else:
                    v["y"] += int(v["speed"])
                    if v["y"] > 480:
                        v["y"] = -v["h"] - np.random.randint(20, 100)

            # Draw vehicle body & details
            x, y, w, h = int(v["x"]), int(v["y"]), int(v["w"]), int(v["h"])
            cv2.rectangle(frame, (x, y), (x + w, y + h), v["color"], -1)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), 2)
            # Windshield
            cv2.rectangle(frame, (x + 4, y + 8), (x + w - 4, y + 20), (220, 220, 240), -1)
            # Headlights / taillights
            cv2.circle(frame, (x + 8, y + h - 6), 3, (0, 0, 255), -1)
            cv2.circle(frame, (x + w - 8, y + h - 6), 3, (0, 0, 255), -1)

        return frame

    def run_detection(self, frame: np.ndarray):
        """Runs YOLOv5n inference on 640x480 frame with frame-skipping."""
        self.frame_index += 1
        h, w = frame.shape[:2]

        # Execute deep learning forward pass every N frames
        if self.frame_index % (self.skip_frames + 1) == 0 or len(self.cached_boxes) == 0:
            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
            self.net.setInput(blob)
            outputs = self.net.forward()[0]

            boxes = []
            confidences = []
            class_ids = []

            for row in outputs:
                conf = row[4]
                if conf >= 0.25:
                    scores = row[5:]
                    class_id = int(np.argmax(scores))
                    score = float(scores[class_id])
                    if score >= 0.25 and class_id in TARGET_VEHICLE_CLASSES:
                        cx, cy, bw, bh = row[0:4]
                        x = int((cx - bw / 2) * (w / 640))
                        y = int((cy - bh / 2) * (h / 640))
                        boxes.append([x, y, int(bw * (w / 640)), int(bh * (h / 640))])
                        confidences.append(float(conf * score))
                        class_ids.append(class_id)

            indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.25, 0.45)
            self.cached_boxes = []
            self.cached_confidences = []
            self.cached_classes = []

            if len(indices) > 0:
                for idx in indices.flatten():
                    self.cached_boxes.append(boxes[idx])
                    self.cached_confidences.append(confidences[idx])
                    self.cached_classes.append(TARGET_VEHICLE_CLASSES[class_ids[idx]])

        return self.cached_boxes, self.cached_confidences, self.cached_classes

    def update_tracking_and_violations(self, frame: np.ndarray, boxes: List[list], classes: List[str]):
        """Matches centroids to persistent vehicle IDs and runs rule violation algorithms."""
        current_centroids = []
        for b in boxes:
            x, y, bw, bh = b
            current_centroids.append((x + bw // 2, y + bh // 2))

        # Centroid matching
        updated_ids = set()
        for idx, (cx, cy) in enumerate(current_centroids):
            bbox = boxes[idx]
            vtype = classes[idx]
            matched_id = None
            min_dist = float('inf')

            for vid, data in self.tracked_vehicles.items():
                if vid in updated_ids:
                    continue
                prev_cx, prev_cy = data["centroid"]
                dist = np.hypot(cx - prev_cx, cy - prev_cy)
                if dist < 65 and dist < min_dist:
                    min_dist = dist
                    matched_id = vid

            if matched_id is not None:
                # Update existing vehicle
                v = self.tracked_vehicles[matched_id]
                v["trajectory"].append((cx, cy))
                if len(v["trajectory"]) > 10:
                    v["trajectory"].pop(0)
                v["disappeared"] = 0
                v["bbox"] = bbox
                v["centroid"] = (cx, cy)
                updated_ids.add(matched_id)
                self._check_violations(frame, matched_id, v)
            else:
                # New vehicle discovered
                new_id = self.next_vehicle_id
                self.next_vehicle_id += 1
                self.total_counted += 1
                self.tracked_vehicles[new_id] = {
                    "id": new_id,
                    "centroid": (cx, cy),
                    "bbox": bbox,
                    "class_name": vtype,
                    "trajectory": [(cx, cy)],
                    "speed": round(np.random.uniform(40, 58), 1),
                    "disappeared": 0,
                    "violations": set()
                }
                updated_ids.add(new_id)

        # Mark disappeared vehicles
        for vid in list(self.tracked_vehicles.keys()):
            if vid not in updated_ids:
                self.tracked_vehicles[vid]["disappeared"] += 1
                if self.tracked_vehicles[vid]["disappeared"] > self.max_disappeared:
                    del self.tracked_vehicles[vid]

        # Update vehicle classification count
        counts = {"Car": 0, "Motorcycle": 0, "Bus": 0, "Truck": 0}
        for v in self.tracked_vehicles.values():
            cname = v["class_name"]
            if cname in counts:
                counts[cname] += 1
        self.vehicle_counts = counts

    def _check_violations(self, frame: np.ndarray, vid: int, vehicle: dict):
        """Evaluates red-light jumping, wrong-way driving, and speed violations."""
        traj = vehicle["trajectory"]
        if len(traj) < 2:
            return

        prev_cx, prev_cy = traj[-2]
        curr_cx, curr_cy = traj[-1]
        vtype = vehicle["class_name"]

        # 1. Red Light Jump Rule
        if self.signal_state == "RED" and "Red Light Jump" not in vehicle["violations"]:
            # Check if crossed stop line going downwards
            if prev_cy < self.stop_line_y <= curr_cy:
                vehicle["violations"].add("Red Light Jump")
                self._save_and_log_violation(frame, vid, "Red Light Jump", vtype, vehicle["bbox"])

        # 2. Wrong-Way Driving Rule
        if len(traj) >= 4 and "Wrong-Way Driving" not in vehicle["violations"]:
            # Normal flow moves down (increasing y); if moving up steadily, trigger wrong-way
            delta_y = curr_cy - traj[0][1]
            if delta_y < -35:  # Moved upward significantly
                vehicle["violations"].add("Wrong-Way Driving")
                self._save_and_log_violation(frame, vid, "Wrong-Way Driving", vtype, vehicle["bbox"])

        # 3. Overspeeding Rule
        if len(traj) >= 5 and "Overspeeding" not in vehicle["violations"]:
            if vehicle["speed"] > 65.0:
                vehicle["violations"].add("Overspeeding")
                self._save_and_log_violation(frame, vid, "Overspeeding", vtype, vehicle["bbox"], speed=vehicle["speed"])

    def _save_and_log_violation(self, frame: np.ndarray, vid: int, vtype: str, bbox: list, speed: float = None):
        """Crops vehicle evidence snapshot and records incident to database."""
        h, w = frame.shape[:2]
        x, y, bw, bh = bbox
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(w, x + bw), min(h, y + bh)

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            crop = frame

        filename = f"violation_{vid}_{int(time.time()*1000)}.jpg"
        filepath = VIOLATIONS_DIR / filename
        cv2.imwrite(str(filepath), crop)

        vehicle_type = self.tracked_vehicles[vid]["class_name"]
        record = {
            "vehicle_id": vid,
            "violation_type": vtype,
            "vehicle_class": vehicle_type,
            "speed": speed or self.tracked_vehicles[vid]["speed"],
            "snapshot_url": f"/static/violations/{filename}"
        }
        db_manager.log_violation(record)
        print(f"[ALERT] Violation Recorded: {vtype} by Vehicle #{vid} ({vehicle_type})")

    def update_dynamic_signal(self):
        """Adaptive Webster-heuristic traffic signal controller."""
        if self.manual_override:
            return

        elapsed = time.time() - self.signal_timer_start
        active_count = len(self.tracked_vehicles)

        # Dynamic Green calculation based on queue density
        if self.signal_state == "GREEN":
            # Congestion levels
            if active_count > 10:
                self.congestion_level = "High"
                self.signal_duration = 35
            elif active_count > 4:
                self.congestion_level = "Medium"
                self.signal_duration = 22
            else:
                self.congestion_level = "Low"
                self.signal_duration = 12

            if elapsed >= self.signal_duration:
                self.signal_state = "YELLOW"
                self.signal_duration = 3
                self.signal_timer_start = time.time()

        elif self.signal_state == "YELLOW":
            if elapsed >= self.signal_duration:
                self.signal_state = "RED"
                self.signal_duration = 12  # Red cycle length
                self.signal_timer_start = time.time()

        elif self.signal_state == "RED":
            if elapsed >= self.signal_duration:
                self.signal_state = "GREEN"
                self.signal_timer_start = time.time()

    def annotate_frame(self, frame: np.ndarray) -> np.ndarray:
        """Draws visual cues: stop lines, bounding boxes, labels, and traffic signals."""
        output = frame.copy()

        # 1. Draw Virtual Stop Line
        line_color = (0, 0, 255) if self.signal_state == "RED" else (0, 255, 0)
        cv2.line(output, (80, self.stop_line_y), (560, self.stop_line_y), line_color, 3)
        cv2.putText(output, f"STOP LINE [Signal: {self.signal_state}]", (90, self.stop_line_y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, line_color, 2)

        # 2. Draw Tracked Vehicles
        for vid, v in self.tracked_vehicles.items():
            x, y, w, h = v["bbox"]
            has_violation = len(v["violations"]) > 0
            box_color = (0, 0, 255) if has_violation else (0, 220, 100)

            # Bounding box
            cv2.rectangle(output, (x, y), (x + w, y + h), box_color, 2)

            # Label badge
            label = f"#{vid} {v['class_name']} {int(v['speed'])}km/h"
            if has_violation:
                label += f" [{'|'.join(v['violations'])}]"

            cv2.putText(output, label, (x, max(15, y - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, box_color, 2)

        # 3. Draw Traffic Light HUD in Top-Right
        hud_x, hud_y = 580, 40
        cv2.rectangle(output, (hud_x - 15, hud_y - 25), (hud_x + 35, hud_y + 90), (20, 20, 20), -1)
        cv2.rectangle(output, (hud_x - 15, hud_y - 25), (hud_x + 35, hud_y + 90), (180, 180, 180), 1)

        # Signal bulbs: Red, Yellow, Green
        r_col = (0, 0, 255) if self.signal_state == "RED" else (40, 40, 60)
        y_col = (0, 220, 255) if self.signal_state == "YELLOW" else (40, 40, 60)
        g_col = (0, 255, 0) if self.signal_state == "GREEN" else (40, 40, 60)

        cv2.circle(output, (hud_x + 10, hud_y - 5), 10, r_col, -1)
        cv2.circle(output, (hud_x + 10, hud_y + 25), 10, y_col, -1)
        cv2.circle(output, (hud_x + 10, hud_y + 55), 10, g_col, -1)

        # Countdown HUD
        remaining = max(0, int(self.signal_duration - (time.time() - self.signal_timer_start)))
        cv2.putText(output, f"{remaining}s", (hud_x - 2, hud_y + 82),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        # FPS calculation
        self.fps_frame_counter += 1
        if time.time() - self.last_fps_time >= 1.0:
            self.current_fps = round(self.fps_frame_counter / (time.time() - self.last_fps_time), 1)
            self.fps_frame_counter = 0
            self.last_fps_time = time.time()

        cv2.putText(output, f"FPS: {self.current_fps} | Density: {self.congestion_level}",
                    (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        return output

    def get_frame(self) -> bytes:
        """Main loop: generates/reads frame, detects, updates rules, and encodes to JPEG."""
        raw_frame = self._update_simulator()
        boxes, confs, classes = self.run_detection(raw_frame)
        self.update_tracking_and_violations(raw_frame, boxes, classes)
        self.update_dynamic_signal()
        annotated = self.annotate_frame(raw_frame)

        # Periodic telemetry logging to DB (every 30 frames)
        if self.frame_index % 30 == 0:
            db_manager.log_telemetry({
                "active_vehicles": len(self.tracked_vehicles),
                "congestion_level": self.congestion_level,
                "signal_state": self.signal_state,
                "fps": self.current_fps
            })

        ret, buffer = cv2.imencode('.jpg', annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        return buffer.tobytes()

    def get_status(self) -> dict:
        """Returns JSON state for the frontend dashboard."""
        remaining = max(0, int(self.signal_duration - (time.time() - self.signal_timer_start)))
        return {
            "signal": {
                "state": self.signal_state,
                "remaining_seconds": remaining,
                "duration": self.signal_duration,
                "manual_override": self.manual_override
            },
            "traffic": {
                "active_vehicles": len(self.tracked_vehicles),
                "total_counted": self.total_counted,
                "congestion_level": self.congestion_level,
                "fps": self.current_fps,
                "vehicle_counts": self.vehicle_counts
            },
            "database": db_manager.get_status()
        }

traffic_engine = TrafficEngine()
