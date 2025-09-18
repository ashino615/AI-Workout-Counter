# test_pullup_counter.py
"""
Test file for the pull-up counter with enhanced visualization and controls.
This file maintains the original pull-up logic while providing a complete testing interface.
"""

import time
import numpy as np
from typing import Tuple
from collections import deque
import cv2
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
        self.movement_threshold = 20  # Pixels of movement to detect direction change
        self.min_consecutive_frames = 3  # Frames needed to confirm direction
        self.rep_cooldown = 2.0  # Seconds between reps to avoid double counting
        self.min_confidence = 0.5  # Minimum keypoint confidence
        self.min_movement_range = 50  # Minimum movement range for valid rep
        self.debug_mode = "debug"  # Enable debug logging

config = SimpleConfig()


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
        
        logger.info(f"Pull-up counter initialized with movement threshold: {config.movement_threshold}px")
    
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
        self.frame_count += 1
        
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
                            
                            logger.info(f"PULL-UP REP #{self.count} completed! Range: {movement_range:.1f}px")
                            
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
    
    def get_debug_info(self):
        """Get current debug information."""
        time_since_last_rep = time.time() - self.last_rep_time if self.last_rep_time > 0 else 0
        return {
            'count': self.count,
            'position': self.position,
            'current_direction': self.current_direction,
            'consecutive_up_frames': self.consecutive_up_frames,
            'consecutive_down_frames': self.consecutive_down_frames,
            'position_buffer_size': len(self.position_history),
            'direction_history_size': len(self.direction_history),
            'time_since_last_rep': f"{time_since_last_rep:.1f}s",
            'cooldown_remaining': max(0, config.rep_cooldown - time_since_last_rep),
            'settings': {
                'movement_threshold': config.movement_threshold,
                'min_consecutive_frames': config.min_consecutive_frames,
                'min_movement_range': config.min_movement_range,
                'rep_cooldown': config.rep_cooldown
            }
        }
    
    def adjust_settings(self, movement_threshold=None, min_consecutive_frames=None, 
                       min_movement_range=None, rep_cooldown=None):
        """Allow runtime adjustment of detection parameters."""
        if movement_threshold is not None:
            config.movement_threshold = movement_threshold
            logger.info(f"Movement threshold adjusted to {movement_threshold}px")
        
        if min_consecutive_frames is not None:
            config.min_consecutive_frames = min_consecutive_frames
            logger.info(f"Min consecutive frames adjusted to {min_consecutive_frames}")
            
        if min_movement_range is not None:
            config.min_movement_range = min_movement_range
            logger.info(f"Min movement range adjusted to {min_movement_range}px")
            
        if rep_cooldown is not None:
            config.rep_cooldown = rep_cooldown
            logger.info(f"Rep cooldown adjusted to {rep_cooldown}s")


def draw_keypoints(frame, keypoints, confs=None):
    """Draw pull-up relevant keypoints and skeleton with enhanced visualization"""
    kpts = keypoints.astype(int)
    
    # Define keypoint indices for pull-up tracking
    L_SHOULDER, R_SHOULDER = 5, 6
    L_WRIST, R_WRIST = 9, 10
    
    # Draw shoulder and wrist keypoints
    shoulder_indices = [L_SHOULDER, R_SHOULDER]
    wrist_indices = [L_WRIST, R_WRIST]
    
    # Draw shoulders in blue
    for idx in shoulder_indices:
        if idx < len(kpts):
            x, y = kpts[idx]
            cv2.circle(frame, (int(x), int(y)), 8, (255, 0, 0), -1)
    
    # Draw wrists in yellow
    for idx in wrist_indices:
        if idx < len(kpts):
            x, y = kpts[idx]
            cv2.circle(frame, (int(x), int(y)), 8, (0, 255, 255), -1)
    
    # Draw lines to show wrist-shoulder relationship
    if (L_SHOULDER < len(kpts) and R_SHOULDER < len(kpts) and 
        L_WRIST < len(kpts) and R_WRIST < len(kpts)):
        
        # Calculate center points
        shoulder_center = ((kpts[L_SHOULDER][0] + kpts[R_SHOULDER][0]) // 2,
                          (kpts[L_SHOULDER][1] + kpts[R_SHOULDER][1]) // 2)
        wrist_center = ((kpts[L_WRIST][0] + kpts[R_WRIST][0]) // 2,
                       (kpts[L_WRIST][1] + kpts[R_WRIST][1]) // 2)
        
        # Draw line between shoulder and wrist centers
        cv2.line(frame, shoulder_center, wrist_center, (0, 255, 0), 3)
        
        # Draw center points
        cv2.circle(frame, shoulder_center, 6, (255, 0, 0), -1)
        cv2.circle(frame, wrist_center, 6, (0, 255, 255), -1)
        
        return frame, wrist_center[1] - shoulder_center[1]
    
    return frame, None


def run_pullup_counter(video_source=0):
    """Main function to run the pull-up counter with enhanced interface"""
    print("Pull-Up Counter")
    print("=" * 60)
    print("Features:")
    print("- Motion-based vertical movement detection")
    print("- Tracks wrist-shoulder distance changes")
    print("- Counts DOWN -> UP sequences as complete reps")
    print("- Requires minimum movement range for valid reps")
    print("Controls:")
    print("- Press 'Q' to quit")
    print("- Press 'R' to reset counter") 
    print("- Press 'D' for debug info")
    print("- Press 'S' to adjust settings")
    print("=" * 60)
    
    model = YOLO("yolov8n-pose.pt")
    cap = cv2.VideoCapture(video_source)
    
    if not cap.isOpened():
        print("Could not open video source")
        return
    
    counter = PullUpCounter()
    
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
                
                rep_count, position = counter.analyze_pose(keypoints_with_conf)
                
                frame, wrist_shoulder_diff = draw_keypoints(frame, kpts, confs)
                
                # Display information with enhanced styling
                cv2.putText(frame, f"Count: {rep_count}", (30, 50),
                           cv2.FONT_HERSHEY_TRIPLEX, 1.5, (0, 255, 0), 3)
                
                # Color-code position status
                if position == "pulling_up":
                    position_color = (0, 255, 0)    # Green for pulling up
                elif position == "lowering_down":
                    position_color = (0, 0, 255)    # Red for lowering down
                else:
                    position_color = (255, 255, 0)  # Yellow for stable/neutral
                
                cv2.putText(frame, f"Status: {position.replace('_', ' ').title()}", (30, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.9, position_color, 2)
                
                cv2.putText(frame, f"Direction: {counter.current_direction.upper()}", (30, 130),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                
                if wrist_shoulder_diff is not None:
                    cv2.putText(frame, f"W-S Diff: {wrist_shoulder_diff:.0f}px", (30, 170),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                
                # Show consecutive frame counts
                cv2.putText(frame, f"Up: {counter.consecutive_up_frames} Down: {counter.consecutive_down_frames}", 
                           (30, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
                
                # Show settings
                cv2.putText(frame, f"Move Thresh: {config.movement_threshold}px | Min Range: {config.min_movement_range}px", 
                           (30, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
                
                
            else:
                cv2.putText(frame, "No person detected", (30, 50),
                           cv2.FONT_HERSHEY_TRIPLEX, 1, (0, 0, 255), 2)
                cv2.putText(frame, "Position yourself in view", (30, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.putText(frame, "Make sure shoulders and wrists are visible", (30, 130),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            cv2.imshow("Pull-up Counter", frame)
            
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
            elif key == ord("s"):
                print("Current settings:")
                print(f"  Movement threshold: {config.movement_threshold}px")
                print(f"  Min consecutive frames: {config.min_consecutive_frames}")
                print(f"  Min movement range: {config.min_movement_range}px")
                print(f"  Rep cooldown: {config.rep_cooldown}s")
                try:
                    new_move_thresh = input("Enter new movement threshold (or press Enter to skip): ").strip()
                    new_min_frames = input("Enter new min consecutive frames (or press Enter to skip): ").strip()
                    new_min_range = input("Enter new min movement range (or press Enter to skip): ").strip()
                    new_cooldown = input("Enter new rep cooldown (or press Enter to skip): ").strip()
                    
                    if new_move_thresh:
                        counter.adjust_settings(movement_threshold=float(new_move_thresh))
                    if new_min_frames:
                        counter.adjust_settings(min_consecutive_frames=int(new_min_frames))
                    if new_min_range:
                        counter.adjust_settings(min_movement_range=float(new_min_range))
                    if new_cooldown:
                        counter.adjust_settings(rep_cooldown=float(new_cooldown))
                except ValueError:
                    print("Invalid values entered")
                except KeyboardInterrupt:
                    pass
                    
    except KeyboardInterrupt:
        print("\nStopped by user")
    
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    print("Pull-up Counter")
    print("Choose video source:")
    print("1. Webcam")
    print("2. Video file")
    
    choice = input("Enter choice (1-2): ").strip()
    
    if choice == "1":
        run_pullup_counter(0)
    elif choice == "2":
        video_path = input("Enter video file path: ").strip().strip('"')
        run_pullup_counter(video_path)
    else:
        print("Invalid choice, using webcam")
        run_pullup_counter(0)