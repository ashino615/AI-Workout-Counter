import logging
from config import config

def setup_logging():
    """
    Configure logging level based on debug mode setting.
    Non-debug mode uses WARNING level to minimize console output.
    Debug modes use INFO level for detailed operation tracking.
    """
    if config.debug_mode == "non_debug":
        level = logging.WARNING
    else:
        level = logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    return logging.getLogger("fitness_coach")

# Global logger instance - import this in other modules
logger = setup_logging()