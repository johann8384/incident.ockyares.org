@app.route("/api/geocode/reverse", methods=["POST"])
@log_request_data
def reverse_geocode():
    """Reverse geocode coordinates to address using GeocodingService"""
    data = request.get_json()

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if latitude is None or longitude is None:
        logger.warning("Missing latitude or longitude in reverse geocode request")
        return jsonify({"error": "Latitude and longitude are required"}), 400

    # Convert to float
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid coordinate format: lat={latitude}, lng={longitude}, error={e}")
        return jsonify({"error": "Invalid latitude or longitude values"}), 400

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


@app.route("/api/hospitals/search", methods=["POST"])
@log_request_data
def search_hospitals():
    """Search for hospitals near a location using server-side API call"""
    data = request.get_json()

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if latitude is None or longitude is None:
        logger.warning("Missing coordinates in hospital search request")
        return jsonify({"error": "Latitude and longitude are required"}), 400

    # Convert to float
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid coordinates in hospital search: lat={latitude}, lng={longitude}, error={e}")
        return jsonify({"error": "Invalid latitude or longitude values"}), 400

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


