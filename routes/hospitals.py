"""Hospital API routes"""

import logging
from flask import Blueprint, request, jsonify

from routes.common import log_request_data, validate_coordinates
from models.database import DatabaseManager
from models.hospital import Hospital

logger = logging.getLogger(__name__)
hospitals_bp = Blueprint('hospitals', __name__, url_prefix='/api')

# Initialize database manager
db_manager = DatabaseManager()


@hospitals_bp.route("/hospitals/search", methods=["POST"])
@log_request_data
def search_hospitals():
    """Search for hospitals near a location using server-side API call"""
    data = request.get_json()
    
    coords, error = validate_coordinates(data, required=True)
    if error:
        logger.warning(f"Invalid coordinates in hospital search: {error}")
        return jsonify({"error": error}), 400
    
    latitude, longitude = coords

    # Get hospital data using the hospital model
    hospital_manager = Hospital(db_manager)
    result = hospital_manager.get_hospitals_for_location(
        latitude=latitude, longitude=longitude, use_cache=True
    )

    if result["success"]:
        logger.info(f"Hospital search successful: {result['total_found']} hospitals found")
        return jsonify(
            {
                "success": True,
                "hospitals": result["hospitals"],
                "total_found": result["total_found"],
                "source": result["source"],
            }
        )
    else:
        logger.error(f"Hospital search failed: {result.get('error', 'Unknown error')}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "hospitals": {},
                }
            ),
            500,
        )
