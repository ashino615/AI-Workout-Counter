# main.py
import cv2
import numpy as np
import time
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import base64

from config import config
from utils.logging_utils import logger
from utils.motivation import get_motivation_text
from services.pose_service import pose_service
from services.debug_service import debug_service
from models.workout_counter import WorkoutCounter
from models.schemas import WorkoutState

# Initialize application configuration from command line arguments
config.setup_from_args()

logger.info(f"Starting in: {config.mode_description}")

# Initialize FastAPI application with dynamic title based on mode
app = FastAPI(title=f"AI Fitness Coach Backend - {config.mode_description}")
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# Session storage for maintaining workout state across requests
workout_sessions = {}

@app.on_event("startup")
async def startup_event():
    """Initialize pose detection model and log available exercise modes"""
    await pose_service.initialize()
    logger.info(f"Supported exercise modes: {config.supported_modes}")

@app.post("/analyze_frame", response_model=WorkoutState)
async def analyze_frame(
    file: UploadFile = File(...), 
    mode: str = Form("chinup")
):
    """
    Core endpoint for exercise analysis from uploaded image frames.
    Processes image, detects pose keypoints, counts repetitions, and returns workout state.
    """
    
    # Validate and sanitize exercise mode
    if mode not in config.supported_modes:
        logger.warning(f"Unsupported mode '{mode}', defaulting to chinup")
        mode = "chinup"
    
    if not pose_service.model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    try:
        # Decode uploaded image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image")
        
        # Retrieve or create workout session
        session_id = "default"
        if session_id not in workout_sessions:
            workout_sessions[session_id] = WorkoutCounter(mode=mode)
        
        counter = workout_sessions[session_id]
        
        # Reset counter if mode changed
        if counter.mode != mode:
            counter = WorkoutCounter(mode=mode)
            workout_sessions[session_id] = counter
            counter.reset()

        # Track frame processing count
        if not hasattr(counter, "frame_count"):
            counter.frame_count = 0
        counter.frame_count += 1
        
        # Initialize response values
        angle_value = None
        position_value = None
        diff = 0.0
        
        # Perform pose detection and analysis
        keypoints = pose_service.detect_pose(img)
        
        if keypoints is not None:
            rep_count, state = counter.update(keypoints)
            
            logger.info(f"Raw counter response - Rep: {rep_count}, State: {state}, State type: {type(state)}")
            
            # Process state based on exercise type (position-based vs angle-based)
            if mode in ["chinup", "pullup"]:
                # Pull-ups use position descriptions (up/down movement)
                if isinstance(state, str):
                    position_value = state
                # Calculate wrist-shoulder difference for debugging
                left_shoulder = keypoints[5]
                right_shoulder = keypoints[6]
                left_wrist = keypoints[9]
                right_wrist = keypoints[10]
                shoulder_y = (left_shoulder[1] + right_shoulder[1]) / 2
                wrist_y = (left_wrist[1] + right_wrist[1]) / 2
                diff = wrist_y - shoulder_y
                
            elif mode in ["pushup", "squat", "armcurl"]:
                # Angle-based exercises return joint angles
                logger.info(f"Processing angle-based exercise: {mode}, state: {state}")
                if state is not None and not isinstance(state, str):
                    try:
                        angle_value = round(float(state), 1)
                        logger.info(f"Angle value set to: {angle_value}")
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert state to float: {state} (type: {type(state)})")
                else:
                    logger.warning(f"State is not a valid angle value: {state} (type: {type(state)})")

                # Push_up_mode, it doesn't use position
                if mode == "pushup":
                    position_value = None

            logger.info(f"Mode: {mode}, Rep: {rep_count}, Angle: {angle_value}, Position: {position_value}")

            # Save debug frame if enabled
            if config.save_frames:
                debug_service.save_debug_frame(
                    contents, counter.frame_count, diff, 
                    position_value or str(angle_value) or "valid", rep_count
                )

        else:
            # No pose detected - maintain current count
            rep_count = counter.count
            
            if config.save_frames:
                debug_service.save_debug_frame(
                    contents, counter.frame_count, 0.0, "no_person", rep_count
                )

        # Generate motivational message based on progress
        motivation = get_motivation_text(rep_count)
        
        # Build response with current workout state
        response = WorkoutState(
            repCount=rep_count,
            angle=angle_value,
            position=position_value,
            motivation=motivation,
            isWorkoutActive=True,
            isConnected=True,
            errorMessage=None,
            framesSent=counter.frame_count,
            lastRepAt=int(time.time() * 1000)
        )
        
        logger.info(f"Sending response: angle={response.angle}, position={response.position}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing frame: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Simple health check endpoint for service monitoring"""
    return {"status": "healthy", "timestamp": time.time()}

@app.post("/reset_session", response_model=WorkoutState)
async def reset_session(mode: str = Form("chinup")):
    """Reset workout session to initial state, optionally changing exercise mode"""
    try:
        if mode not in config.supported_modes:
            mode = "chinup"
            
        session_id = "default"
        workout_sessions[session_id] = WorkoutCounter(mode=mode)
        logger.info(f"Session {session_id} reset successfully (mode={mode})")

        return WorkoutState(
            repCount=0,
            angle=None,
            position=None,
            motivation="Ready to start!",
            isWorkoutActive=False,
            isConnected=True,
            errorMessage=None,
            framesSent=0,
            lastRepAt=int(time.time() * 1000)
        )
        
    except Exception as e:
        logger.error(f"Error resetting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))