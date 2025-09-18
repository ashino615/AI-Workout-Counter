import cv2
import numpy as np
import time
from config import config
from utils.logging_utils import logger

class DebugService:
    """
    Debug frame visualization and saving service for development and troubleshooting.
    Overlays exercise metrics on frames and saves them when debug mode is enabled.
    """
    
    @staticmethod
    def save_debug_frame(img_bytes: bytes, frame_count: int, diff_value: float, position: str, rep_count: int):
        """
        Save annotated debug frame to disk if frame saving is enabled.
        Overlays exercise metrics and saves with descriptive filename.
        """
        if not config.save_frames or not config.debug_dir:
            return
            
        try:
            # Decode image from bytes
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return
            
            # Create annotated copy
            debug_img = img.copy()
            font = cv2.FONT_HERSHEY_SIMPLEX
            
            # Overlay exercise metrics
            texts = [
                f"Frame: {frame_count}",
                f"Diff: {diff_value:.1f}", 
                f"Position or Angle: {position}",
                f"Reps: {rep_count}"
            ]
            
            for i, text in enumerate(texts):
                y_pos = 40 + (i * 35)
                cv2.putText(debug_img, text, (10, y_pos), font, 0.8, (0, 255, 0), 2)
            
            # Generate descriptive filename with timestamp
            timestamp = int(time.time())
            filename = f"frame_{frame_count:04d}_reps_{rep_count}_{timestamp}.jpg"
            filepath = config.debug_dir / filename
            
            cv2.imwrite(str(filepath), debug_img)
            logger.debug(f"Debug frame saved: {filename}")
            
        except Exception as e:
            logger.error(f"Error saving debug frame: {e}")

# Global service instance
debug_service = DebugService()