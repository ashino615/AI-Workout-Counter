import argparse
from pathlib import Path
from typing import Optional

class Config:
    """
    Central configuration manager for the AI Fitness Coach application.
    Handles command-line argument parsing, debug modes, and exercise parameters.
    """
    
    def __init__(self):
        # Application mode settings
        self.debug_mode: str = "debug"
        self.save_frames: bool = False
        self.debug_dir: Optional[Path] = None
        
        # Pose detection thresholds
        self.min_confidence: float = 0.3  # Minimum keypoint confidence required
        self.model_conf_threshold: float = 0.4  # YOLO model confidence threshold
        
        # Exercise counting parameters
        self.rep_cooldown: float = 0.5  # Seconds between rep detections to prevent double counting
        self.min_consecutive_frames: int = 3  # Frames needed to confirm movement direction
        self.movement_threshold: int = 4  # Minimum pixel movement to register direction change
        self.min_movement_range: int = 15  # Minimum range for valid rep completion
        
        # Image processing settings
        self.image_width_limit: int = 640  # Resize images larger than this for performance
        
        # Exercise mode configuration
        self.supported_modes = ["chinup", "pushup", "squat", "armcurl"]
        
        # Human-readable descriptions for each debug mode
        self.mode_descriptions = {
            "debug": "Debug Mode (with frame saving)",
            "debug_no_save": "Debug Mode (without frame saving)", 
            "non_debug": "Non-Debug Mode (minimal logging)"
        }
    
    def setup_from_args(self):
        """
        Parse command line arguments and configure application settings.
        Creates debug directory if frame saving is enabled.
        """
        parser = argparse.ArgumentParser(description="AI Fitness Coach Backend")
        parser.add_argument(
            "--mode", 
            choices=["debug", "debug_no_save", "non_debug"],
            default="debug_no_save",
            help="Debug mode setting"
        )
        args = parser.parse_args()
        
        self.debug_mode = args.mode
        self.save_frames = (self.debug_mode == "debug")
        
        # Create debug frame directory if needed
        if self.save_frames:
            self.debug_dir = Path("debug_frames")
            self.debug_dir.mkdir(exist_ok=True)
    
    @property
    def mode_description(self) -> str:
        """Get human-readable description of current mode"""
        return self.mode_descriptions[self.debug_mode]

# Global configuration instance - import this in other modules
config = Config()