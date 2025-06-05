import os
from typing import Dict, List, Optional

import requests

from .database import DatabaseManager


class Hospital:
    """Hospital model for storing and managing Kentucky hospital data"""

    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()
        # Kentucky hospital service endpoints
        self.base_url = "https://services3.arcgis.com/ghsX9CKghMvyYjBU/arcgis/rest/services/Ky_Hospitals_WM/FeatureServer/0/query"

        # Define hospital queries
        self.queries = {
            "all_acute": "LIC_TYPE = 'ACUTE'",
            "level1_trauma": "FACILITYID = '100220' OR FACILITYID = '100121'",
            "level1_pediatric": "FACILITYID = '100234' OR FACILITYID = '100121'",
        }

    def fetch_hospitals_from_ky_service(
        self, query_type: str = "all_acute"
    ) -> List[Dict]:
        """Fetch hospital data from Kentucky GeoJSON service"""
        try:
            params = {
                "where": self.queries.get(query_type, self.queries["all_acute"]),
                "outFields": "FACILITYID,FACILITY,ADDRESS,CITY,COUNTY,ZIP_CODE,PHONE,LIC_TYPE,ACUTE,CRITICAL_ACCESS,TB,CONTACT,AGENCY",
                "outSR": "4326",
                "f": "json",
            }

            headers = {"User-Agent": "EmergencyIncidentApp/1.0"}

            response = requests.get(
                self.base_url, params=params, headers=headers, timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("features", [])

            return []

        except Exception as e:
            print(f"Failed to fetch hospitals from Kentucky service: {e}")
            return []

    def _calculate_distance(
        self, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        """Calculate distance between two points using Haversine formula"""
        import math

        R = 6371  # Earth's radius in kilometers

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def find_closest_hospitals(self, latitude: float, longitude: float) -> Dict:
        """Find closest hospitals for each category"""
        results = {}

        # Get all acute care hospitals
        all_hospitals = self.fetch_hospitals_from_ky_service("all_acute")
        if all_hospitals:
            # Calculate distances and find closest
            hospitals_with_distance = []
            for hospital in all_hospitals:
                if (
                    hospital.get("geometry")
                    and hospital["geometry"].get("x")
                    and hospital["geometry"].get("y")
                ):
                    hospital_lat = hospital["geometry"]["y"]
                    hospital_lng = hospital["geometry"]["x"]
                    distance = self._calculate_distance(
                        latitude, longitude, hospital_lat, hospital_lng
                    )
                    hospital["distance"] = distance
                    hospitals_with_distance.append(hospital)

            # Sort by distance and get closest
            hospitals_with_distance.sort(key=lambda h: h["distance"])
            results["closest"] = (
                hospitals_with_distance[0] if hospitals_with_distance else None
            )

        # Get Level 1 Trauma centers
        trauma_hospitals = self.fetch_hospitals_from_ky_service("level1_trauma")
        if trauma_hospitals:
            trauma_with_distance = []
            for hospital in trauma_hospitals:
                if (
                    hospital.get("geometry")
                    and hospital["geometry"].get("x")
                    and hospital["geometry"].get("y")
                ):
                    hospital_lat = hospital["geometry"]["y"]
                    hospital_lng = hospital["geometry"]["x"]
                    distance = self._calculate_distance(
                        latitude, longitude, hospital_lat, hospital_lng
                    )
                    hospital["distance"] = distance
                    trauma_with_distance.append(hospital)

            trauma_with_distance.sort(key=lambda h: h["distance"])
            results["level1_trauma"] = (
                trauma_with_distance[0] if trauma_with_distance else None
            )

        # Get Level 1 Pediatric centers
        pediatric_hospitals = self.fetch_hospitals_from_ky_service("level1_pediatric")
        if pediatric_hospitals:
            pediatric_with_distance = []
            for hospital in pediatric_hospitals:
                if (
                    hospital.get("geometry")
                    and hospital["geometry"].get("x")
                    and hospital["geometry"].get("y")
                ):
                    hospital_lat = hospital["geometry"]["y"]
                    hospital_lng = hospital["geometry"]["x"]
                    distance = self._calculate_distance(
                        latitude, longitude, hospital_lat, hospital_lng
                    )
                    hospital["distance"] = distance
                    pediatric_with_distance.append(hospital)

            pediatric_with_distance.sort(key=lambda h: h["distance"])
            results["level1_pediatric"] = (
                pediatric_with_distance[0] if pediatric_with_distance else None
            )

        return results

    def cache_hospitals(self, hospitals: List[Dict]) -> bool:
        """Cache hospital data in local database"""
        try:
            for hospital_data in hospitals:
                self.save_hospital(hospital_data)
            return True
        except Exception as e:
            print(f"Failed to cache hospitals: {e}")
            return False

    def get_cached_hospitals(
        self, latitude: float, longitude: float, radius_km: float = 100
    ) -> List[Dict]:
        """Get cached hospitals within radius"""
        try:
            query = """
            SELECT 
                id, name, facility_id, address, city, county, zip_code, phone,
                license_type, latitude, longitude,
                ST_Distance(
                    hospital_location,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                ) / 1000 as distance_km
            FROM hospitals
            WHERE ST_DWithin(
                hospital_location,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                %s * 1000
            )
            ORDER BY distance_km
            """

            params = (longitude, latitude, longitude, latitude, radius_km)
            result = self.db.execute_query(query, params, fetch=True)

            if result:
                hospitals = []
                for row in result:
                    hospital = {
                        "attributes": {
                            "FACILITYID": row["facility_id"],
                            "FACILITY": row["name"],
                            "ADDRESS": row["address"],
                            "CITY": row["city"],
                            "COUNTY": row["county"],
                            "ZIP_CODE": row["zip_code"],
                            "PHONE": row["phone"],
                            "LIC_TYPE": row["license_type"],
                            "distance": row["distance_km"],
                        },
                        "geometry": {
                            "x": float(row["longitude"]),
                            "y": float(row["latitude"]),
                        },
                        "distance": row["distance_km"],
                    }
                    hospitals.append(hospital)

                return hospitals

            return []

        except Exception as e:
            print(f"Failed to get cached hospitals: {e}")
            return []

    def get_hospitals_for_location(
        self,
        latitude: float,
        longitude: float,
        use_cache: bool = True,
        cache_duration_hours: int = 24,
    ) -> Dict:
        """Get hospital data for a location"""
        try:
            # Get closest hospitals using the Kentucky service
            print("Fetching hospital data from Kentucky GeoJSON service...")
            key_hospitals = self.find_closest_hospitals(latitude, longitude)

            # Cache the data if requested
            if use_cache and key_hospitals:
                hospitals_to_cache = [
                    h for h in key_hospitals.values() if h is not None
                ]
                if hospitals_to_cache:
                    self.cache_hospitals(hospitals_to_cache)
                    print(f"Cached {len(hospitals_to_cache)} hospitals")

            return {
                "success": True,
                "hospitals": key_hospitals,
                "total_found": len(
                    [h for h in key_hospitals.values() if h is not None]
                ),
                "source": "kentucky_geojson",
            }

        except Exception as e:
            print(f"Failed to get hospitals for location: {e}")
            return {
                "success": False,
                "error": str(e),
                "hospitals": {},
                "total_found": 0,
            }

    def save_hospital(self, hospital_data: Dict) -> int:
        """Save hospital data to database"""
        try:
            attributes = hospital_data.get("attributes", {})
            geometry = hospital_data.get("geometry", {})

            query = """
            INSERT INTO hospitals (
                facility_id, name, address, city, county, zip_code,
                phone, license_type, latitude, longitude, 
                hospital_location, distance_km
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s
            )
            ON CONFLICT (facility_id) DO UPDATE SET
                name = EXCLUDED.name,
                address = EXCLUDED.address,
                city = EXCLUDED.city,
                county = EXCLUDED.county,
                zip_code = EXCLUDED.zip_code,
                phone = EXCLUDED.phone,
                license_type = EXCLUDED.license_type,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                hospital_location = EXCLUDED.hospital_location,
                distance_km = EXCLUDED.distance_km,
                updated_at = NOW()
            RETURNING id
            """

            params = (
                attributes.get("FACILITYID", ""),
                attributes.get("FACILITY", ""),
                attributes.get("ADDRESS", ""),
                attributes.get("CITY", ""),
                attributes.get("COUNTY", ""),
                attributes.get("ZIP_CODE", ""),
                attributes.get("PHONE", ""),
                attributes.get("LIC_TYPE", ""),
                geometry.get("y", 0.0),  # latitude
                geometry.get("x", 0.0),  # longitude
                geometry.get("x", 0.0),  # longitude for PostGIS point
                geometry.get("y", 0.0),  # latitude for PostGIS point
                hospital_data.get("distance", 0.0),
            )

            result = self.db.execute_query(query, params, fetch=True)
            return result[0]["id"] if result else None

        except Exception as e:
            print(f"Failed to save hospital: {e}")
            return None

    def save_incident_hospitals(self, incident_id: str, hospital_data: Dict) -> bool:
        """Save hospital data associated with an incident"""
        try:
            hospital_ids = {}

            # Save each hospital type
            if hospital_data.get("closest"):
                hospital_id = self.save_hospital(hospital_data["closest"])
                if hospital_id:
                    hospital_ids["closest"] = hospital_id

            if hospital_data.get("level1_trauma"):
                hospital_id = self.save_hospital(hospital_data["level1_trauma"])
                if hospital_id:
                    hospital_ids["level1_trauma"] = hospital_id

            if hospital_data.get("level1_pediatric"):
                hospital_id = self.save_hospital(hospital_data["level1_pediatric"])
                if hospital_id:
                    hospital_ids["level1_pediatric"] = hospital_id

            # Link hospitals to incident
            query = """
            INSERT INTO incident_hospitals (
                incident_id, closest_hospital_id, level1_hospital_id, pediatric_hospital_id
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (incident_id) DO UPDATE SET
                closest_hospital_id = EXCLUDED.closest_hospital_id,
                level1_hospital_id = EXCLUDED.level1_hospital_id,
                pediatric_hospital_id = EXCLUDED.pediatric_hospital_id,
                updated_at = NOW()
            """

            params = (
                incident_id,
                hospital_ids.get("closest"),
                hospital_ids.get("level1_trauma"),
                hospital_ids.get("level1_pediatric"),
            )

            self.db.execute_query(query, params)
            return True

        except Exception as e:
            print(f"Failed to save incident hospitals: {e}")
            return False

    def get_incident_hospitals(self, incident_id: str) -> Dict:
        """Get hospital data for an incident"""
        try:
            query = """
            SELECT 
                h_closest.name as closest_name,
                h_closest.address as closest_address,
                h_closest.city as closest_city,
                h_closest.phone as closest_phone,
                h_closest.distance_km as closest_distance,
                
                h_level1.name as level1_name,
                h_level1.address as level1_address,
                h_level1.city as level1_city,
                h_level1.phone as level1_phone,
                h_level1.distance_km as level1_distance,
                
                h_pediatric.name as pediatric_name,
                h_pediatric.address as pediatric_address,
                h_pediatric.city as pediatric_city,
                h_pediatric.phone as pediatric_phone,
                h_pediatric.distance_km as pediatric_distance
                
            FROM incident_hospitals ih
            LEFT JOIN hospitals h_closest ON ih.closest_hospital_id = h_closest.id
            LEFT JOIN hospitals h_level1 ON ih.level1_hospital_id = h_level1.id
            LEFT JOIN hospitals h_pediatric ON ih.pediatric_hospital_id = h_pediatric.id
            WHERE ih.incident_id = %s
            """

            result = self.db.execute_query(query, (incident_id,), fetch=True)

            if result:
                row = result[0]
                return {
                    "closest": (
                        {
                            "name": row["closest_name"],
                            "address": row["closest_address"],
                            "city": row["closest_city"],
                            "phone": row["closest_phone"],
                            "distance": row["closest_distance"],
                        }
                        if row["closest_name"]
                        else None
                    ),
                    "level1_trauma": (
                        {
                            "name": row["level1_name"],
                            "address": row["level1_address"],
                            "city": row["level1_city"],
                            "phone": row["level1_phone"],
                            "distance": row["level1_distance"],
                        }
                        if row["level1_name"]
                        else None
                    ),
                    "level1_pediatric": (
                        {
                            "name": row["pediatric_name"],
                            "address": row["pediatric_address"],
                            "city": row["pediatric_city"],
                            "phone": row["pediatric_phone"],
                            "distance": row["pediatric_distance"],
                        }
                        if row["pediatric_name"]
                        else None
                    ),
                }

            return {}

        except Exception as e:
            print(f"Failed to get incident hospitals: {e}")
            return {}
