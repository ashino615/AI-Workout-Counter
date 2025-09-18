# test_improved_squat_counter.py
"""
Test file for the improved squat counter with enhanced visualization and controls.
This file maintains the simplified squat logic while providing a complete testing interface.
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

# Simple config replacement for standalone testing
class SimpleConfig:
    def __init__(self):
        self.squat_up = 170     # Standing threshold
        self.squat_down = 140   # Squatting threshold

config = SimpleConfig()


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
        self.up_threshold = getattr(config, "squat_up", 130)    # Standing (knees straight)
        self.down_threshold = getattr(config, "squat_down", 100)  # Squatting (knees bent)
        
        # Movement tracking
        self.went_down = False
        self.last_state_change = 0
        self.min_frames_in_state = 2  # Minimal frame requirement
        
        logger.info(f"Squat thresholds: Up={self.up_threshold}°, Down={self.down_threshold}°")
    
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
            
            # Return best angle, confidence, and leg info
            if r_conf >= 0.3 and l_conf >= 0.3:
                if r_angle is not None and l_angle is not None and abs(r_angle - l_angle) < 30:
                    return (r_angle + l_angle) / 2, (r_conf + l_conf) / 2, "Both"
                else:
                    if r_conf >= l_conf:
                        return r_angle, r_conf, "Right"
                    else:
                        return l_angle, l_conf, "Left"
            elif r_conf >= 0.3:
                return r_angle, r_conf, "Right"
            elif l_conf >= 0.3:
                return l_angle, l_conf, "Left"
            else:
                return None, 0, "None"
                
        except Exception as e:
            logger.error(f"Error getting leg angle: {e}")
            return None, 0, "Error"
    
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
            angle, confidence, leg_side = self.get_best_leg_angle(keypoints)
            
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
    
    def get_debug_info(self):
        """Get current debug information."""
        return {
            'count': self.count,
            'state': self.state,
            'went_down': self.went_down,
            'frames_in_state': self.frame_count - self.last_state_change,
            'angle_buffer_size': len(self.angle_history),
            'thresholds': {
                'up': self.up_threshold,
                'down': self.down_threshold
            },
            'settings': {
                'min_frames_in_state': self.min_frames_in_state,
                'frame_count': self.frame_count
            }
        }
    
    def adjust_thresholds(self, up_threshold=None, down_threshold=None):
        """Allow runtime threshold adjustment for testing."""
        if up_threshold is not None:
            self.up_threshold = up_threshold
            config.squat_up = up_threshold
            logger.info(f"Up threshold adjusted to {up_threshold}°")
        
        if down_threshold is not None:
            self.down_threshold = down_threshold
            config.squat_down = down_threshold
            logger.info(f"Down threshold adjusted to {down_threshold}°")


def draw_keypoints(frame, keypoints, confs=None):
    """Draw squat relevant keypoints and skeleton with enhanced visualization"""
    kpts = keypoints.astype(int)
    
    # Define keypoint indices
    R_HIP, R_KNEE, R_ANKLE = 12, 14, 16
    L_HIP, L_KNEE, L_ANKLE = 11, 13, 15
    
    # Determine which leg to highlight based on confidence
    if confs is not None:
        r_conf = (confs[R_HIP] + confs[R_KNEE] + confs[R_ANKLE]) / 3
        l_conf = (confs[L_HIP] + confs[L_KNEE] + confs[L_ANKLE]) / 3
        
        if r_conf >= l_conf:
            pairs = [(R_HIP, R_KNEE), (R_KNEE, R_ANKLE)]
            indices = [R_HIP, R_KNEE, R_ANKLE]
            side = "Right"
        else:
            pairs = [(L_HIP, L_KNEE), (L_KNEE, L_ANKLE)]
            indices = [L_HIP, L_KNEE, L_ANKLE]
            side = "Left"
    else:
        # Default to right leg
        pairs = [(R_HIP, R_KNEE), (R_KNEE, R_ANKLE)]
        indices = [R_HIP, R_KNEE, R_ANKLE]
        side = "Right"
    
    # Draw keypoints with different colors for each joint
    colors = [(255, 0, 0), (0, 255, 255), (255, 255, 0)]  # Hip, Knee, Ankle
    for i, idx in enumerate(indices):
        if idx < len(kpts):
            x, y = kpts[idx]
            cv2.circle(frame, (int(x), int(y)), 8, colors[i], -1)
    
    # Draw skeleton
    for (i, j) in pairs:
        if i < len(kpts) and j < len(kpts):
            x1, y1 = kpts[i]
            x2, y2 = kpts[j]
            cv2.line(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 4)
    
    return frame, side


def run_improved_squat_counter(video_source=0):
    """Main function to run the improved squat counter with enhanced interface"""
    print("Improved Squat Counter - Reliable Counting")
    print("=" * 60)
    print("Features:")
    print("- Simple 2-state detection (UP ↔ DOWN)")
    print("- Knee angle analysis for squat detection")
    print("- UP: Standing position (>130°)")
    print("- DOWN: Squatting position (<100°)")
    print("- Minimal frame requirements for quick response")
    print("Controls:")
    print("- Press 'Q' to quit")
    print("- Press 'R' to reset counter") 
    print("- Press 'D' for debug info")
    print("- Press 'T' to adjust thresholds")
    print("=" * 60)
    
    model = YOLO("yolov8n-pose.pt")
    cap = cv2.VideoCapture(video_source)
    
    if not cap.isOpened():
        print("Could not open video source")
        return
    
    counter = SquatCounter()
    
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
                    # Color-code angle based on thresholds
                    if angle < counter.down_threshold:
                        angle_color = (0, 0, 255)     # Red for squat down
                        position = "SQUATTING"
                    elif angle > counter.up_threshold:
                        angle_color = (0, 255, 0)     # Green for standing up
                        position = "STANDING"
                    else:
                        angle_color = (0, 255, 255)   # Yellow for transition
                        position = "TRANSITION"
                    
                    cv2.putText(frame, f"Knee: {angle:.1f}° ({position})", (30, 130),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, angle_color, 2)
                
                cv2.putText(frame, f"Active Leg: {active_side}", (30, 170),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                
                # Display thresholds
                cv2.putText(frame, f"Stand: >{counter.up_threshold}° | Squat: <{counter.down_threshold}°", 
                           (30, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # Show frames in current state
                frames_in_state = counter.frame_count - counter.last_state_change
                cv2.putText(frame, f"Frames in {counter.state}: {frames_in_state}", 
                           (30, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
                
            
                
            else:
                cv2.putText(frame, "No person detected", (30, 50),
                           cv2.FONT_HERSHEY_TRIPLEX, 1, (0, 0, 255), 2)
                cv2.putText(frame, "Stand in view and start squats", (30, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.putText(frame, "Make sure legs are visible", (30, 130),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            cv2.imshow("Improved Squat Counter", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("r"):
                print("Resetting counter...")
                counter.reset()
                print("Counter reset to 0")
            elif key == ord("d"):
                debug_info = counter.get_debug_info()
                print("Debug Information:")
                for k, v in debug_info.items():
                    print(f"  {k}: {v}")
            elif key == ord("t"):
                print("Current thresholds:")
                print(f"  Up threshold (standing): {counter.up_threshold}°")
                print(f"  Down threshold (squat): {counter.down_threshold}°")
                try:
                    new_up = input("Enter new standing threshold (or press Enter to skip): ").strip()
                    new_down = input("Enter new squat threshold (or press Enter to skip): ").strip()
                    
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
    print("Improved Squat Counter")
    print("Choose video source:")
    print("1. Webcam")
    print("2. Video file")
    
    choice = input("Enter choice (1-2): ").strip()
    
    if choice == "1":
        run_improved_squat_counter(0)
    elif choice == "2":
        video_path = input("Enter video file path: ").strip().strip('"')
        run_improved_squat_counter(video_path)
    else:
        print("Invalid choice, using webcam")
        run_improved_squat_counter(0)