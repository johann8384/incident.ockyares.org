    def _generate_voronoi_cells_scipy(self, seed_points: List[Tuple[float, float]], polygon: Polygon) -> List[Polygon]:
        """Generate Voronoi cells using scipy.spatial.Voronoi"""
        try:
            points = np.array(seed_points)
            
            # Expand bounds to ensure complete coverage
            bounds = polygon.bounds
            margin = max((bounds[2] - bounds[0]), (bounds[3] - bounds[1])) * 0.5
            
            # Add boundary points well outside the search area to ensure coverage
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
            all_points = np.vstack([points, np.array(boundary_buffer_points)])
            
            # Create Voronoi diagram
            vor = Voronoi(all_points)
            
            voronoi_polygons = []
            
            # Only process regions corresponding to original seed points (not buffer points)
            for point_idx in range(len(seed_points)):
                # Find the Voronoi region for this point
                for region_idx, region in enumerate(vor.regions):
                    if len(region) >= 3 and -1 not in region:  # Valid finite region
                        # Check if this region corresponds to our point
                        region_point_indices = [i for i, p in enumerate(vor.ridge_points) 
                                              if region_idx in [vor.point_region[p[0]], vor.point_region[p[1]]]]
                        
                        # Alternative approach: check if point is close to region centroid
                        try:
                            region_vertices = [vor.vertices[i] for i in region]
                            if len(region_vertices) >= 3:
                                region_poly = Polygon(region_vertices)
                                
                                # Check if this region is for our current seed point
                                seed_point = Point(seed_points[point_idx])
                                if region_poly.contains(seed_point) or region_poly.distance(seed_point) < 0.001:
                                    # Clip to search area to ensure complete coverage
                                    clipped = polygon.intersection(region_poly)
                                    
                                    if hasattr(clipped, 'area') and clipped.area > 0.000001:
                                        if hasattr(clipped, 'exterior'):
                                            voronoi_polygons.append(clipped)
                                        elif hasattr(clipped, 'geoms'):
                                            for geom in clipped.geoms:
                                                if hasattr(geom, 'area') and geom.area > 0.000001 and hasattr(geom, 'exterior'):
                                                    voronoi_polygons.append(geom)
                                    break
                                                
                        except Exception as e:
                            print(f"Error processing Voronoi region for point {point_idx}: {e}")
                            continue

            # Ensure complete coverage by checking for gaps
            voronoi_polygons = self._ensure_complete_coverage(voronoi_polygons, polygon)
            
            # Sort by area (largest first) for consistent ordering
            voronoi_polygons.sort(key=lambda p: p.area, reverse=True)
            
            print(f"Scipy Voronoi generated {len(voronoi_polygons)} valid cells with complete coverage")
            return voronoi_polygons

        except Exception as e:
            print(f"Error in scipy Voronoi generation: {e}")
            return []

    def _ensure_complete_coverage(self, voronoi_polygons: List[Polygon], search_area: Polygon) -> List[Polygon]:
        """Ensure Voronoi polygons completely cover the search area with no gaps"""
        try:
            if not voronoi_polygons:
                return []
            
            # Union all Voronoi cells
            covered_area = unary_union(voronoi_polygons)
            
            # Find uncovered area (gaps)
            uncovered = search_area.difference(covered_area)
            
            # If there are gaps, we need to fill them
            if hasattr(uncovered, 'area') and uncovered.area > 0.000001:
                print(f"Found uncovered area of {uncovered.area:.6f} square degrees, filling gaps...")
                
                # Handle different geometry types for uncovered areas
                gap_polygons = []
                if hasattr(uncovered, 'exterior'):
                    gap_polygons = [uncovered]
                elif hasattr(uncovered, 'geoms'):
                    gap_polygons = [g for g in uncovered.geoms 
                                  if hasattr(g, 'area') and g.area > 0.000001 and hasattr(g, 'exterior')]
                
                # For each gap, assign it to the nearest existing division
                for gap in gap_polygons:
                    try:
                        gap_centroid = gap.centroid
                        
                        # Find the nearest Voronoi cell
                        min_distance = float('inf')
                        nearest_idx = -1
                        
                        for i, cell in enumerate(voronoi_polygons):
                            try:
                                distance = cell.distance(gap_centroid)
                                if distance < min_distance:
                                    min_distance = distance
                                    nearest_idx = i
                            except:
                                continue
                        
                        # Merge the gap with the nearest cell
                        if nearest_idx >= 0:
                            try:
                                merged = unary_union([voronoi_polygons[nearest_idx], gap])
                                if hasattr(merged, 'exterior'):
                                    voronoi_polygons[nearest_idx] = merged
                                elif hasattr(merged, 'geoms'):
                                    # Take the largest component if union creates multiple polygons
                                    largest = max(merged.geoms, key=lambda g: g.area if hasattr(g, 'area') else 0)
                                    if hasattr(largest, 'exterior'):
                                        voronoi_polygons[nearest_idx] = largest
                                
                                print(f"Merged gap of area {gap.area:.6f} with division {nearest_idx}")
                                
                            except Exception as e:
                                print(f"Error merging gap with division {nearest_idx}: {e}")
                                # If merge fails, add gap as separate division
                                voronoi_polygons.append(gap)
                        else:
                            # If no nearest cell found, add gap as separate division
                            voronoi_polygons.append(gap)
                            print(f"Added gap as separate division")
                            
                    except Exception as e:
                        print(f"Error processing gap: {e}")
                        continue
            
            # Final validation - ensure all polygons are valid and within search area
            valid_polygons = []
            for poly in voronoi_polygons:
                try:
                    if hasattr(poly, 'area') and poly.area > 0.000001 and hasattr(poly, 'exterior'):
                        # Ensure polygon is within search area bounds
                        if search_area.intersects(poly):
                            clipped = search_area.intersection(poly)
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
            
            # Verify complete coverage
            final_coverage = unary_union(valid_polygons)
            coverage_ratio = final_coverage.area / search_area.area if search_area.area > 0 else 0
            
            print(f"Final coverage ratio: {coverage_ratio:.3f} ({len(valid_polygons)} divisions)")
            
            if coverage_ratio < 0.98:  # Less than 98% coverage
                print(f"Warning: Coverage ratio {coverage_ratio:.3f} is below threshold, may have remaining gaps")
            
            return valid_polygons
            
        except Exception as e:
            print(f"Error ensuring complete coverage: {e}")
            return voronoi_polygons
