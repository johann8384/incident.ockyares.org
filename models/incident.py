    def _subdivide_single_division(self, division: Dict, search_area: Polygon) -> List[Dict]:
        """Subdivide a single division into two halves"""
        try:
            coords = division.get('coordinates', [])
            if not coords:
                return [division]
            
            # Create polygon from coordinates
            poly = Polygon(coords)
            bounds = poly.bounds
            
            # Determine split direction based on aspect ratio
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            
            if width > height:
                # Split vertically (east/west)
                mid_x = (bounds[0] + bounds[2]) / 2
                west_box = Polygon([
                    (bounds[0], bounds[1]),
                    (mid_x, bounds[1]),
                    (mid_x, bounds[3]),
                    (bounds[0], bounds[3])
                ])
                east_box = Polygon([
                    (mid_x, bounds[1]),
                    (bounds[2], bounds[1]),
                    (bounds[2], bounds[3]),
                    (mid_x, bounds[3])
                ])
                boxes = [west_box, east_box]
            else:
                # Split horizontally (north/south)
                mid_y = (bounds[1] + bounds[3]) / 2
                south_box = Polygon([
                    (bounds[0], bounds[1]),
                    (bounds[2], bounds[1]),
                    (bounds[2], mid_y),
                    (bounds[0], mid_y)
                ])
                north_box = Polygon([
                    (bounds[0], mid_y),
                    (bounds[2], mid_y),
                    (bounds[2], bounds[3]),
                    (bounds[0], bounds[3])
                ])
                boxes = [south_box, north_box]
            
            subdivisions = []
            for i, box in enumerate(boxes):
                try:
                    # Intersect with original division and search area
                    clipped = poly.intersection(box)
                    if search_area:
                        clipped = search_area.intersection(clipped)
                    
                    if hasattr(clipped, 'area') and clipped.area > 0.000001:
                        # Handle MultiPolygon case
                        if hasattr(clipped, 'exterior'):
                            geoms = [clipped]
                        elif hasattr(clipped, 'geoms'):
                            geoms = [g for g in clipped.geoms if hasattr(g, 'area') and g.area > 0.000001]
                        else:
                            continue
                        
                        for geom in geoms:
                            if hasattr(geom, 'exterior'):
                                sub_coords = list(geom.exterior.coords)
                                
                                # Create new division (names will be assigned later)
                                sub_division = {
                                    'division_name': f"temp_{i}",  # Temporary name
                                    'division_id': f"temp_{i}",    # Temporary ID
                                    'coordinates': sub_coords,
                                    'estimated_area_m2': self._calculate_area_m2(geom),
                                    'status': division.get('status', 'unassigned'),
                                    'priority': division.get('priority', 'Low'),
                                    'search_type': division.get('search_type', 'primary'),
                                    'estimated_duration': division.get('estimated_duration', '2 hours'),
                                }
                                subdivisions.append(sub_division)
                
                except Exception as e:
                    print(f"Error creating subdivision {i}: {e}")
                    continue
            
            # If subdivision failed, return original
            if not subdivisions:
                return [division]
            
            return subdivisions
            
        except Exception as e:
            print(f"Error subdividing single division: {e}")
            return [division]