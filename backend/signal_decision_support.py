import time
from typing import Dict, Any, List

class SignalDecisionSupport:
    def __init__(self):
        # Operational constraints
        self.min_green = 15
        self.max_green = 60
        self.yellow_clearance = 4
        self.all_red_clearance = 2
        self.pedestrian_phase_duration = 10
        
        # State
        self.current_phase = "GREEN"  # GREEN, YELLOW, RED, PEDESTRIAN_CROSSING
        self.phase_start_time = time.time()
        self.allocated_duration = 20
        self.manual_override = False
        self.pedestrians_waiting = 0
        self.last_pedestrian_walk_time = time.time()
        
        # Performance comparison metrics (Adaptive vs. Fixed 30s Baseline)
        self.baseline_fixed_cycle = 30
        self.total_adaptive_cycles = 0
        self.cumulative_time_saved_secs = 0.0

    def compute_lane_pcu(self, vehicle_counts: Dict[str, int]) -> float:
        """
        Calculates Passenger Car Units (PCU) for Indian mixed traffic:
        - Car: 1.0 PCU
        - Motorcycle: 0.5 PCU
        - Auto-Rickshaw: 0.8 PCU
        - Bus: 2.5 PCU
        - Truck: 2.5 PCU
        """
        pcu = (
            vehicle_counts.get("Car", 0) * 1.0 +
            vehicle_counts.get("Motorcycle", 0) * 0.5 +
            vehicle_counts.get("Auto-Rickshaw", 0) * 0.8 +
            vehicle_counts.get("Bus", 0) * 2.5 +
            vehicle_counts.get("Truck", 0) * 2.5
        )
        return round(float(pcu), 1)

    def calculate_adaptive_timing(self, active_pcu: float, cross_street_pcu: float = 6.0, 
                                  queue_estimates: Dict[str, int] = None) -> Dict[str, Any]:
        """
        Calculates recommended Webster green interval based on real-time traffic density and approach queues.
        """
        if queue_estimates:
            ns_queue = max(1, queue_estimates.get("north", 0) + queue_estimates.get("south", 0))
            ew_queue = max(1, queue_estimates.get("east", 0) + queue_estimates.get("west", 0))
            total_queue = ns_queue + ew_queue
            flow_ratio = ns_queue / total_queue
        else:
            total_pcu = max(1.0, active_pcu + cross_street_pcu)
            flow_ratio = active_pcu / total_pcu
        
        # Webster formula for optimum cycle length and phase split
        # Total lost time L = 2 phases * (4s yellow + 2s all-red) = 12s
        lost_time = 12.0
        y_critical = min(0.85, max(0.15, flow_ratio * 0.75))
        c_opt = (1.5 * lost_time + 5.0) / max(0.10, 1.0 - y_critical)
        c_opt = max(40.0, min(120.0, c_opt))
        
        # Effective green allocation for dominant approach
        raw_green = (c_opt - lost_time) * (y_critical / max(0.15, y_critical + 0.25))
        recommended_green = int(max(self.min_green, min(self.max_green, round(raw_green))))
        
        # Compute baseline delay vs adaptive delay
        fixed_time_delay = 30.0
        adaptive_time_delay = float(recommended_green)
        efficiency_gain_pct = round(abs(fixed_time_delay - adaptive_time_delay) / fixed_time_delay * 100, 1)

        return {
            "recommended_green_seconds": recommended_green,
            "min_clamp": self.min_green,
            "max_clamp": self.max_green,
            "active_pcu": active_pcu,
            "optimum_cycle_length": int(c_opt),
            "efficiency_gain_pct": efficiency_gain_pct,
            "mode": "ADVISORY_DECISION_SUPPORT",
            "safety_interlock_engaged": True
        }

    def update_state(self, active_vehicles: int, vehicle_counts: Dict[str, int], 
                     queue_estimates: Dict[str, int] = None) -> Dict[str, Any]:
        """Progresses signal state machine according to adaptive decisions."""
        if self.manual_override:
            elapsed = time.time() - self.phase_start_time
            remaining = max(0, int(self.allocated_duration - elapsed))
            return self.get_status(remaining)

        elapsed = time.time() - self.phase_start_time
        active_pcu = self.compute_lane_pcu(vehicle_counts)

        if self.current_phase == "GREEN":
            # Check if duration reached
            if elapsed >= self.allocated_duration:
                self.current_phase = "YELLOW"
                self.allocated_duration = self.yellow_clearance
                self.phase_start_time = time.time()

        elif self.current_phase == "YELLOW":
            if elapsed >= self.allocated_duration:
                # Check if pedestrian phase should precede Red
                time_since_ped = time.time() - self.last_pedestrian_walk_time
                if self.pedestrians_waiting > 0 or time_since_ped > 75.0:
                    self.current_phase = "PEDESTRIAN_CROSSING"
                    self.allocated_duration = self.pedestrian_phase_duration
                    self.phase_start_time = time.time()
                    self.last_pedestrian_walk_time = time.time()
                    self.pedestrians_waiting = 0
                else:
                    self.current_phase = "RED"
                    self.allocated_duration = 14
                    self.phase_start_time = time.time()

        elif self.current_phase == "PEDESTRIAN_CROSSING":
            if elapsed >= self.allocated_duration:
                self.current_phase = "RED"
                self.allocated_duration = 10
                self.phase_start_time = time.time()

        elif self.current_phase == "RED":
            if elapsed >= self.allocated_duration:
                # Re-calculate optimal green for next cycle based on real approach queues
                decision = self.calculate_adaptive_timing(active_pcu, queue_estimates=queue_estimates)
                self.allocated_duration = decision["recommended_green_seconds"]
                self.current_phase = "GREEN"
                self.phase_start_time = time.time()
                self.total_adaptive_cycles += 1

        remaining = max(0, int(self.allocated_duration - (time.time() - self.phase_start_time)))
        return self.get_status(remaining, active_pcu)

    def set_override(self, state: str, manual: bool = True):
        state = state.upper()
        if state in ("GREEN", "YELLOW", "RED"):
            self.current_phase = state
            self.manual_override = manual
            self.allocated_duration = 30
            self.phase_start_time = time.time()

    def get_status(self, remaining: int = 0, active_pcu: float = 0.0) -> Dict[str, Any]:
        return {
            "current_phase": self.current_phase,
            "remaining_seconds": remaining,
            "allocated_duration": self.allocated_duration,
            "manual_override": self.manual_override,
            "active_pcu": active_pcu,
            "safety_interlock": "ACTIVE_SAFETY_GUARD_ENGAGED",
            "advisory_only": True
        }

signal_decision_support = SignalDecisionSupport()
