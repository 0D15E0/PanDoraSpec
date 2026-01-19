import logging
from rich.logging import RichHandler

def setup_logger(name: str = "pandoraspec", level: int = logging.INFO) -> logging.Logger:
    """Configures a rich-enabled logger for the application."""
    logger = logging.getLogger(name)
    
    # Avoid adding multiple handlers if setup is called multiple times
    if logger.handlers:
        return logger
        
    logger.setLevel(level)
    
    handler = RichHandler(rich_tracebacks=True, markup=True, show_time=False)
    handler.setFormatter(logging.Formatter("%(message)s"))
    
    logger.addHandler(handler)
    return logger

# Singleton instance
logger = setup_logger()
