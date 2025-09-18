# pull_up_counter.py
"""
Pull-up counter using motion-based detection of vertical movement patterns.
Tracks wrist-to-shoulder distance changes to identify up/down movement phases.
"""

import time
import numpy as np
from typing import Tuple
from collections import deque
from config import config
from utils.logging_utils import logger
from models.workout_counter import ExerciseCounter


class PullUpCounter(ExerciseCounter):
    """
    Pull-up repetition counter using motion analysis of wrist-shoulder relationship.
    Detects upward and downward movement phases with confirmation requirements.
    """
    
    def __init__(self):
        super().__init__()
        self.position = "neutral"
        
        # Movement tracking for smoothing and direction detection
        self.position_history = deque(maxlen=30)
        self.direction_history = deque(maxlen=10)
        
        # Rep counting state management
        self.last_rep_time = 0
        
        # Movement direction tracking
        self.current_direction = "stable"
        self.consecutive_up_frames = 0
        self.consecutive_down_frames = 0
        
        # YOLO keypoint indices for pull-up analysis
        self.L_SHOULDER = 5
        self.R_SHOULDER = 6
        self.L_WRIST = 9
        self.R_WRIST = 10
    
    def detect_direction_change(self, current_diff: float) -> Tuple[str, float]:
        """
        Analyze movement direction with confirmation requirements to avoid noise.
        Uses hysteresis and consecutive frame confirmation for reliable detection.
        """
        self.position_history.append(current_diff)
        
        if len(self.position_history) < 5:
            return "starting", 0
        
        # Analyze recent movement trend
        recent = list(self.position_history)[-5:]
        movement = recent[-1] - recent[0]
        
        # Determine direction with movement threshold
        new_direction = "stable"
        if movement > config.movement_threshold:  # Moving up
            new_direction = "up"
        elif movement < -config.movement_threshold:  # Moving down
            new_direction = "down"
        
        # Update consecutive frame counters for confirmation
        if new_direction == "up":
            self.consecutive_up_frames += 1
            self.consecutive_down_frames = 0
        elif new_direction == "down":
            self.consecutive_down_frames += 1
            self.consecutive_up_frames = 0
        else:
            # Gradually decay counters when no clear direction
            if self.consecutive_up_frames > 0:
                self.consecutive_up_frames = max(0, self.consecutive_up_frames - 0.5)
            if self.consecutive_down_frames > 0:
                self.consecutive_down_frames = max(0, self.consecutive_down_frames - 0.5)
        
        # Confirm direction only after minimum consecutive frames
        confirmed_direction = self.current_direction
        if self.consecutive_up_frames >= config.min_consecutive_frames:
            confirmed_direction = "up"
        elif self.consecutive_down_frames >= config.min_consecutive_frames:
            confirmed_direction = "down"
        elif self.consecutive_up_frames == 0 and self.consecutive_down_frames == 0:
            confirmed_direction = "stable"
        
        # Log direction changes for debugging
        if confirmed_direction != self.current_direction:
            self.direction_history.append((confirmed_direction, time.time(), current_diff))
            self.current_direction = confirmed_direction
            
            if config.debug_mode != "non_debug":
                logger.info(f"Pull-up direction: {self.current_direction.upper()} (diff: {current_diff:.1f})")
        
        return confirmed_direction, abs(movement)
    
    def analyze_pose(self, keypoints: np.ndarray) -> Tuple[int, str]:
        """
        Analyze pose keypoints to count pull-up repetitions based on movement patterns.
        Looks for DOWN -> UP sequences with sufficient movement range to confirm valid reps.
        """
        if keypoints is None or len(keypoints) == 0:
            return self.count, "no_person"
            
        try:
            # Extract relevant keypoints
            left_shoulder = keypoints[self.L_SHOULDER]
            right_shoulder = keypoints[self.R_SHOULDER]
            left_wrist = keypoints[self.L_WRIST]
            right_wrist = keypoints[self.R_WRIST]
            
            # Validate keypoint confidence levels
            min_confidence = min(
                left_shoulder[2], right_shoulder[2], 
                left_wrist[2], right_wrist[2]
            )
            if min_confidence < config.min_confidence:
                return self.count, "low_confidence"
            
            # Calculate wrist-shoulder vertical relationship
            shoulder_y = (left_shoulder[1] + right_shoulder[1]) / 2
            wrist_y = (left_wrist[1] + right_wrist[1]) / 2
            wrist_shoulder_diff = wrist_y - shoulder_y
            
            # Detect movement direction
            direction, magnitude = self.detect_direction_change(wrist_shoulder_diff)
            
            # Rep counting logic - detect DOWN -> UP pattern completion
            current_time = time.time()
            if current_time - self.last_rep_time > config.rep_cooldown:
                
                if len(self.direction_history) >= 2:
                    recent_changes = list(self.direction_history)[-2:]
                    
                    # Look for complete pull-up cycle: DOWN -> UP
                    if (len(recent_changes) == 2 and 
                        recent_changes[0][0] == "down" and 
                        recent_changes[1][0] == "up"):
                        
                        # Validate sufficient movement range for valid rep
                        down_diff = recent_changes[0][2]
                        up_diff = recent_changes[1][2]
                        movement_range = abs(up_diff - down_diff)
                        
                        if movement_range > config.min_movement_range:
                            self.count += 1
                            self.last_rep_time = current_time
                            
                            if config.debug_mode != "non_debug":
                                logger.info(f"Pull-up REP {self.count} completed!")
                            
                            # Clear history to prevent double counting
                            self.direction_history.clear()
            
            # Set user-friendly position description
            if direction == "up":
                self.position = "pulling_up"
            elif direction == "down": 
                self.position = "lowering_down"
            else:
                self.position = "stable"
            
            return self.count, self.position
            
        except Exception as e:
            logger.error(f"Error in pull-up analysis: {e}")
            return self.count, "error"
    
    def reset(self):
        """Reset all pull-up counter state to initial values"""
        self.count = 0
        self.position = "neutral"
        self.position_history.clear()
        self.direction_history.clear()
        self.last_rep_time = 0
        self.current_direction = "stable"
        self.consecutive_up_frames = 0
        self.consecutive_down_frames = 0
        self.frame_count = 0
        logger.info("Pull-up counter reset")