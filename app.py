@app.route("/api/incidents/active", methods=["GET"])
@log_request_data
def get_active_incidents():
    """Get all incidents with status 'Active'"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT incident_id, name, incident_type, description, 
                       latitude, longitude, address, status, created_at
                FROM incidents 
                WHERE status = 'Active'
                ORDER BY created_at DESC
            """)
            
            incidents = []
            for row in cursor.fetchall():
                incidents.append({
                    'incident_id': row[0],
                    'name': row[1],
                    'incident_type': row[2],
                    'description': row[3] or '',
                    'latitude': float(row[4]) if row[4] else None,
                    'longitude': float(row[5]) if row[5] else None,
                    'address': row[6] or '',
                    'status': row[7],
                    'created_at': row[8].isoformat() if row[8] else None
                })
            
            logger.info(f"Retrieved {len(incidents)} active incidents")
            return jsonify({
                "success": True,
                "incidents": incidents,
                "count": len(incidents)
            })
            
    except Exception as e:
        logger.error(f"Error getting active incidents: {str(e)}")
        return jsonify({"error": str(e)}), 500


