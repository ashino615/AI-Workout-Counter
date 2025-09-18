# squat_counter.py
"""
Improved Squat counter using simplified angle analysis for reliable counting.
Uses knee angle measurements with a 2-state system for consistent rep detection.
"""

import numpy as np
from typing import Tuple, Optional
from collections import deque
from config import config
from utils.logging_utils import logger
from models.workout_counter import ExerciseCounter


class SquatCounter(ExerciseCounter):
    """
    Squat repetition counter using knee angle measurements.
    Simplified 2-state system for reliable counting.
    """
    
    def __init__(self):
        super().__init__()
        self.state = "up"  # up (standing) or down (squatting)
        self.angle_history = deque(maxlen=3)  # Shorter buffer for responsiveness
        
        # YOLO keypoint indices
        self.R_HIP = 12
        self.R_KNEE = 14
        self.R_ANKLE = 16
        self.L_HIP = 11
        self.L_KNEE = 13
        self.L_ANKLE = 15
        
        # Simplified thresholds - more aggressive for reliable counting
        self.up_threshold = getattr(config, "squat_up", 170)    # Standing (knees straight)
        self.down_threshold = getattr(config, "squat_down", 140)  # Squatting (knees bent)
        
        # Movement tracking
        self.went_down = False
        self.last_state_change = 0
        self.min_frames_in_state = 2  # Minimal frame requirement
    
    def calculate_angle(self, a, b, c):
        """
        Calculate angle between three points using vector dot product.
        Returns angle in degrees between vectors ba and bc.
        """
        try:
            v1 = np.array(a[:2]) - np.array(b[:2])
            v2 = np.array(c[:2]) - np.array(b[:2])
            
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 < 1e-6 or norm2 < 1e-6:
                return None
                
            cosine = np.dot(v1, v2) / (norm1 * norm2)
            angle = np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))
            return angle
        except:
            return None
    
    def get_best_leg_angle(self, keypoints):
        """Get knee angle from the most confident leg."""
        try:
            # Calculate knee angles for both legs
            r_angle = self.calculate_angle(
                keypoints[self.R_HIP],
                keypoints[self.R_KNEE],
                keypoints[self.R_ANKLE]
            )
            
            l_angle = self.calculate_angle(
                keypoints[self.L_HIP],
                keypoints[self.L_KNEE],
                keypoints[self.L_ANKLE]
            )
            
            # Calculate confidence for each leg
            r_conf = (keypoints[self.R_HIP][2] + keypoints[self.R_KNEE][2] + keypoints[self.R_ANKLE][2]) / 3
            l_conf = (keypoints[self.L_HIP][2] + keypoints[self.L_KNEE][2] + keypoints[self.L_ANKLE][2]) / 3
            
            # Use leg with higher confidence, or average if both are good
            if r_conf >= 0.3 and l_conf >= 0.3:
                if abs(r_angle - l_angle) < 30:  # Legs moving in sync
                    return (r_angle + l_angle) / 2, (r_conf + l_conf) / 2
                else:  # Use more confident leg
                    return r_angle if r_conf >= l_conf else l_angle, max(r_conf, l_conf)
            elif r_conf >= 0.3:
                return r_angle, r_conf
            elif l_conf >= 0.3:
                return l_angle, l_conf
            else:
                return None, 0
                
        except Exception as e:
            logger.error(f"Error getting leg angle: {e}")
            return None, 0
    
    def analyze_pose(self, keypoints: np.ndarray) -> Tuple[int, Optional[float]]:
        """
        Analyze pose to count squats based on knee angle changes.
        Uses simplified 2-state system for reliable counting.
        """
        self.frame_count += 1
        
        if keypoints is None or len(keypoints) == 0:
            return self.count, None
        
        try:
            # Get best knee angle
            angle, confidence = self.get_best_leg_angle(keypoints)
            
            if angle is None or confidence < 0.3:
                return self.count, None
            
            # Apply minimal smoothing
            self.angle_history.append(angle)
            if len(self.angle_history) >= 2:
                avg_angle = np.mean(list(self.angle_history)[-2:])  # Average last 2 values
            else:
                avg_angle = angle
            
            # Check minimum frames in current state
            frames_in_current_state = self.frame_count - self.last_state_change
            if frames_in_current_state < self.min_frames_in_state:
                return self.count, avg_angle
            
            # Simple 2-state machine: up <-> down
            if self.state == "up" and avg_angle < self.down_threshold:
                # Transition to squat down
                self.state = "down"
                self.went_down = True
                self.last_state_change = self.frame_count
                logger.info(f"Squat DOWN detected at {avg_angle:.1f}° (threshold: {self.down_threshold}°)")
                
            elif self.state == "down" and avg_angle > self.up_threshold:
                # Transition to standing up - count rep if we went down first
                self.state = "up"
                self.last_state_change = self.frame_count
                
                if self.went_down:
                    self.count += 1
                    self.went_down = False
                    logger.info(f"Squat REP #{self.count} completed! UP at {avg_angle:.1f}°")
                else:
                    logger.info(f"UP detected but no prior DOWN")
            
            return self.count, avg_angle
            
        except Exception as e:
            logger.error(f"Error in squat analysis: {e}")
            return self.count, None
    
    def reset(self):
        """Reset squat counter state to initial values"""
        self.count = 0
        self.state = "up"
        self.angle_history.clear()
        self.frame_count = 0
        self.went_down = False
        self.last_state_change = 0
        logger.info("Squat counter reset")