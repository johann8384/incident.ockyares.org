    def _create_grid_divisions_preview(self, polygon: Polygon, num_divisions: int) -> List[Dict]:
        """Create grid-based divisions for preview"""
        divisions = []
        bounds = polygon.bounds

        # Ensure polygon is valid
        if not polygon.is_valid:
            polygon = polygon.buffer(0)  # Fix invalid geometry

        # Calculate grid dimensions
        cols = int((num_divisions**0.5)) if num_divisions > 1 else 1
        rows = int(num_divisions / cols) + (1 if num_divisions % cols else 0)

        width = (bounds[2] - bounds[0]) / cols
        height = (bounds[3] - bounds[1]) / rows

        division_counter = 0
        for row in range(rows):
            for col in range(cols):
                if division_counter >= num_divisions:
                    break

                # Create grid cell with small buffer to avoid edge cases
                x1 = bounds[0] + col * width
                y1 = bounds[1] + row * height
                x2 = x1 + width
                y2 = y1 + height

                cell = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])

                # Ensure cell is valid
                if not cell.is_valid:
                    cell = cell.buffer(0)

                try:
                    # Clip to search area with safety checks
                    if polygon.intersects(cell):
                        clipped = polygon.intersection(cell)
                        
                        # Handle different geometry types returned by intersection
                        if hasattr(clipped, "area") and clipped.area > 0:
                            # Only process if it's a valid polygon-like geometry
                            if hasattr(clipped, "exterior"):
                                coords = list(clipped.exterior.coords)
                            elif hasattr(clipped, "geoms"):
                                # MultiPolygon case - take the largest polygon
                                largest = max(clipped.geoms, key=lambda g: g.area if hasattr(g, 'area') else 0)
                                if hasattr(largest, "exterior"):
                                    coords = list(largest.exterior.coords)
                                    clipped = largest
                                else:
                                    continue
                            else:
                                # Fallback to grid cell
                                coords = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
                                clipped = cell

                            division_letter = chr(65 + division_counter)  # A, B, C, etc.
                            division_name = f"Division {division_letter}"
                            division_id = f"DIV-{division_letter}"

                            divisions.append({
                                "division_name": division_name,
                                "division_id": division_id,
                                "coordinates": coords,
                                "estimated_area_m2": self._calculate_area_m2(clipped),
                                "status": "unassigned",
                                "priority": 1,
                                "search_type": "primary",
                                "estimated_duration": "2 hours"
                            })

                            division_counter += 1
                
                except Exception as e:
                    print(f"Error processing grid cell {row},{col}: {e}")
                    # Skip this cell and continue
                    continue

        return divisions