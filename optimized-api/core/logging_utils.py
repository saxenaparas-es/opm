import logging
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("optimized_api")


def setup_logging(debug=False):
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)


def log_request(endpoint, data=None):
    logger.info(f"[REQUEST] {endpoint}")
    if data and isinstance(data, dict):
        logger.debug(f"[DATA] {data}")


def log_response(endpoint, status, data=None):
    logger.info(f"[RESPONSE] {endpoint} - Status: {status}")
    if data and isinstance(data, dict):
        logger.debug(f"[DATA] {data}")


def log_error(endpoint, error):
    logger.error(f"[ERROR] {endpoint} - {type(error).__name__}: {str(error)}")


def log_warning(message):
    logger.warning(f"[WARNING] {message}")


def log_info(message):
    logger.info(f"[INFO] {message}")


__all__ = [
    'logger',
    'setup_logging',
    'log_request',
    'log_response',
    'log_error',
    'log_warning',
    'log_info',
]