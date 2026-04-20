"""
Comprehensive Logging Utility for optimized-filter
=================================================
Provides structured logging with clear visual separation for debugging and monitoring.
"""

import logging
import sys
import os
import json
from datetime import datetime
from functools import wraps
import traceback

def setup_logging(debug=False, log_file=None):
    """
    Setup logging configuration for the application.
    
    Args:
        debug: Enable debug mode for verbose logging
        log_file: Optional file path for log output
    """
    level = logging.DEBUG if debug else logging.INFO
    
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-25s | %(name)-20s | %(funcName)-30s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(detailed_formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = []
    root_logger.addHandler(console_handler)
    
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger


logger = logging.getLogger("optimized_filter")


def log_function_call(logger_instance=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _logger = logger_instance or logger
            func_name = func.__name__
            
            args_repr = [repr(a) for a in args]
            kwargs_repr = [f"{k}={repr(v)}" for k, v in kwargs.items()]
            all_args = args_repr + kwargs_repr
            args_str = ", ".join(all_args) if all_args else ""
            
            _logger.info(f"{'='*60}")
            _logger.info(f"▶ FUNCTION START: {func_name}")
            _logger.info(f"  Arguments: {args_str}")
            _logger.info(f"{'─'*60}")
            
            start_time = datetime.now()
            
            try:
                result = func(*args, **kwargs)
                elapsed = (datetime.now() - start_time).total_seconds()
                
                _logger.info(f"{'─'*60}")
                _logger.info(f"✓ FUNCTION END: {func_name} (took {elapsed:.4f}s)")
                _logger.info(f"{'='*60}")
                
                return result
                
            except Exception as e:
                elapsed = (datetime.now() - start_time).total_seconds()
                _logger.error(f"{'─'*60}")
                _logger.error(f"✗ FUNCTION ERROR: {func_name} after {elapsed:.4f}s")
                _logger.error(f"  Exception: {type(e).__name__}: {str(e)}")
                _logger.error(f"  Traceback: {traceback.format_exc()}")
                _logger.error(f"{'='*60}")
                raise
        
        return wrapper
    return decorator


def log_request(endpoint, method="POST", data=None, logger_instance=None):
    _logger = logger_instance or logger
    _logger.info(f"{'─'*60}")
    _logger.info(f"📥 REQUEST RECEIVED | Endpoint: {endpoint} | Method: {method}")
    if data:
        data_str = json.dumps(data, indent=2)
        if len(data_str) > 500:
            data_str = data_str[:500] + "\n    ... (truncated)"
        _logger.debug(f"  Request Data:\n    {data_str}")
    _logger.info(f"{'─'*60}")


def log_response(endpoint, status_code, data=None, logger_instance=None):
    _logger = logger_instance or logger
    
    if 200 <= status_code < 300:
        status_str = f"✓ {status_code} OK"
    elif 400 <= status_code < 500:
        status_str = f"⚠ {status_code} CLIENT ERROR"
    elif 500 <= status_code:
        status_str = f"✗ {status_code} SERVER ERROR"
    else:
        status_str = f"{status_code}"
    
    _logger.info(f"📤 RESPONSE SENT | Endpoint: {endpoint} | Status: {status_str}")
    if data:
        data_str = json.dumps(data, indent=2)
        if len(data_str) > 500:
            data_str = data_str[:500] + "\n    ... (truncated)"
        _logger.debug(f"  Response Data:\n    {data_str}")
    _logger.info(f"{'─'*60}")


def log_error(error, context="", logger_instance=None):
    _logger = logger_instance or logger
    _logger.error(f"{'✗'*30}")
    _logger.error(f"ERROR in {context}: {type(error).__name__}")
    _logger.error(f"  Message: {str(error)}")
    _logger.error(f"  Traceback: {traceback.format_exc()}")
    _logger.error(f"{'✗'*30}")


def log_warning(message, logger_instance=None):
    _logger = logger_instance or logger
    _logger.warning(f"⚠ {message}")


def log_info(message, logger_instance=None):
    _logger = logger_instance or logger
    _logger.info(f"ℹ {message}")


def log_debug(message, logger_instance=None):
    _logger = logger_instance or logger
    _logger.debug(f"🔍 {message}")


def log_data_flow(direction, endpoint, data, logger_instance=None):
    _logger = logger_instance or logger
    
    arrow = "→" if direction == "OUT" else "←"
    symbol = "📤" if direction == "OUT" else "📥"
    
    _logger.info(f"{symbol} DATA {direction} | {endpoint} | {arrow}")
    
    if data:
        try:
            data_str = json.dumps(data, indent=2)
            if len(data_str) > 1000:
                data_str = data_str[:1000] + "\n    ... (truncated)"
            _logger.debug(f"  Data:\n    {data_str}")
        except:
            _logger.debug(f"  Data: {data}")
    
    _logger.info(f"{'─'*60}")


def log_variable(name, value, logger_instance=None):
    _logger = logger_instance or logger
    value_str = str(value)
    if len(value_str) > 200:
        value_str = value_str[:200] + "..."
    _logger.debug(f"  📌 {name}: {value_str}")


def log_dict_variables(data, prefix="", logger_instance=None):
    _logger = logger_instance or logger
    for key, value in data.items():
        value_str = str(value)
        if len(value_str) > 150:
            value_str = value_str[:150] + "..."
        _logger.debug(f"  📌 {prefix}{key}: {value_str}")


def log_separator(char="-", length=60, logger_instance=None):
    _logger = logger_instance or logger
    _logger.info(char * length)


def log_section(title, logger_instance=None):
    _logger = logger_instance or logger
    _logger.info(f"{'#'*60}")
    _logger.info(f"# {title}")
    _logger.info(f"{'#'*60}")


def get_logger(name):
    return logging.getLogger(f"optimized_filter.{name}")


runner_logger = logging.getLogger("optimized_filter.runner")
collector_logger = logging.getLogger("optimized_filter.collector")
processor_logger = logging.getLogger("optimized_filter.processor")
mqtt_logger = logging.getLogger("optimized_filter.mqtt")


__all__ = [
    'logger',
    'runner_logger',
    'collector_logger',
    'processor_logger',
    'mqtt_logger',
    'setup_logging',
    'log_function_call',
    'log_request',
    'log_response',
    'log_error',
    'log_warning',
    'log_info',
    'log_debug',
    'log_data_flow',
    'log_variable',
    'log_dict_variables',
    'log_separator',
    'log_section',
    'get_logger',
]
