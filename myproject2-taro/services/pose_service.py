import cv2
import numpy as np
from ultralytics import YOLO
from utils.logging_utils import logger
from config import config

class PoseService:
    """
    YOLO-based pose detection service for exercise analysis.
    Handles model initialization, image preprocessing, and keypoint extraction.
    """
    
    def __init__(self):
        self.model = None
    
    async def initialize(self):
        """
        Initialize YOLO pose detection model and perform warm-up inference.
        Loads YOLOv8 nano pose model and runs dummy inference for optimization.
        """
        logger.info("Loading YOLO pose model...")
        self.model = YOLO('yolov8n-pose.pt')
        
        # Warm up model with dummy inference to optimize subsequent calls
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        _ = self.model(dummy, verbose=False)
        
        logger.info(f"Pose model loaded successfully!")
    
    def detect_pose(self, img: np.ndarray):
        """
        Detect pose keypoints in image with automatic resize for performance.
        Returns numpy array of keypoints [x, y, confidence] or None if no pose detected.
        """
        if not self.model:
            raise RuntimeError("Model not initialized")
        
        # Resize large images for performance while maintaining aspect ratio
        height, width = img.shape[:2]
        if width > config.image_width_limit:
            scale = config.image_width_limit / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = cv2.resize(img, (new_width, new_height))
        
        # Run pose detection
        results = self.model(img, verbose=False, conf=config.model_conf_threshold)
        
        # Extract first detected person's keypoints
        if results[0].keypoints is not None and len(results[0].keypoints.data) > 0:
            return results[0].keypoints.data[0].cpu().numpy()
        
        return None

# Global service instance
pose_service = PoseService()