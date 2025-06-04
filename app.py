from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import requests

from models.database import DatabaseManager
from models.incident import Incident
from models.hospital import Hospital

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

# Initialize database
db_manager = DatabaseManager()


@app.route("/")
def index():
    """Main incident creation page"""
    return render_template("index.html")


@app.route("/incident/<incident_id>")
def view_incident(incident_id):
    """View specific incident"""
    return render_template("incident_view.html", incident_id=incident_id)


@app.route("/api/geocode/reverse", methods=["POST"])
def reverse_geocode():
    """Reverse geocode coordinates to address"""
    try:
        data = request.get_json()
        
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        
        if latitude is None or longitude is None:
            return jsonify({"error": "Latitude and longitude are required"}), 400
        
        # Convert to float
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid latitude or longitude values"}), 400
        
        # Make request to Nominatim
        try:
            nominatim_url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'format': 'json',
                'lat': latitude,
                'lon': longitude,
                'zoom': 18,
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': 'EmergencyIncidentApp/1.0 (Emergency Management System)'
            }
            
            response = requests.get(nominatim_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                geocode_data = response.json()
                address = geocode_data.get('display_name')
                
                return jsonify({
                    "success": True,
                    "address": address,
                    "data": geocode_data
                })
            else:
                return jsonify({
                    "success": False,
                    "error": f"Geocoding service returned status {response.status_code}"
                }), 500
                
        except requests.exceptions.Timeout:
            return jsonify({
                "success": False,
                "error": "Geocoding request timed out"
            }), 500
        except requests.exceptions.RequestException as e:
            return jsonify({
                "success": False,
                "error": f"Geocoding request failed: {str(e)}"
            }), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/hospitals/search", methods=["POST"])
def search_hospitals():
    """Search for hospitals near a location using server-side API call"""
    try:
        data = request.get_json()
        
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        
        if latitude is None or longitude is None:
            return jsonify({"error": "Latitude and longitude are required"}), 400
        
        # Convert to float
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid latitude or longitude values"}), 400
        
        # Get hospital data using the hospital model
        hospital_manager = Hospital(db_manager)
        result = hospital_manager.get_hospitals_for_location(
            latitude=latitude,
            longitude=longitude,
            use_cache=True
        )
        
        if result['success']:
            return jsonify({
                "success": True,
                "hospitals": result['hospitals'],
                "total_found": result['total_found'],
                "source": result['source']
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get('error', 'Unknown error'),
                "hospitals": {}
            }), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/divisions/generate", methods=["POST"])
def generate_divisions_preview():
    """Generate search divisions for preview (without saving to database)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get("coordinates") or len(data.get("coordinates", [])) < 3:
            return jsonify({"error": "Search area coordinates required (minimum 3 points)"}), 400
            
        # Create temporary incident instance for division generation
        incident = Incident(db_manager)
        
        # Generate divisions without saving
        divisions = incident.generate_divisions_preview(
            search_area_coordinates=data["coordinates"],
            area_size_m2=data.get("area_size_m2", 40000)
        )
        
        return jsonify({
            "success": True,
            "divisions": divisions,
            "count": len(divisions),
            "message": f"Generated {len(divisions)} search divisions for preview"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/incident", methods=["POST"])
def create_incident():
    """Create new incident with full data including location, hospitals, and divisions"""
    try:
        data = request.get_json()

        # Validate required fields
        if not data.get("name") or not data.get("incident_type"):
            return jsonify({"error": "Name and incident type are required"}), 400

        # Create incident with all available data
        incident = Incident(db_manager)
        incident_id = incident.create_incident(
            name=data["name"],
            incident_type=data["incident_type"],
            description=data.get("description", ""),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            address=data.get("address"),
            hospital_data=data.get("hospital_data"),
            search_area_coordinates=data.get("search_area_coordinates"),
            divisions=data.get("divisions")  # Save divisions if provided
        )

        return jsonify(
            {
                "success": True,
                "incident_id": incident_id,
                "message": "Incident created successfully",
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/incident/<incident_id>", methods=["GET"])
def get_incident(incident_id):
    """Get incident details including hospitals and divisions"""
    try:
        incident = Incident.get_incident_by_id(incident_id, db_manager)
        if not incident:
            return jsonify({"error": "Incident not found"}), 404
        
        incident_data = incident.get_incident_data()
        return jsonify({
            "success": True,
            "incident": incident_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/incident/<incident_id>/location", methods=["POST"])
def set_incident_location(incident_id):
    """Set incident location"""
    try:
        data = request.get_json()

        if not data.get("latitude") or not data.get("longitude"):
            return jsonify({"error": "Latitude and longitude are required"}), 400

        incident = Incident(db_manager)
        incident.incident_id = incident_id

        success = incident.set_location(
            latitude=float(data["latitude"]), 
            longitude=float(data["longitude"])
        )

        if success:
            return jsonify(
                {
                    "success": True,
                    "address": incident.address,
                    "message": "Location set successfully",
                }
            )
        else:
            return jsonify({"error": "Failed to set location"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/incident/<incident_id>/search-area", methods=["POST"])
def set_search_area(incident_id):
    """Set search area polygon"""
    try:
        data = request.get_json()

        if not data.get("coordinates") or len(data["coordinates"]) < 3:
            return (
                jsonify({"error": "At least 3 coordinates required for polygon"}),
                400,
            )

        incident = Incident(db_manager)
        incident.incident_id = incident_id

        success = incident.set_search_area(data["coordinates"])

        if success:
            return jsonify({"success": True, "message": "Search area set successfully"})
        else:
            return jsonify({"error": "Failed to set search area"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/incident/<incident_id>/hospitals", methods=["POST"])
def save_hospital_data(incident_id):
    """Save hospital data for incident"""
    try:
        data = request.get_json()
        
        if not data.get("hospital_data"):
            return jsonify({"error": "Hospital data is required"}), 400
        
        incident = Incident(db_manager)
        incident.incident_id = incident_id
        
        success = incident.save_hospital_data(data["hospital_data"])
        
        if success:
            return jsonify({
                "success": True,
                "message": "Hospital data saved successfully"
            })
        else:
            return jsonify({"error": "Failed to save hospital data"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/incident/<incident_id>/divisions", methods=["POST"])
def save_divisions(incident_id):
    """Save search divisions for existing incident"""
    try:
        data = request.get_json()
        
        if not data.get("divisions"):
            return jsonify({"error": "Divisions data is required"}), 400
            
        incident = Incident.get_incident_by_id(incident_id, db_manager)
        if not incident:
            return jsonify({"error": "Incident not found"}), 404

        success = incident.save_divisions(data["divisions"])
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Saved {len(data['divisions'])} divisions successfully"
            })
        else:
            return jsonify({"error": "Failed to save divisions"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/incident/<incident_id>/divisions", methods=["GET"])
def get_divisions(incident_id):
    """Get search divisions for incident"""
    try:
        incident = Incident(db_manager)
        incident.incident_id = incident_id
        
        divisions = incident.get_divisions()
        
        return jsonify({
            "success": True,
            "divisions": divisions,
            "count": len(divisions)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db_manager.connect()
        db_manager.close()

        return jsonify({"status": "healthy", "database": "connected"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


if __name__ == "__main__":
    # Initialize database schema on startup
    try:
        db_manager.create_tables()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization failed: {e}")

    app.run(
        debug=os.getenv("FLASK_DEBUG", "True").lower() == "true",
        host="0.0.0.0",
        port=int(os.getenv("FLASK_PORT", 5000)),
    )
