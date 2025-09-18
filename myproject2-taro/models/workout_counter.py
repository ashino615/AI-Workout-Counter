# Workout_counter.py
"""
Main workout counter that manages different exercise-specific counters.
Uses composition pattern to delegate analysis to specialized counter implementations.
"""

from typing import Optional, Tuple, Dict, Any
from abc import ABC, abstractmethod
import numpy as np
from config import config
from utils.logging_utils import logger

class ExerciseCounter(ABC):
    """
    Abstract base class defining interface for all exercise-specific counters.
    Provides common properties and enforces implementation of core analysis methods.
    """
    
    def __init__(self):
        self.count = 0
        self.frame_count = 0
    
    @abstractmethod
    def analyze_pose(self, keypoints: np.ndarray) -> Tuple[int, Any]:
        """Analyze pose keypoints and return (rep_count, exercise_state)"""
        pass
    
    @abstractmethod
    def reset(self):
        """Reset counter to initial state"""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get current counter status for debugging"""
        return {
            "count": self.count,
            "frame_count": self.frame_count
        }


class WorkoutCounter:
    """
    Main workout coordinator that delegates to exercise-specific counter implementations.
    Handles mode switching, session management, and provides unified interface for all exercises.
    """
    
    def __init__(self, mode: str = "chinup"):
        self.mode = mode
        self.counter: Optional[ExerciseCounter] = None
        self.frame_count = 0  
        self._initialize_counter(mode)
        logger.info(f"WorkoutCounter initialized with mode: {mode}")
    
    def _initialize_counter(self, mode: str):
        """
        Factory method to create appropriate counter instance based on exercise mode.
        Imports are done locally to avoid circular import issues.
        """
        from models.pull_up_counter import PullUpCounter
        from models.push_up_counter import PushUpCounter
        from models.squat_counter import SquatCounter
        from models.armcurl_counter import ArmCurlCounter
        
        counters = {
            "chinup": PullUpCounter,
            "pullup": PullUpCounter,  # Alias for chinup
            "pushup": PushUpCounter,
            "squat": SquatCounter,
            "armcurl": ArmCurlCounter
        }
        
        counter_class = counters.get(mode)
        if counter_class:
            self.counter = counter_class()
            logger.info(f"Initialized {counter_class.__name__} for mode: {mode}")
        else:
            logger.warning(f"Unknown mode: {mode}, defaulting to PullUpCounter")
            self.counter = PullUpCounter()
            self.mode = "chinup"
    
    @property
    def count(self) -> int:
        """Get current repetition count"""
        if self.counter:
            return self.counter.count
        return 0
    
    def update(self, keypoints: np.ndarray) -> Tuple[int, Any]:
        """
        Process new frame keypoints through exercise-specific counter.
        Returns: (rep_count, exercise_specific_data)
        """
        if self.counter is None:
            logger.error("No counter initialized")
            return 0, None
        
        # Track frame processing
        self.counter.frame_count += 1
        self.frame_count = self.counter.frame_count
        
        # Delegate to specific exercise counter
        return self.counter.analyze_pose(keypoints)
    
    def reset(self):
        """Reset current counter state to initial values"""
        if self.counter:
            self.counter.reset()
            self.frame_count = 0
            logger.info(f"Reset {self.mode} counter")
    
    def switch_mode(self, new_mode: str):
        """Change exercise mode and reinitialize appropriate counter"""
        if new_mode != self.mode:
            self.mode = new_mode
            self._initialize_counter(new_mode)
            self.frame_count = 0
            logger.info(f"Switched to {new_mode} mode")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive workout status for debugging"""
        if self.counter:
            status = self.counter.get_status()
            status["mode"] = self.mode
            return status
        return {"mode": self.mode, "count": 0, "frame_count": 0}

