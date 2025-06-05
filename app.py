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


@app.route("/incident/<incident_id>/unit-checkin")
def unit_checkin(incident_id):
    """Unit checkin page"""
    return render_template("unit_checkin.html", incident_id=incident_id)


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


@app.route("/api/unit/checkin", methods=["POST"])
def unit_checkin_api():
    """Check in a unit to an incident"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['incident_id', 'unit_id', 'company_officer', 'number_of_personnel', 'latitude', 'longitude']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"{field.replace('_', ' ').title()} is required"}), 400
        
        # Validate numeric fields
        try:
            personnel_count = int(data['number_of_personnel'])
            latitude = float(data['latitude'])
            longitude = float(data['longitude'])
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid number format for personnel count or coordinates"}), 400
        
        if personnel_count < 1:
            return jsonify({"error": "Personnel count must be at least 1"}), 400
        
        # Check if incident exists
        incident = Incident.get_incident_by_id(data['incident_id'], db_manager)
        if not incident:
            return jsonify({"error": "Incident not found"}), 404
        
        # Check if unit already checked in
        conn = db_manager.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM units 
            WHERE incident_id = %s AND unit_id = %s
        """, (data['incident_id'], data['unit_id']))
        
        existing_unit = cursor.fetchone()
        if existing_unit:
            cursor.close()
            conn.close()
            return jsonify({"error": f"Unit {data['unit_id']} is already checked in to this incident"}), 400
        
        # Insert unit
        cursor.execute("""
            INSERT INTO units (
                incident_id, unit_id, company_officer, number_of_personnel, 
                bsar_tech, latitude, longitude, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['incident_id'],
            data['unit_id'],
            data['company_officer'],
            personnel_count,
            data.get('bsar_tech', False),
            latitude,
            longitude,
            data.get('notes', '')
        ))
        
        unit_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "unit_id": data['unit_id'],
            "message": f"Unit {data['unit_id']} checked in successfully"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/incident/<incident_id>/units", methods=["GET"])
def get_incident_units(incident_id):
    """Get all units checked into an incident"""
    try:
        conn = db_manager.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                unit_id, company_officer, number_of_personnel, bsar_tech,
                latitude, longitude, status, checked_in_at, last_updated, notes
            FROM units 
            WHERE incident_id = %s 
            ORDER BY checked_in_at DESC
        """, (incident_id,))
        
        units = []
        for row in cursor.fetchall():
            units.append({
                'unit_id': row[0],
                'company_officer': row[1],
                'number_of_personnel': row[2],
                'bsar_tech': row[3],
                'latitude': float(row[4]) if row[4] else None,
                'longitude': float(row[5]) if row[5] else None,
                'status': row[6],
                'checked_in_at': row[7].isoformat() if row[7] else None,
                'last_updated': row[8].isoformat() if row[8] else None,
                'notes': row[9]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "units": units,
            "count": len(units)
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
