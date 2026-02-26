import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging(log_dir="logs"):
    """
    Sets up the logging configuration for the application.
    Creates a 'logs' directory if it doesn't exist.
    Configures a rotating file handler for general logs and a separate handler for errors.
    """
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create formatters
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Clear existing handlers to avoid duplicates if called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # 1. Rotating File Handler (General logs)
    # 10 MB per file, max 5 backup files
    app_log_path = os.path.join(log_dir, "app.log")
    file_handler = RotatingFileHandler(app_log_path, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 2. Error File Handler (Errors only)
    error_log_path = os.path.join(log_dir, "error.log")
    error_handler = logging.FileHandler(error_log_path, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    # 3. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logging.info("Logging initialized.")

if __name__ == "__main__":
    setup_logging()
    logging.info("This is a test info message.")
    logging.warning("This is a test warning message.")
    logging.error("This is a test error message.")
