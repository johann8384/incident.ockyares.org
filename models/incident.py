    def save_divisions(self, divisions: List[Dict]) -> bool:
        """Save divisions to database"""
        try:
            for division in divisions:
                # Extract coordinates from division data
                coordinates = None
                if 'coordinates' in division:
                    coordinates = division['coordinates']
                elif 'geom' in division and division['geom']:
                    # Parse geometry if it's in different format
                    geom_data = json.loads(division['geom']) if isinstance(division['geom'], str) else division['geom']
                    if 'coordinates' in geom_data:
                        coordinates = geom_data['coordinates'][0]  # Get outer ring
                
                if coordinates:
                    # Ensure polygon is closed
                    coords = coordinates.copy()
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    
                    # Convert coordinates to WKT
                    coords_str = ", ".join([f"{coord[0]} {coord[1]}" for coord in coords])
                    polygon_wkt = f"POLYGON(({coords_str}))"

                    query = """
                    INSERT INTO search_divisions 
                    (incident_id, division_name, division_id, area_geometry, 
                     estimated_area_m2, status, priority, 
                     search_type, estimated_duration, assigned_team)
                    VALUES (%s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, %s, %s, %s)
                    """

                    params = (
                        self.incident_id,
                        division.get("division_name", division.get("name")),
                        division.get("division_id"),
                        polygon_wkt,
                        division.get("estimated_area_m2", 0),
                        division.get("status", "unassigned"),
                        division.get("priority", 1),
                        division.get("search_type", "primary"),
                        division.get("estimated_duration", "2 hours"),
                        division.get("assigned_team")
                    )

                    self.db.execute_query(query, params)
            
            return True

        except Exception as e:
            print(f"Failed to save divisions: {e}")
            return False