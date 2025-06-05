    def get_divisions(self) -> List[Dict]:
        """Get search divisions for this incident"""
        try:
            query = """
            SELECT 
                id, division_name, division_id, estimated_area_m2,
                assigned_team, team_leader, priority, search_type,
                estimated_duration, status,
                ST_AsGeoJSON(area_geometry) as geometry_geojson
            FROM search_divisions
            WHERE incident_id = %s
            ORDER BY division_name
            """
            
            result = self.db.execute_query(query, (self.incident_id,), fetch=True)
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            print(f"Failed to get divisions: {e}")
            return []