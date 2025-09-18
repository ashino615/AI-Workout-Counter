# test_armcurl_counter.py
"""
Test file for the arm curl counter with enhanced visualization and controls.
This file maintains the original arm curl logic while providing a complete testing interface.
"""

import numpy as np
from typing import Tuple, Optional
from collections import deque
import cv2
import time
from ultralytics import YOLO

# Simple logger replacement for standalone testing
class SimpleLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")
    def warning(self, msg): print(f"[WARNING] {msg}")

logger = SimpleLogger()

# Simple base class replacement for standalone testing
class ExerciseCounter:
    def __init__(self):
        self.count = 0
        self.frame_count = 0


class ArmCurlCounter(ExerciseCounter):
    """
    Arm curl repetition counter using elbow angle measurements.
    Tracks arm flexion (curl up) and extension (lower down) to count complete reps.
    """
    
    def __init__(self):
        super().__init__()
        self.angle_history = deque(maxlen=5)  # Smoothing buffer for angle measurements
        self.state = "down"

        # YOLO keypoint indices for arm angle calculation
        self.R_SHOULDER = 6
        self.R_ELBOW = 8
        self.R_WRIST = 10
        self.L_SHOULDER = 5
        self.L_ELBOW = 7
        self.L_WRIST = 9
        
        # Arm curl angle thresholds (degrees) - opposite of push-ups
        self.up_threshold = 90     # Arms curled up (bicep contracted)
        self.down_threshold = 130  # Arms extended down (bicep stretched)
        
        logger.info(f"💪 Arm curl thresholds: Up={self.up_threshold}°, Down={self.down_threshold}°")
    
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
    
    def analyze_pose(self, keypoints: np.ndarray) -> Tuple[int, Optional[float]]:
        """
        Analyze pose to count arm curls based on elbow angle changes.
        Uses arm with higher confidence score for more reliable measurements.
        """
        self.frame_count += 1
        
        if keypoints is None or len(keypoints) == 0:
            return self.count, None
        
        try:
            angle, confidence, arm_side = self.get_best_arm_angle(keypoints)
            
            if angle is None or confidence < 0.5:
                return self.count, None
            
            # Apply smoothing to reduce noise
            self.angle_history.append(angle)
            
            if len(self.angle_history) == self.angle_history.maxlen:
                avg_angle = np.mean(self.angle_history)
                
                # State machine for rep counting: up -> down = one rep (opposite of push-up)
                if avg_angle < self.up_threshold and self.state == "down":
                    self.state = "up"
                    logger.info(f"🔼 CURL UP detected at {avg_angle:.1f}° (threshold: {self.up_threshold}°)")
                elif avg_angle > self.down_threshold and self.state == "up":
                    self.count += 1  # Completed full rep (curl -> extend)
                    self.state = "down"
                    logger.info(f"✅ ARM CURL REP #{self.count} completed! Extended to {avg_angle:.1f}°")
                
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
        logger.info("💪 Arm curl counter reset")
    
    def get_debug_info(self):
        """Get current debug information."""
        return {
            'count': self.count,
            'state': self.state,
            'angle_buffer_size': len(self.angle_history),
            'thresholds': {
                'up': self.up_threshold,
                'down': self.down_threshold
            },
            'frame_count': self.frame_count
        }
    
    def adjust_thresholds(self, up_threshold=None, down_threshold=None):
        """Allow runtime threshold adjustment for testing."""
        if up_threshold is not None:
            self.up_threshold = up_threshold
            logger.info(f"💪 Up threshold adjusted to {up_threshold}°")
        
        if down_threshold is not None:
            self.down_threshold = down_threshold  
            logger.info(f"💪 Down threshold adjusted to {down_threshold}°")


def draw_keypoints(frame, keypoints, confs=None):
    """Draw arm curl relevant keypoints and skeleton with enhanced visualization"""
    kpts = keypoints.astype(int)
    
    # Define keypoint indices
    R_SHOULDER, R_ELBOW, R_WRIST = 6, 8, 10
    L_SHOULDER, L_ELBOW, L_WRIST = 5, 7, 9
    
    # Determine which arm to highlight based on confidence
    if confs is not None:
        r_conf = (confs[R_SHOULDER] + confs[R_ELBOW] + confs[R_WRIST]) / 3
        l_conf = (confs[L_SHOULDER] + confs[L_ELBOW] + confs[L_WRIST]) / 3
        
        if r_conf >= l_conf:
            pairs = [(R_SHOULDER, R_ELBOW), (R_ELBOW, R_WRIST)]
            indices = [R_SHOULDER, R_ELBOW, R_WRIST]
            side = "Right"
        else:
            pairs = [(L_SHOULDER, L_ELBOW), (L_ELBOW, L_WRIST)]
            indices = [L_SHOULDER, L_ELBOW, L_WRIST]
            side = "Left"
    else:
        # Default to right arm
        pairs = [(R_SHOULDER, R_ELBOW), (R_ELBOW, R_WRIST)]
        indices = [R_SHOULDER, R_ELBOW, R_WRIST]
        side = "Right"
    
    # Draw keypoints with different colors for better visibility
    for i, idx in enumerate(indices):
        if idx < len(kpts):
            x, y = kpts[idx]
            color = [(255, 0, 0), (0, 255, 255), (255, 255, 0)][i]  # Different color for each joint
            cv2.circle(frame, (int(x), int(y)), 8, color, -1)
    
    # Draw skeleton
    for (i, j) in pairs:
        if i < len(kpts) and j < len(kpts):
            x1, y1 = kpts[i]
            x2, y2 = kpts[j]
            cv2.line(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 4)
    
    return frame, side


def run_armcurl_counter(video_source=0):
    """Main function to run the arm curl counter with enhanced interface"""
    print("💪 Arm Curl Counter")
    print("=" * 60)
    print("Features:")
    print("- Elbow angle analysis for bicep curl detection")
    print("- UP position: Arms curled (< 90°)")
    print("- DOWN position: Arms extended (> 130°)")
    print("- Counts complete curl-to-extension reps")
    print("Controls:")
    print("- Press 'Q' to quit")
    print("- Press 'R' to reset counter") 
    print("- Press 'D' for debug info")
    print("- Press 'T' to adjust thresholds")
    print("=" * 60)
    
    model = YOLO("yolov8n-pose.pt")
    cap = cv2.VideoCapture(video_source)
    
    if not cap.isOpened():
        print("❌ Could not open video source")
        return
    
    counter = ArmCurlCounter()
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("End of video or camera disconnected")
                break
            
            results = model(frame, verbose=False, conf=0.3)
            result = results[0] if isinstance(results, list) else results
            
            if result.keypoints is not None and len(result.keypoints.data) > 0:
                kpts = result.keypoints.xy[0].cpu().numpy()
                confs = result.keypoints.conf[0].cpu().numpy()
                
                # Convert to format expected by counter (x, y, confidence)
                keypoints_with_conf = np.zeros((len(kpts), 3))
                keypoints_with_conf[:, :2] = kpts
                keypoints_with_conf[:, 2] = confs
                
                rep_count, angle = counter.analyze_pose(keypoints_with_conf)
                
                frame, active_side = draw_keypoints(frame, kpts, confs)
                
                # Display information with enhanced styling
                cv2.putText(frame, f"Count: {rep_count}", (30, 50),
                           cv2.FONT_HERSHEY_TRIPLEX, 1.5, (0, 255, 0), 3)
                cv2.putText(frame, f"State: {counter.state.upper()}", (30, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)
                
                if angle is not None:
                    # Color-code angle based on thresholds (opposite of push-ups)
                    if angle < counter.up_threshold:
                        angle_color = (0, 255, 0)    # Green for curled up position
                        position = "CURLED"
                    elif angle > counter.down_threshold:
                        angle_color = (0, 0, 255)    # Red for extended down position  
                        position = "EXTENDED"
                    else:
                        angle_color = (0, 255, 255)  # Yellow for transition
                        position = "TRANSITION"
                    
                    cv2.putText(frame, f"Angle: {angle:.1f}° ({position})", (30, 130),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, angle_color, 2)
                
                cv2.putText(frame, f"Active Arm: {active_side}", (30, 170),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                
                # Display thresholds
                cv2.putText(frame, f"Curl: <{counter.up_threshold}° | Extend: >{counter.down_threshold}°", 
                           (30, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # Display exercise instruction
                cv2.putText(frame, "Curl arms up, then extend down for rep", 
                           (30, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
                
            else:
                cv2.putText(frame, "No person detected", (30, 50),
                           cv2.FONT_HERSHEY_TRIPLEX, 1, (0, 0, 255), 2)
                cv2.putText(frame, "Stand in view and start arm curls", (30, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.putText(frame, "Make sure arms are visible", (30, 130),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            cv2.imshow("Arm Curl Counter", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("r"):
                print("💪 Resetting counter...")
                counter.reset()
                print("Counter reset to 0")
            elif key == ord("d"):
                debug_info = counter.get_debug_info()
                print("📊 Debug Information:")
                for k, v in debug_info.items():
                    print(f"  {k}: {v}")
            elif key == ord("t"):
                print("💪 Current thresholds:")
                print(f"  Up threshold (curl): {counter.up_threshold}°")
                print(f"  Down threshold (extend): {counter.down_threshold}°")
                try:
                    new_up = input("Enter new curl threshold (or press Enter to skip): ").strip()
                    new_down = input("Enter new extend threshold (or press Enter to skip): ").strip()
                    
                    if new_up:
                        counter.adjust_thresholds(up_threshold=float(new_up))
                    if new_down:
                        counter.adjust_thresholds(down_threshold=float(new_down))
                except ValueError:
                    print("Invalid threshold values entered")
                except KeyboardInterrupt:
                    pass
                    
    except KeyboardInterrupt:
        print("\nStopped by user")
    
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    print("Arm Curl Counter")
    print("Choose video source:")
    print("1. Webcam")
    print("2. Video file")
    
    choice = input("Enter choice (1-2): ").strip()
    
    if choice == "1":
        run_armcurl_counter(0)
    elif choice == "2":
        video_path = input("Enter video file path: ").strip().strip('"')
        run_armcurl_counter(video_path)
    else:
        print("Invalid choice, using webcam")
        run_armcurl_counter(0)