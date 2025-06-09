"""Geocoding API routes"""

import logging
from flask import Blueprint, request, jsonify

from routes.common import log_request_data, validate_coordinates
from services.geocoding import GeocodingService

logger = logging.getLogger(__name__)
geocoding_bp = Blueprint('geocoding', __name__, url_prefix='/api')

# Initialize geocoding service
geocoding_service = GeocodingService()


@geocoding_bp.route("/geocode/reverse", methods=["POST"])
@log_request_data
def reverse_geocode():
    """Reverse geocode coordinates to address using GeocodingService"""
    data = request.get_json()
    
    coords, error = validate_coordinates(data, required=True)
    if error:
        logger.warning(f"Invalid coordinates in reverse geocode: {error}")
        return jsonify({"error": error}), 400
    
    latitude, longitude = coords
    
    # Use GeocodingService instead of direct API call
    result = geocoding_service.reverse_geocode(latitude, longitude)

    if result["success"]:
        logger.info(f"Successful reverse geocode: {latitude},{longitude} -> {result.get('address')}")
        return jsonify(
            {
                "success": True,
                "address": result["address"],
                "formatted_address": result.get("formatted_address"),
                "address_components": result.get("address_components"),
                "data": result.get("raw_data"),
            }
        )
    else:
        logger.error(f"Reverse geocode failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]}), 500


@geocoding_bp.route("/geocode/forward", methods=["POST"])
@log_request_data
def forward_geocode():
    """Forward geocode address to coordinates using GeocodingService"""
    data = request.get_json()

    address = data.get("address")
    if not address:
        logger.warning("Missing address in forward geocode request")
        return jsonify({"error": "Address is required"}), 400

    # Use GeocodingService for forward geocoding
    result = geocoding_service.forward_geocode(address)

    if result["success"]:
        logger.info(f"Successful forward geocode: {address} -> {result['count']} results")
        return jsonify(
            {
                "success": True,
                "results": result["results"],
                "count": result["count"],
            }
        )
    else:
        logger.error(f"Forward geocode failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]}), 500
