"""Health check routes"""

import logging
from flask import Blueprint, jsonify

from models.database import DatabaseManager

logger = logging.getLogger(__name__)
health_bp = Blueprint('health', __name__)

# Initialize database manager
db_manager = DatabaseManager()


@health_bp.route("/health")
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db_manager.connect()
        db_manager.close()

        logger.info("Health check successful")
        return jsonify({"status": "healthy", "database": "connected"})
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 503
