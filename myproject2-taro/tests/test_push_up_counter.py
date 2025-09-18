# test_tuned_push_up_counter.py
"""
Test file for the tuned push-up counter with enhanced visualization and controls.
This file maintains the original tuned logic while providing a complete testing interface.
"""

import numpy as np
from typing import Tuple, Optional
from collections import deque
from enum import Enum
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


def draw_keypoints(frame, keypoints, confs=None):
    """Draw push-up relevant keypoints and skeleton with enhanced visualization"""
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
    
    # Draw keypoints
    for idx in indices:
        if idx < len(kpts):
            x, y = kpts[idx]
            cv2.circle(frame, (int(x), int(y)), 6, (0, 255, 255), -1)
    
    # Draw skeleton
    for (i, j) in pairs:
        if i < len(kpts) and j < len(kpts):
            x1, y1 = kpts[i]
            x2, y2 = kpts[j]
            cv2.line(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 3)
    
    return frame, side


def run_tuned_pushup_counter(video_source=0):
    """Main function to run the tuned push-up counter with enhanced interface"""
    print("🎯 Tuned Push-up Counter")
    print("=" * 60)
    print("Features:")
    print("- Tuned thresholds based on video analysis")
    print("- Responsive detection (reduced frame requirements)")
    print("- Improved angle smoothing")
    print("- Enhanced state machine")
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
    
    counter = PushUpCounter()
    
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
                cv2.putText(frame, f"State: {counter.state.value}", (30, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)
                
                if angle is not None:
                    # Color-code angle based on thresholds
                    if angle < counter.DOWN_ANGLE_THRESHOLD:
                        angle_color = (0, 0, 255)  # Red for down position
                    elif angle > counter.UP_ANGLE_THRESHOLD:
                        angle_color = (0, 255, 0)  # Green for up position
                    else:
                        angle_color = (0, 255, 255)  # Yellow for transition
                    
                    cv2.putText(frame, f"Angle: {angle:.1f}°", (30, 130),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, angle_color, 2)
                
                cv2.putText(frame, f"Arm: {active_side}", (30, 170),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                
                # Display thresholds
                cv2.putText(frame, f"Up: {counter.UP_ANGLE_THRESHOLD}° Down: {counter.DOWN_ANGLE_THRESHOLD}°", 
                           (30, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
            else:
                cv2.putText(frame, "No person detected", (30, 50),
                           cv2.FONT_HERSHEY_TRIPLEX, 1, (0, 0, 255), 2)
                cv2.putText(frame, "Stand in view and start push-ups", (30, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            cv2.imshow("Tuned Push-up Counter", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("r"):
                print("🔄 Resetting counter...")
                counter.reset()
                print("Counter reset to 0")
            elif key == ord("d"):
                debug_info = counter.get_debug_info()
                print("📊 Debug Information:")
                for k, v in debug_info.items():
                    print(f"  {k}: {v}")
            elif key == ord("t"):
                print("🎯 Current thresholds:")
                print(f"  Up threshold: {counter.UP_ANGLE_THRESHOLD}°")
                print(f"  Down threshold: {counter.DOWN_ANGLE_THRESHOLD}°")
                try:
                    new_up = input("Enter new up threshold (or press Enter to skip): ").strip()
                    new_down = input("Enter new down threshold (or press Enter to skip): ").strip()
                    
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
    print("Tuned Push-up Counter")
    print("Choose video source:")
    print("1. Webcam")
    print("2. Video file")
    
    choice = input("Enter choice (1-2): ").strip()
    
    if choice == "1":
        run_tuned_pushup_counter(0)
    elif choice == "2":
        video_path = input("Enter video file path: ").strip().strip('"')
        run_tuned_pushup_counter(video_path)
    else:
        print("Invalid choice, using webcam")
        run_tuned_pushup_counter(0)