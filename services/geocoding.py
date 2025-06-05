"""
Geocoding Service - Handles address and coordinate operations
"""
import requests
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class GeocodingService:
    """Service for geocoding and reverse geocoding operations"""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.nominatim_base_url = "https://nominatim.openstreetmap.org"
        self.user_agent = "EmergencyIncidentApp/1.0 (Emergency Management System)"
    
    def reverse_geocode(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Convert coordinates to address using Nominatim API
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Dictionary with geocoding results
        """
        try:
            # Validate coordinates
            if not self._validate_coordinates(latitude, longitude):
                return {
                    'success': False,
                    'error': 'Invalid coordinates provided'
                }
            
            # Make request to Nominatim
            url = f"{self.nominatim_base_url}/reverse"
            params = {
                'format': 'json',
                'lat': latitude,
                'lon': longitude,
                'zoom': 18,
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': self.user_agent
            }
            
            response = requests.get(
                url, 
                params=params, 
                headers=headers, 
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract and format address information
                address_info = self._format_address_data(data)
                
                return {
                    'success': True,
                    'address': data.get('display_name', ''),
                    'formatted_address': address_info['formatted'],
                    'address_components': address_info['components'],
                    'raw_data': data
                }
            else:
                logger.warning(f"Nominatim API returned status {response.status_code}")
                return {
                    'success': False,
                    'error': f"Geocoding service returned status {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            logger.error("Geocoding request timed out")
            return {
                'success': False,
                'error': 'Geocoding request timed out'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Geocoding request failed: {e}")
            return {
                'success': False,
                'error': f'Geocoding request failed: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error during geocoding: {e}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def forward_geocode(self, address: str) -> Dict[str, Any]:
        """
        Convert address to coordinates using Nominatim API
        
        Args:
            address: Address string to geocode
            
        Returns:
            Dictionary with geocoding results
        """
        try:
            if not address or len(address.strip()) < 3:
                return {
                    'success': False,
                    'error': 'Address must be at least 3 characters long'
                }
            
            url = f"{self.nominatim_base_url}/search"
            params = {
                'q': address.strip(),
                'format': 'json',
                'addressdetails': 1,
                'limit': 5
            }
            
            headers = {
                'User-Agent': self.user_agent
            }
            
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data:
                    # Process multiple results
                    results = []
                    for item in data:
                        address_info = self._format_address_data(item)
                        results.append({
                            'latitude': float(item['lat']),
                            'longitude': float(item['lon']),
                            'display_name': item.get('display_name', ''),
                            'formatted_address': address_info['formatted'],
                            'address_components': address_info['components'],
                            'importance': item.get('importance', 0)
                        })
                    
                    return {
                        'success': True,
                        'results': results,
                        'count': len(results)
                    }
                else:
                    return {
                        'success': False,
                        'error': 'No results found for the provided address'
                    }
            else:
                return {
                    'success': False,
                    'error': f"Geocoding service returned status {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Geocoding request timed out'
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Geocoding request failed: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def _validate_coordinates(self, latitude: float, longitude: float) -> bool:
        """
        Validate coordinate values
        
        Args:
            latitude: Latitude to validate
            longitude: Longitude to validate
            
        Returns:
            True if coordinates are valid
        """
        try:
            lat = float(latitude)
            lon = float(longitude)
            
            return (-90 <= lat <= 90) and (-180 <= lon <= 180)
        except (ValueError, TypeError):
            return False
    
    def _format_address_data(self, geocode_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format address data from Nominatim response
        
        Args:
            geocode_data: Raw geocoding data from Nominatim
            
        Returns:
            Formatted address information
        """
        address = geocode_data.get('address', {})
        
        # Extract common address components
        components = {
            'house_number': address.get('house_number', ''),
            'road': address.get('road', ''),
            'neighborhood': address.get('neighbourhood', ''),
            'city': address.get('city') or address.get('town') or address.get('village', ''),
            'county': address.get('county', ''),
            'state': address.get('state', ''),
            'postcode': address.get('postcode', ''),
            'country': address.get('country', ''),
            'country_code': address.get('country_code', '')
        }
        
        # Create formatted address
        formatted_parts = []
        
        # Add house number and road
        if components['house_number'] and components['road']:
            formatted_parts.append(f"{components['house_number']} {components['road']}")
        elif components['road']:
            formatted_parts.append(components['road'])
        
        # Add city
        if components['city']:
            formatted_parts.append(components['city'])
        
        # Add state and postcode
        state_zip = []
        if components['state']:
            state_zip.append(components['state'])
        if components['postcode']:
            state_zip.append(components['postcode'])
        
        if state_zip:
            formatted_parts.append(' '.join(state_zip))
        
        # Add country if not US
        if components['country_code'] and components['country_code'].upper() != 'US':
            formatted_parts.append(components['country'])
        
        formatted_address = ', '.join(formatted_parts)
        
        return {
            'formatted': formatted_address,
            'components': components
        }
    
    def get_distance_between_points(self, lat1: float, lon1: float, 
                                  lat2: float, lon2: float) -> float:
        """
        Calculate distance between two coordinate points using Haversine formula
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in kilometers
        """
        import math
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in kilometers
        r = 6371
        
        return c * r
    
    def format_coordinates(self, latitude: float, longitude: float, 
                          format_type: str = 'decimal') -> str:
        """
        Format coordinates in different formats
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            format_type: Format type ('decimal', 'dms', 'utm')
            
        Returns:
            Formatted coordinate string
        """
        if format_type == 'decimal':
            return f"{latitude:.6f}, {longitude:.6f}"
        elif format_type == 'dms':
            return self._decimal_to_dms(latitude, longitude)
        else:
            return f"{latitude:.6f}, {longitude:.6f}"
    
    def _decimal_to_dms(self, latitude: float, longitude: float) -> str:
        """
        Convert decimal coordinates to degrees, minutes, seconds format
        
        Args:
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            
        Returns:
            DMS formatted string
        """
        def dd_to_dms(dd: float, is_longitude: bool = False) -> str:
            direction = ''
            if is_longitude:
                direction = 'E' if dd >= 0 else 'W'
            else:
                direction = 'N' if dd >= 0 else 'S'
            
            dd = abs(dd)
            degrees = int(dd)
            minutes_float = (dd - degrees) * 60
            minutes = int(minutes_float)
            seconds = (minutes_float - minutes) * 60
            
            return f"{degrees}°{minutes:02d}'{seconds:05.2f}\"{direction}"
        
        lat_dms = dd_to_dms(latitude, False)
        lon_dms = dd_to_dms(longitude, True)
        
        return f"{lat_dms}, {lon_dms}"


# Convenience function for simple reverse geocoding
def reverse_geocode_simple(latitude: float, longitude: float) -> Optional[str]:
    """
    Simple reverse geocoding function that returns just the address string
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        
    Returns:
        Address string or None if failed
    """
    geocoder = GeocodingService()
    result = geocoder.reverse_geocode(latitude, longitude)
    
    if result['success']:
        return result.get('address')
    else:
        logger.warning(f"Reverse geocoding failed: {result.get('error')}")
        return None


# Convenience function for forward geocoding
def geocode_address_simple(address: str) -> Optional[Tuple[float, float]]:
    """
    Simple forward geocoding function that returns coordinates
    
    Args:
        address: Address string to geocode
        
    Returns:
        Tuple of (latitude, longitude) or None if failed
    """
    geocoder = GeocodingService()
    result = geocoder.forward_geocode(address)
    
    if result['success'] and result['results']:
        first_result = result['results'][0]
        return (first_result['latitude'], first_result['longitude'])
    else:
        logger.warning(f"Forward geocoding failed: {result.get('error')}")
        return None
