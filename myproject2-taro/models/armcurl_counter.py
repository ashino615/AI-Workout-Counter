# armcurl_counter_simplified.py
"""
Simplified Arm curl counter using elbow angle analysis to detect bicep curl motions.
Measures shoulder-elbow-wrist angle to determine curl position and count reps.
"""

import numpy as np
from typing import Tuple
from collections import deque
from config import config
from utils.logging_utils import logger
from models.workout_counter import ExerciseCounter


class ArmCurlCounter(ExerciseCounter):
    """
    Simplified arm curl repetition counter using elbow angle measurements.
    Tracks arm flexion (curl up) and extension (lower down) to count complete reps.
    """
    
    def __init__(self):
        super().__init__()
        self.angle_history = deque(maxlen=5)  # Reduced buffer size for better responsiveness
        self.state = "down"

        # YOLO keypoint indices for arm angle calculation
        self.R_SHOULDER = 6
        self.R_ELBOW = 8
        self.R_WRIST = 10
        self.L_SHOULDER = 5
        self.L_ELBOW = 7
        self.L_WRIST = 9
        
        # Simplified arm curl angle thresholds (degrees)
        self.up_threshold = getattr(config, "armcurl_up", 90)     # Arms curled up (relaxed threshold)
        self.down_threshold = getattr(config, "armcurl_down", 120) # Arms extended down (relaxed threshold)
        
        logger.info(f"Arm curl thresholds: Up={self.up_threshold}°, Down={self.down_threshold}°")
    
    def calculate_angle(self, a, b, c):
        """
        Calculate angle between three points using vector dot product.
        Returns angle in degrees between vectors ba and bc.
        """
        try:
            v1 = np.array(a[:2]) - np.array(b[:2])
            v2 = np.array(c[:2]) - np.array(b[:2])
            
            # Check for zero vectors
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 < 1e-6 or norm2 < 1e-6:
                return None
            
            cosine = np.dot(v1, v2) / (norm1 * norm2)
            angle = np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))
            
            return angle if 0 <= angle <= 180 else None
            
        except Exception as e:
            logger.warning(f"Error calculating angle: {e}")
            return None
    
    def get_best_arm_angle(self, keypoints):
        """Get the elbow angle from the most confident arm."""
        try:
            # Calculate elbow angles for both arms
            r_angle = self.calculate_angle(
                keypoints[self.R_SHOULDER],
                keypoints[self.R_ELBOW],
                keypoints[self.R_WRIST]
            )
            
            l_angle = self.calculate_angle(
                keypoints[self.L_SHOULDER],
                keypoints[self.L_ELBOW],
                keypoints[self.L_WRIST]
            )
            
            # Determine confidence for each arm based on keypoint visibility
            r_conf = (keypoints[self.R_SHOULDER][2] + keypoints[self.R_ELBOW][2] + keypoints[self.R_WRIST][2]) / 3
            l_conf = (keypoints[self.L_SHOULDER][2] + keypoints[self.L_ELBOW][2] + keypoints[self.L_WRIST][2]) / 3
            
            # Return best angle and confidence
            if r_angle is not None and l_angle is not None:
                # Use arm with higher confidence
                if r_conf >= l_conf:
                    return r_angle, r_conf, "Right"
                else:
                    return l_angle, l_conf, "Left"
            elif r_angle is not None:
                return r_angle, r_conf, "Right"
            elif l_angle is not None:
                return l_angle, l_conf, "Left"
            else:
                return None, 0, "None"
                
        except Exception as e:
            logger.error(f"Error getting arm angle: {e}")
            return None, 0, "Error"
    
    def analyze_pose(self, keypoints: np.ndarray) -> Tuple[int, float]:
        """
        Analyze pose to count arm curls based on elbow angle changes.
        Uses arm with higher confidence score for more reliable measurements.
        """
        if keypoints is None or len(keypoints) == 0:
            return self.count, None
        
        try:
            angle, confidence, arm_side = self.get_best_arm_angle(keypoints)
            
            # Relaxed confidence requirement
            if angle is None or confidence < 0.5:
                return self.count, None
            
            # Apply simple smoothing to reduce noise
            self.angle_history.append(angle)
            
            # Wait for enough samples for stable measurement
            if len(self.angle_history) == self.angle_history.maxlen:
                # Simple average for smoothing
                avg_angle = np.mean(self.angle_history)
                
                # Simple state machine for rep counting
                if avg_angle < self.up_threshold and self.state == "down":
                    self.state = "up"
                    logger.info(f"CURL UP detected at {avg_angle:.1f}° (threshold: {self.up_threshold}°)")
                elif avg_angle > self.down_threshold and self.state == "up":
                    self.count += 1  # Completed full rep (curl -> extend)
                    self.state = "down"
                    logger.info(f"ARM CURL REP #{self.count} completed! Extended to {avg_angle:.1f}°")
                
                return self.count, avg_angle
            
            return self.count, angle
            
        except Exception as e:
            logger.error(f"Error in arm curl analysis: {e}")
            return self.count, None
    
    def reset(self):
        """Reset arm curl counter state to initial values"""
        self.count = 0
        self.state = "down"
        self.angle_history.clear()
        self.frame_count = 0
        logger.info("Arm curl counter reset")
    
    def get_debug_info(self):
        """Get debug information for troubleshooting"""
        return {
            "count": self.count,
            "state": self.state,
            "angle_history_size": len(self.angle_history),
            "up_threshold": self.up_threshold,
            "down_threshold": self.down_threshold,
            "frame_count": self.frame_count
        }