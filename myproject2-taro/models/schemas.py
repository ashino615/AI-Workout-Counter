# schemas.py
from pydantic import BaseModel
from typing import Optional

class WorkoutState(BaseModel):
    """
    Pydantic model representing the complete workout state returned to clients.
    Contains rep count, exercise-specific data, user feedback, and connection status.
    """
    repCount: int = 0                           # Current repetition count
    angle: Optional[float] = None               # Joint angle for angle-based exercises (degrees)
    position: Optional[str] = None              # Position description for motion-based exercises
    motivation: str = "Let's get started!"     # Motivational message for user engagement
    isWorkoutActive: bool = False              # Whether workout session is active
    isConnected: bool = False                  # Connection status to backend
    errorMessage: Optional[str] = None         # Error details if processing failed
    framesSent: int = 0                        # Total frames processed in session
    lastRepAt: int = 0                         # Timestamp of last completed repetition (milliseconds)