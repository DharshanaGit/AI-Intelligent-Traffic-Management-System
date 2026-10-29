import cv2
import numpy as np
from typing import Tuple, Optional, List

class PerspectiveCalibration:
    def __init__(self):
        # Default 4-point road plane in pixels (for 640x480 resolution)
        # Bottom-left, Bottom-right, Top-right, Top-left
        self.src_points = np.float32([
            [100, 460],  # Bottom Left
            [540, 460],  # Bottom Right
            [410, 240],  # Top Right
            [230, 240]   # Top Left
        ])
        
        # Real-world metric dimensions (in meters)
        # 12 meters road width, 25 meters longitudinal trap
        self.dst_points = np.float32([
            [0.0, 25.0],
            [12.0, 25.0],
            [12.0, 0.0],
            [0.0, 0.0]
        ])
        
        self.is_calibrated = True
        self.H_matrix = None
        self._compute_homography()

    def _compute_homography(self):
        try:
            self.H_matrix = cv2.getPerspectiveTransform(self.src_points, self.dst_points)
            self.is_calibrated = True
        except Exception as e:
            self.is_calibrated = False
            self.H_matrix = None
            print(f"[CALIBRATION ERROR] Failed computing homography matrix: {e}")

    def update_points(self, src_pts: List[List[float]], dst_pts: Optional[List[List[float]]] = None):
        """Updates calibration points dynamically."""
        if len(src_pts) == 4:
            self.src_points = np.float32(src_pts)
            if dst_pts and len(dst_pts) == 4:
                self.dst_points = np.float32(dst_pts)
            self._compute_homography()

    def is_inside_trap(self, px: float, py: float) -> bool:
        """Verifies if pixel point lies within calibrated road quadrilateral."""
        if self.src_points is None or len(self.src_points) != 4:
            return False
        pts = self.src_points.reshape((-1, 1, 2)).astype(np.int32)
        return cv2.pointPolygonTest(pts, (float(px), float(py)), False) >= 0

    def pixel_to_world(self, px: float, py: float) -> Optional[Tuple[float, float]]:
        """Converts pixel coordinate (x, y) to real-world ground coordinate (X_meters, Y_meters)."""
        if not self.is_calibrated or self.H_matrix is None:
            return None
        
        # Guard against unbounded points outside calibration zone
        if not self.is_inside_trap(px, py):
            return None
        
        pt = np.array([[[px, py]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, self.H_matrix)
        world_x, world_y = transformed[0][0]
        return float(world_x), float(world_y)

    def calculate_speed_kmh(self, pt1: Tuple[float, float], pt2: Tuple[float, float], delta_time: float) -> Optional[float]:
        """Calculates calibrated vehicle velocity in km/h between two pixel points over time."""
        if delta_time <= 0.001 or not self.is_calibrated:
            return None

        w1 = self.pixel_to_world(pt1[0], pt1[1])
        w2 = self.pixel_to_world(pt2[0], pt2[1])
        if w1 is None or w2 is None:
            return None

        dx = w2[0] - w1[0]
        dy = w2[1] - w1[1]
        distance_meters = np.hypot(dx, dy)
        speed_mps = distance_meters / delta_time
        speed_kmh = speed_mps * 3.6
        return round(float(speed_kmh), 1)

calibration_engine = PerspectiveCalibration()
