    def _create_road_aware_divisions_preview(
        self, polygon: Polygon, num_divisions: int, incident_location: Point = None, roads: List[LineString] = None
    ) -> List[Dict]:
        """Create road-aware divisions using roads as natural boundaries"""
        try:
            if not roads:
                return []

            print(f"Creating road-aware divisions with {len(roads)} roads")
            
            # Filter roads to only major ones within our polygon
            major_roads = []
            for road in roads:
                try:
                    # Only use roads that significantly cross our polygon
                    intersection = polygon.intersection(road)
                    if isinstance(intersection, LineString) and intersection.length > 0.001:  # Significant intersection
                        major_roads.append(road)
                    elif hasattr(intersection, 'geoms'):
                        for geom in intersection.geoms:
                            if isinstance(geom, LineString) and geom.length > 0.001:
                                major_roads.append(road)
                                break
                except Exception as e:
                    print(f"Error filtering road: {e}")
                    continue

            print(f"Filtered to {len(major_roads)} major roads")
            
            if not major_roads:
                return []

            # Create a simpler approach: use roads to create natural division boundaries
            bounds = polygon.bounds
            divisions = []
            
            # Start with a base grid but modify it based on roads
            cols = int((num_divisions**0.5)) if num_divisions > 1 else 1
            rows = int(num_divisions / cols) + (1 if num_divisions % cols else 0)

            width = (bounds[2] - bounds[0]) / cols
            height = (bounds[3] - bounds[1]) / rows

            division_counter = 0
            
            # Create horizontal and vertical division lines, but snap them to roads
            division_lines = []
            
            # Create vertical division lines (adjusted by roads)
            for i in range(1, cols):
                x = bounds[0] + i * width
                base_line = LineString([(x, bounds[1]), (x, bounds[3])])
                
                # Find nearest major road and snap to it if close
                best_road = None
                min_distance = float('inf')
                
                for road in major_roads:
                    try:
                        distance = base_line.distance(road)
                        if distance < min_distance and distance < width * 0.3:  # Within 30% of grid width
                            min_distance = distance
                            best_road = road
                    except:
                        continue
                
                if best_road:
                    # Use the road as the division line
                    road_intersection = polygon.intersection(best_road)
                    if isinstance(road_intersection, LineString):
                        division_lines.append(road_intersection)
                    elif hasattr(road_intersection, 'geoms'):
                        for geom in road_intersection.geoms:
                            if isinstance(geom, LineString):
                                division_lines.append(geom)
                else:
                    # Use original grid line
                    grid_intersection = polygon.intersection(base_line)
                    if isinstance(grid_intersection, LineString):
                        division_lines.append(grid_intersection)

            # Create horizontal division lines (adjusted by roads)
            for i in range(1, rows):
                y = bounds[1] + i * height
                base_line = LineString([(bounds[0], y), (bounds[2], y)])
                
                # Find nearest major road and snap to it if close
                best_road = None
                min_distance = float('inf')
                
                for road in major_roads:
                    try:
                        distance = base_line.distance(road)
                        if distance < min_distance and distance < height * 0.3:  # Within 30% of grid height
                            min_distance = distance
                            best_road = road
                    except:
                        continue
                
                if best_road:
                    # Use the road as the division line
                    road_intersection = polygon.intersection(best_road)
                    if isinstance(road_intersection, LineString):
                        division_lines.append(road_intersection)
                    elif hasattr(road_intersection, 'geoms'):
                        for geom in road_intersection.geoms:
                            if isinstance(geom, LineString):
                                division_lines.append(geom)
                else:
                    # Use original grid line
                    grid_intersection = polygon.intersection(base_line)
                    if isinstance(grid_intersection, LineString):
                        division_lines.append(grid_intersection)

            print(f"Created {len(division_lines)} division lines")

            # If we have division lines, try to use them to create polygons
            if division_lines:
                try:
                    # Extend division lines to ensure they create complete boundaries
                    extended_lines = []
                    polygon_boundary = polygon.boundary
                    
                    for line in division_lines:
                        coords = list(line.coords)
                        if len(coords) >= 2:
                            # Extend line to polygon boundary
                            start_point = Point(coords[0])
                            end_point = Point(coords[-1])
                            
                            # Extend line by 10% in both directions
                            dx = coords[-1][0] - coords[0][0]
                            dy = coords[-1][1] - coords[0][1]
                            
                            if abs(dx) > 0.0001 or abs(dy) > 0.0001:
                                length_factor = 0.1
                                extended_start = (coords[0][0] - dx * length_factor, coords[0][1] - dy * length_factor)
                                extended_end = (coords[-1][0] + dx * length_factor, coords[-1][1] + dy * length_factor)
                                extended_lines.append(LineString([extended_start] + coords + [extended_end]))
                            else:
                                extended_lines.append(line)
                    
                    # Add polygon boundary to help with polygonization
                    if hasattr(polygon.boundary, 'geoms'):
                        for boundary_part in polygon.boundary.geoms:
                            if isinstance(boundary_part, LineString):
                                extended_lines.append(boundary_part)
                    else:
                        extended_lines.append(polygon.boundary)
                    
                    # Create polygons from lines
                    try:
                        result_polygons = list(polygonize(extended_lines))
                        print(f"Polygonize created {len(result_polygons)} polygons")
                        
                        # Filter and validate polygons
                        valid_polygons = []
                        for poly in result_polygons:
                            try:
                                if hasattr(poly, 'area') and poly.area > 0.000001:
                                    # Check if polygon is within our search area
                                    if polygon.contains(poly.centroid) or polygon.intersects(poly):
                                        # Clip to our search area
                                        clipped = polygon.intersection(poly)
                                        if hasattr(clipped, 'area') and clipped.area > 0.000001:
                                            if hasattr(clipped, 'exterior'):
                                                valid_polygons.append(clipped)
                                            elif hasattr(clipped, 'geoms'):
                                                for geom in clipped.geoms:
                                                    if hasattr(geom, 'area') and geom.area > 0.000001 and hasattr(geom, 'exterior'):
                                                        valid_polygons.append(geom)
                            except Exception as e:
                                print(f"Error validating polygon: {e}")
                                continue
                        
                        print(f"Found {len(valid_polygons)} valid polygons")
                        
                        # If we have valid polygons but not enough, subdivide them
                        if valid_polygons and len(valid_polygons) < num_divisions:
                            print(f"Need {num_divisions} divisions but only got {len(valid_polygons)}, subdividing...")
                            valid_polygons = self._subdivide_polygons(valid_polygons, num_divisions)
                            print(f"After subdivision: {len(valid_polygons)} polygons")
                        
                        # Create divisions from valid polygons
                        if valid_polygons and len(valid_polygons) >= max(1, num_divisions // 2):
                            # Sort by area (largest first) and take up to num_divisions
                            valid_polygons.sort(key=lambda p: p.area, reverse=True)
                            
                            for i, geom in enumerate(valid_polygons[:num_divisions]):
                                if division_counter >= num_divisions:
                                    break
                                    
                                try:
                                    coords = list(geom.exterior.coords)
                                    
                                    division_letter = chr(65 + division_counter)
                                    division_name = f"Division {division_letter}"
                                    division_id = f"DIV-{division_letter}"

                                    priority = self._calculate_division_priority(
                                        geom, incident_location, divisions
                                    )

                                    divisions.append({
                                        "division_name": division_name,
                                        "division_id": division_id,
                                        "coordinates": coords,
                                        "estimated_area_m2": self._calculate_area_m2(geom),
                                        "status": "unassigned",
                                        "priority": priority,
                                        "search_type": "primary",
                                        "estimated_duration": "2 hours",
                                    })

                                    division_counter += 1
                                    
                                except Exception as e:
                                    print(f"Error creating division from polygon: {e}")
                                    continue
                        
                    except Exception as e:
                        print(f"Polygonize failed: {e}")
                
                except Exception as e:
                    print(f"Error in polygon creation: {e}")

            # If road-based approach didn't work well, ensure we have some divisions
            if len(divisions) < max(1, num_divisions // 3):  # More lenient threshold
                print("Road-based approach didn't create enough divisions, falling back to grid")
                return []

            print(f"Successfully created {len(divisions)} road-aware divisions")
            return divisions

        except Exception as e:
            print(f"Road-aware division creation failed: {e}")
            return []

    def _subdivide_polygons(self, polygons: List[Polygon], target_count: int) -> List[Polygon]:
        """Subdivide polygons to reach target count"""
        try:
            result_polygons = polygons.copy()
            
            while len(result_polygons) < target_count:
                # Find the largest polygon to subdivide
                if not result_polygons:
                    break
                    
                largest_poly = max(result_polygons, key=lambda p: p.area)
                result_polygons.remove(largest_poly)
                
                # Subdivide the largest polygon
                subdivided = self._subdivide_single_polygon(largest_poly)
                if subdivided and len(subdivided) > 1:
                    result_polygons.extend(subdivided)
                    print(f"Subdivided polygon into {len(subdivided)} parts")
                else:
                    # If subdivision failed, put the original back and stop
                    result_polygons.append(largest_poly)
                    break
                    
                # Safety check to prevent infinite loops
                if len(result_polygons) > target_count * 2:
                    break
            
            return result_polygons[:target_count]  # Return up to target count
            
        except Exception as e:
            print(f"Error in polygon subdivision: {e}")
            return polygons

    def _subdivide_single_polygon(self, polygon: Polygon) -> List[Polygon]:
        """Subdivide a single polygon into smaller parts"""
        try:
            bounds = polygon.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            
            # Determine subdivision direction based on aspect ratio
            if width > height:
                # Split vertically (north/south)
                mid_x = bounds[0] + width / 2
                split_line = LineString([(mid_x, bounds[1] - height * 0.1), (mid_x, bounds[3] + height * 0.1)])
                direction = "east/west"
            else:
                # Split horizontally (east/west)  
                mid_y = bounds[1] + height / 2
                split_line = LineString([(bounds[0] - width * 0.1, mid_y), (bounds[2] + width * 0.1, mid_y)])
                direction = "north/south"
            
            # Create a buffer around the split line to ensure clean cuts
            split_buffer = split_line.buffer(0.0001)
            
            # Use the split line to divide the polygon
            try:
                # Split the polygon using difference operations
                left_poly = polygon.difference(split_buffer)
                right_poly = polygon.difference(split_buffer)
                
                # Alternative approach: use intersection with half-spaces
                if width > height:
                    # Vertical split
                    left_box = Polygon([
                        (bounds[0] - width * 0.1, bounds[1] - height * 0.1),
                        (mid_x, bounds[1] - height * 0.1),
                        (mid_x, bounds[3] + height * 0.1),
                        (bounds[0] - width * 0.1, bounds[3] + height * 0.1)
                    ])
                    right_box = Polygon([
                        (mid_x, bounds[1] - height * 0.1),
                        (bounds[2] + width * 0.1, bounds[1] - height * 0.1),
                        (bounds[2] + width * 0.1, bounds[3] + height * 0.1),
                        (mid_x, bounds[3] + height * 0.1)
                    ])
                else:
                    # Horizontal split
                    left_box = Polygon([
                        (bounds[0] - width * 0.1, bounds[1] - height * 0.1),
                        (bounds[2] + width * 0.1, bounds[1] - height * 0.1),
                        (bounds[2] + width * 0.1, mid_y),
                        (bounds[0] - width * 0.1, mid_y)
                    ])
                    right_box = Polygon([
                        (bounds[0] - width * 0.1, mid_y),
                        (bounds[2] + width * 0.1, mid_y),
                        (bounds[2] + width * 0.1, bounds[3] + height * 0.1),
                        (bounds[0] - width * 0.1, bounds[3] + height * 0.1)
                    ])
                
                left_part = polygon.intersection(left_box)
                right_part = polygon.intersection(right_box)
                
                # Validate the results
                valid_parts = []
                for part in [left_part, right_part]:
                    if hasattr(part, 'area') and part.area > 0.000001:
                        if hasattr(part, 'exterior'):
                            valid_parts.append(part)
                        elif hasattr(part, 'geoms'):
                            # Handle MultiPolygon results
                            for geom in part.geoms:
                                if hasattr(geom, 'area') and geom.area > 0.000001 and hasattr(geom, 'exterior'):
                                    valid_parts.append(geom)
                
                if len(valid_parts) >= 2:
                    print(f"Successfully split polygon {direction}")
                    return valid_parts
                else:
                    print(f"Subdivision failed - insufficient valid parts: {len(valid_parts)}")
                    return [polygon]
                    
            except Exception as e:
                print(f"Error in polygon splitting: {e}")
                return [polygon]
                
        except Exception as e:
            print(f"Error in single polygon subdivision: {e}")
            return [polygon]