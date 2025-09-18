# tuned_push_up_counter.py
"""
Tuned push-up counter based on your video analysis results.
Adjusted thresholds and reduced minimum frame requirements for better detection.
"""

import numpy as np
from typing import Tuple, Optional
from collections import deque
from enum import Enum

# Mock dependencies if not available
try:
    from config import config
    from utils.logging_utils import logger
    from models.workout_counter import ExerciseCounter
except ImportError:
    class MockLogger:
        @staticmethod
        def info(msg): print(f"[INFO] {msg}")
        @staticmethod
        def error(msg): print(f"[ERROR] {msg}")
        @staticmethod
        def warning(msg): print(f"[WARNING] {msg}")
    
    class MockExerciseCounter:
        def __init__(self):
            self.count = 0
            self.frame_count = 0
    
    logger = MockLogger()
    ExerciseCounter = MockExerciseCounter


class PushUpState(Enum):
    """Simplified states for push-up movement tracking"""
    UP = "up"
    DOWN = "down"
    TRANSITION = "transition"


class PushUpCounter(ExerciseCounter):
    """
    Push-up counter tuned based on your video analysis.
    """
    
    def __init__(self):
        super().__init__()
        self.state = PushUpState.UP
        self.last_state_change = 0
        
        # Smaller buffer for more responsive detection
        self.angle_history = deque(maxlen=3)  # Reduced from 5
        
        # YOLO keypoint indices
        self.R_SHOULDER = 6
        self.R_ELBOW = 8
        self.R_WRIST = 10
        self.L_SHOULDER = 5
        self.L_ELBOW = 7
        self.L_WRIST = 9
        
        # TUNED THRESHOLDS based on your video results
        # Your angle range was 83.3° - 171.9°, average 131.9°
        self.UP_ANGLE_THRESHOLD = 135      # Lowered from 140° (was too high)
        self.DOWN_ANGLE_THRESHOLD = 105    # Raised from 90° (catches more reps)
        self.HYSTERESIS = 5                # Smaller hysteresis for more sensitivity
        
        # Movement validation - MORE RESPONSIVE
        self.MIN_CONFIDENCE = 0.3          # Lowered from 0.4
        self.MIN_FRAMES_IN_STATE = 2       # Reduced from 3 (faster transitions)
        self.MAX_ANGLE_CHANGE = 50         # Increased to allow bigger changes
        
        # Counting logic
        self.went_down = False
        
        logger.info(f"🎯 Tuned thresholds: Up={self.UP_ANGLE_THRESHOLD}°, Down={self.DOWN_ANGLE_THRESHOLD}°")
    
    def calculate_angle(self, shoulder, elbow, wrist):
        """Calculate elbow angle between shoulder-elbow-wrist."""
        try:
            # Vectors from elbow to shoulder and elbow to wrist
            vec1 = np.array([shoulder[0] - elbow[0], shoulder[1] - elbow[1]])
            vec2 = np.array([wrist[0] - elbow[0], wrist[1] - elbow[1]])
            
            # Handle zero vectors
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 < 1e-6 or norm2 < 1e-6:
                return None
                
            # Calculate angle
            cosine = np.dot(vec1, vec2) / (norm1 * norm2)
            cosine = np.clip(cosine, -1.0, 1.0)
            angle = np.degrees(np.arccos(cosine))
            
            return angle
            
        except Exception as e:
            logger.warning(f"Error calculating angle: {e}")
            return None
    
    def get_best_arm_angle(self, keypoints):
        """Get the elbow angle from the most confident arm."""
        try:
            # Check confidence for both arms
            r_confidence = (keypoints[self.R_SHOULDER][2] + 
                           keypoints[self.R_ELBOW][2] + 
                           keypoints[self.R_WRIST][2]) / 3
            
            l_confidence = (keypoints[self.L_SHOULDER][2] + 
                           keypoints[self.L_ELBOW][2] + 
                           keypoints[self.L_WRIST][2]) / 3
            
            # Calculate angles
            r_angle = None
            l_angle = None
            
            if r_confidence >= self.MIN_CONFIDENCE:
                r_angle = self.calculate_angle(
                    keypoints[self.R_SHOULDER],
                    keypoints[self.R_ELBOW], 
                    keypoints[self.R_WRIST]
                )
            
            if l_confidence >= self.MIN_CONFIDENCE:
                l_angle = self.calculate_angle(
                    keypoints[self.L_SHOULDER],
                    keypoints[self.L_ELBOW],
                    keypoints[self.L_WRIST]
                )
            
            # Return best angle and confidence
            if r_angle is not None and l_angle is not None:
                # Use average if both arms are detected with similar confidence
                if abs(r_confidence - l_confidence) < 0.1:
                    return (r_angle + l_angle) / 2, (r_confidence + l_confidence) / 2
                # Use more confident arm
                elif r_confidence > l_confidence:
                    return r_angle, r_confidence
                else:
                    return l_angle, l_confidence
            elif r_angle is not None:
                return r_angle, r_confidence
            elif l_angle is not None:
                return l_angle, l_confidence
            else:
                return None, 0
                
        except Exception as e:
            logger.error(f"Error getting arm angle: {e}")
            return None, 0
    
    def smooth_angle(self, angle):
        """Apply minimal smoothing - more responsive than original."""
        if angle is None:
            return None
            
        # More lenient filtering of extreme changes
        if len(self.angle_history) > 0:
            last_angle = self.angle_history[-1]
            if abs(angle - last_angle) > self.MAX_ANGLE_CHANGE:
                logger.warning(f"Large angle change: {last_angle:.1f} -> {angle:.1f}")
                # Don't filter as aggressively - allow some large changes
        
        self.angle_history.append(angle)
        
        # Less aggressive smoothing - use most recent values
        if len(self.angle_history) >= 2:
            return np.mean(list(self.angle_history)[-2:])  # Average of last 2 values
        else:
            return angle
    
    def update_state_and_count(self, angle):
        """Updated state machine with more sensitive thresholds."""
        if angle is None:
            return
        
        frames_in_current_state = self.frame_count - self.last_state_change
        
        # Shorter minimum frames requirement for faster response
        if frames_in_current_state < self.MIN_FRAMES_IN_STATE:
            return
        
        # More sensitive state machine
        if self.state == PushUpState.UP:
            # Transition to DOWN when angle decreases below threshold
            if angle < self.DOWN_ANGLE_THRESHOLD:
                self._change_state(PushUpState.DOWN)
                self.went_down = True
                logger.info(f"🔽 DOWN detected at {angle:.1f}° (threshold: {self.DOWN_ANGLE_THRESHOLD}°)")
        
        elif self.state == PushUpState.DOWN:
            # Transition to UP when angle increases above threshold
            if angle > self.UP_ANGLE_THRESHOLD:
                self._change_state(PushUpState.UP)
                
                # Count rep only if we went down first
                if self.went_down:
                    self.count += 1
                    self.went_down = False
                    logger.info(f"✅ REP #{self.count}! UP at {angle:.1f}° (threshold: {self.UP_ANGLE_THRESHOLD}°)")
                else:
                    logger.info(f"🔼 UP detected but no prior DOWN")
    
    def _change_state(self, new_state):
        """Change state and update tracking."""
        if new_state != self.state:
            old_state = self.state.value
            self.state = new_state
            self.last_state_change = self.frame_count
            logger.info(f"State: {old_state} → {new_state.value}")
    
    def analyze_pose(self, keypoints: np.ndarray) -> Tuple[int, Optional[float]]:
        """
        Main analysis function - tuned for your video characteristics.
        """
        self.frame_count += 1
        
        if keypoints is None or len(keypoints) == 0:
            return self.count, None
        
        try:
            # Get best arm angle
            angle, confidence = self.get_best_arm_angle(keypoints)
            
            if angle is None or confidence < self.MIN_CONFIDENCE:
                return self.count, None
            
            # Apply minimal smoothing
            smoothed_angle = self.smooth_angle(angle)
            
            if smoothed_angle is None:
                return self.count, None
            
            # Update state and count with new thresholds
            self.update_state_and_count(smoothed_angle)
            
            # More frequent debug logging to catch issues
            if self.frame_count % 10 == 0:  # Every 10 frames
                logger.info(f"📊 Frame {self.frame_count}: Angle={smoothed_angle:.1f}°, State={self.state.value}, Count={self.count}")
            
            return self.count, smoothed_angle
            
        except Exception as e:
            logger.error(f"Error in push-up analysis: {e}")
            return self.count, None
    
    def reset(self):
        """Reset counter to initial state."""
        self.count = 0
        self.state = PushUpState.UP
        self.frame_count = 0
        self.last_state_change = 0
        self.went_down = False
        self.angle_history.clear()
        
        logger.info("🔄 Push-up counter reset with tuned thresholds")
    
    def get_debug_info(self):
        """Get current debug information."""
        return {
            'count': self.count,
            'state': self.state.value,
            'went_down': self.went_down,
            'frames_in_state': self.frame_count - self.last_state_change,
            'angle_buffer_size': len(self.angle_history),
            'thresholds': {
                'up': self.UP_ANGLE_THRESHOLD,
                'down': self.DOWN_ANGLE_THRESHOLD,
                'hysteresis': self.HYSTERESIS
            },
            'settings': {
                'min_confidence': self.MIN_CONFIDENCE,
                'min_frames_in_state': self.MIN_FRAMES_IN_STATE,
                'max_angle_change': self.MAX_ANGLE_CHANGE
            }
        }
    
    def adjust_thresholds(self, up_threshold=None, down_threshold=None):
        """Allow runtime threshold adjustment for testing."""
        if up_threshold is not None:
            self.UP_ANGLE_THRESHOLD = up_threshold
            logger.info(f"🎯 Up threshold adjusted to {up_threshold}°")
        
        if down_threshold is not None:
            self.DOWN_ANGLE_THRESHOLD = down_threshold  
            logger.info(f"🎯 Down threshold adjusted to {down_threshold}°")