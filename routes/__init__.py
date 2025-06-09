"""Routes package initialization"""

from .views import views_bp
from .incidents import incidents_bp
from .units import units_bp
from .divisions import divisions_bp
from .geocoding import geocoding_bp
from .hospitals import hospitals_bp
from .health import health_bp

# List of all blueprints to register
ALL_BLUEPRINTS = [
    views_bp,
    incidents_bp,
    units_bp,
    divisions_bp,
    geocoding_bp,
    hospitals_bp,
    health_bp
]
