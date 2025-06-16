    def _generate_voronoi_cells_postgis(self, seed_points: List[Tuple[float, float]], polygon: Polygon) -> List[Polygon]:
        """Generate Voronoi cells using PostGIS ST_VoronoiPolygons as fallback"""
        try:
            # Add boundary buffer points for complete coverage
            bounds = polygon.bounds
            margin = max((bounds[2] - bounds[0]), (bounds[3] - bounds[1])) * 0.5
            
            boundary_buffer_points = [
                (bounds[0] - margin, bounds[1] - margin),  # SW
                (bounds[2] + margin, bounds[1] - margin),  # SE  
                (bounds[2] + margin, bounds[3] + margin),  # NE
                (bounds[0] - margin, bounds[3] + margin),  # NW
                (bounds[0] - margin, (bounds[1] + bounds[3]) / 2),  # W
                (bounds[2] + margin, (bounds[1] + bounds[3]) / 2),  # E
                ((bounds[0] + bounds[2]) / 2, bounds[1] - margin),  # S
                ((bounds[0] + bounds[2]) / 2, bounds[3] + margin),  # N
            ]
            
            # Combine original points with boundary buffer points
            all_points = seed_points + boundary_buffer_points
            
            # Create points collection for PostGIS
            points_wkt = "MULTIPOINT(" + ", ".join([f"({p[0]} {p[1]})" for p in all_points]) + ")"
            
            # Get polygon boundary for clipping
            polygon_wkt = polygon.wkt
            
            # Use PostGIS to generate Voronoi diagram with complete coverage
            query = """
            WITH voronoi_cells AS (
                SELECT (ST_Dump(ST_VoronoiPolygons(ST_GeomFromText(%s, 4326), 0.0, ST_Expand(ST_GeomFromText(%s, 4326), %s)))).geom as cell_geom
            ),
            clipped_cells AS (
                SELECT ST_Intersection(cell_geom, ST_GeomFromText(%s, 4326)) as clipped_geom
                FROM voronoi_cells
                WHERE ST_Intersects(cell_geom, ST_GeomFromText(%s, 4326))
                AND ST_Area(ST_Intersection(cell_geom, ST_GeomFromText(%s, 4326))) > 0.000001
            )
            SELECT ST_AsText(clipped_geom) as geom_wkt
            FROM clipped_cells
            WHERE ST_GeometryType(clipped_geom) = 'ST_Polygon'
            ORDER BY ST_Area(clipped_geom) DESC
            """
            
            result = self.db.execute_query(
                query, 
                (points_wkt, polygon_wkt, margin, polygon_wkt, polygon_wkt, polygon_wkt), 
                fetch=True
            )
            
            voronoi_polygons = []
            if result:
                for row in result:
                    try:
                        wkt_geom = row[0]
                        if wkt_geom and wkt_geom.startswith('POLYGON'):
                            # Parse WKT back to Shapely polygon
                            from shapely import wkt
                            geom = wkt.loads(wkt_geom)
                            if hasattr(geom, 'area') and geom.area > 0.000001:
                                voronoi_polygons.append(geom)
                    except Exception as e:
                        print(f"Error parsing PostGIS Voronoi result: {e}")
                        continue

            # Ensure complete coverage
            voronoi_polygons = self._ensure_complete_coverage(voronoi_polygons, polygon)

            print(f"PostGIS Voronoi generated {len(voronoi_polygons)} valid cells with complete coverage")
            return voronoi_polygons

        except Exception as e:
            print(f"Error in PostGIS Voronoi generation: {e}")
            return []
