    def _fetch_building_data(self, polygon: Polygon) -> List[Dict]:
        """Fetch building data from Overpass API (reused from previous implementation)"""
        try:
            bounds = polygon.bounds
            cache_key = hashlib.md5(str(bounds).encode()).hexdigest()
            
            if cache_key in self._building_cache:
                return self._building_cache[cache_key]

            overpass_url = "https://overpass-api.de/api/interpreter"
            
            # More comprehensive building query
            query = f"""
            [out:json][timeout:30];
            (
              way["building"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
              relation["building"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
              way["amenity"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
              way["shop"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
              way["office"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
            );
            out geom;
            """

            print(f"Querying buildings in bounds: {bounds}")
            print(f"Query URL: {overpass_url}")
            
            response = requests.post(overpass_url, data=query, timeout=35)
            
            print(f"Building query response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Overpass API error for buildings: {response.status_code}")
                print(f"Response text: {response.text[:500]}")
                return []

            data = response.json()
            print(f"Overpass returned {len(data.get('elements', []))} elements")
            
            buildings = []

            for element in data.get("elements", []):
                try:
                    building_data = self._process_building_element(element, polygon)
                    if building_data:
                        buildings.append(building_data)
                except Exception as e:
                    print(f"Error processing building element: {e}")
                    continue

            # If no buildings found, let's try a broader search
            if not buildings:
                print("No buildings found with standard query, trying broader search...")
                broader_query = f"""
                [out:json][timeout:30];
                (
                  way({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
                  relation({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
                );
                out geom;
                """
                
                response = requests.post(overpass_url, data=broader_query, timeout=35)
                if response.status_code == 200:
                    broader_data = response.json()
                    print(f"Broader query returned {len(broader_data.get('elements', []))} total elements")
                    
                    # Look for any structures
                    for element in broader_data.get("elements", []):
                        tags = element.get("tags", {})
                        if any(key in tags for key in ["building", "amenity", "shop", "office", "leisure", "tourism"]):
                            try:
                                building_data = self._process_building_element(element, polygon)
                                if building_data:
                                    buildings.append(building_data)
                            except Exception as e:
                                continue

            # Cache the result
            self._building_cache[cache_key] = buildings
            total_area = sum(b['area_m2'] for b in buildings) if buildings else 0
            print(f"Final result: {len(buildings)} buildings, total area: {total_area:,.0f} sq meters")
            
            # If still no buildings, create some synthetic ones for testing
            if not buildings and len(data.get("elements", [])) == 0:
                print("No OSM data found - this might be a rural area or OSM data gap")
                print("Creating synthetic structures for testing...")
                buildings = self._create_synthetic_buildings(polygon)
            
            return buildings

        except Exception as e:
            print(f"Failed to fetch building data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _create_synthetic_buildings(self, polygon: Polygon) -> List[Dict]:
        """Create synthetic buildings for testing when no OSM data available"""
        try:
            buildings = []
            bounds = polygon.bounds
            
            # Create a grid of synthetic buildings
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            
            # Create buildings every ~200m (0.002 degrees)
            spacing = 0.002
            cols = max(1, int(width / spacing))
            rows = max(1, int(height / spacing))
            
            for row in range(rows):
                for col in range(cols):
                    if len(buildings) >= 20:  # Limit synthetic buildings
                        break
                        
                    x = bounds[0] + (col + 0.5) * (width / cols)
                    y = bounds[1] + (row + 0.5) * (height / rows)
                    
                    # Create small building polygon
                    building_size = 0.0005  # ~50m x 50m
                    building_coords = [
                        (x - building_size, y - building_size),
                        (x + building_size, y - building_size), 
                        (x + building_size, y + building_size),
                        (x - building_size, y + building_size),
                        (x - building_size, y - building_size)
                    ]
                    
                    building_poly = Polygon(building_coords)
                    
                    # Check if building is within search area
                    if polygon.contains(building_poly.centroid):
                        area_m2 = self._calculate_area_m2(building_poly)
                        
                        buildings.append({
                            "geometry": building_poly,
                            "type": "synthetic_house",
                            "area_m2": area_m2,
                            "levels": 2,
                            "searchable_area_m2": area_m2 * 2,
                            "centroid": building_poly.centroid,
                            "tags": {"building": "synthetic"}
                        })
            
            print(f"Created {len(buildings)} synthetic buildings for testing")
            return buildings
            
        except Exception as e:
            print(f"Error creating synthetic buildings: {e}")
            return []