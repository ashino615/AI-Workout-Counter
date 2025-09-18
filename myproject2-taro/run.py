import uvicorn
from main import app
from config import config

if __name__ == "__main__":
    # Display startup information with available command-line options
    print("\n" + "="*60)
    print("AI Fitness Coach Backend")
    print("="*60)
    print(f"Mode: {config.mode_description}")
    print("\nAvailable modes:")
    print("  python run.py --mode debug         # Debug with frame saving")
    print("  python run.py --mode debug_no_save # Debug without frame saving") 
    print("  python run.py --mode non_debug     # Minimal logging only")
    print("="*60 + "\n")
    
    # Start FastAPI server with CORS enabled for cross-origin requests
    uvicorn.run(app, host="0.0.0.0", port=8000)