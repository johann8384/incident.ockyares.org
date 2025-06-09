"""Common utilities and decorators for routes"""

import logging
import traceback
from functools import wraps

from flask import request, jsonify

logger = logging.getLogger(__name__)


def log_request_data(func):
    """Decorator to log request data for API endpoints"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Log request details
            logger.info(f"API Call: {request.method} {request.path}")
            logger.info(f"Remote IP: {request.remote_addr}")
            logger.info(f"User Agent: {request.headers.get('User-Agent', 'Unknown')}")
            
            # Log request data for POST/PUT requests
            if request.method in ['POST', 'PUT', 'PATCH']:
                if request.is_json:
                    data = request.get_json()
                    # Sanitize sensitive data
                    sanitized_data = {k: v for k, v in data.items() if k not in ['password', 'token']}
                    logger.info(f"Request data: {sanitized_data}")
                else:
                    logger.info(f"Request content type: {request.content_type}")
            
            # Call the actual function
            result = func(*args, **kwargs)
            
            # Log successful response
            if hasattr(result, 'status_code'):
                logger.info(f"Response status: {result.status_code}")
            
            return result
            
        except Exception as e:
            # Log the full exception with traceback
            logger.error(f"Error in {func.__name__}: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Return structured error response
            return jsonify({
                "error": str(e),
                "endpoint": request.path,
                "method": request.method,
                "timestamp": str(logger.handlers[0].formatter.formatTime(logging.LogRecord(
                    name='', level=0, pathname='', lineno=0, msg='', args=(), exc_info=None
                ), logger.handlers[0].formatter.datefmt))
            }), 500
    
    return wrapper


def validate_coordinates(data, required=True):
    """Validate latitude and longitude coordinates"""
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    
    if required and (latitude is None or longitude is None):
        return None, "Latitude and longitude are required"
    
    if latitude is not None or longitude is not None:
        try:
            latitude = float(latitude) if latitude is not None else None
            longitude = float(longitude) if longitude is not None else None
        except (ValueError, TypeError):
            return None, "Invalid latitude or longitude values"
    
    return (latitude, longitude), None


def validate_required_fields(data, required_fields):
    """Validate that required fields are present in data"""
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        return False, f"Required fields missing: {', '.join(missing_fields)}"
    return True, None
