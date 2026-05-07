# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Emergency Incident Management System - A Flask-based web application with PostGIS for managing emergency response incidents, including search operations, unit tracking, and division assignments. Includes a React Native mobile app (Expo) in the `taskforce-mobile/` directory.

## Development Commands

### Running the Application

**Docker (Recommended):**
```bash
docker-compose up --build
```
- Web UI: http://localhost:5000
- Database: localhost:5432
- Nginx (optional): localhost:80

**Local Development:**
```bash
python app.py
```

### Testing

**Run all tests:**
```bash
pytest
```

**Run specific test file:**
```bash
pytest tests/test_incident.py -v
```

**Run with coverage:**
```bash
pytest --cov=. --cov-report=term-missing
```

**Test markers:**
- `-m "not slow"` - Skip slow tests
- `-m integration` - Run only integration tests
- `-m unit` - Run only unit tests

**Test database:** Runs on port 5433 by default (configured in pytest.ini)

### Mobile App (taskforce-mobile/)

```bash
cd taskforce-mobile
npm install
npx expo start
```

### Database

**Initialize schema:**
```bash
python -c "from models.database import DatabaseManager; DatabaseManager().create_tables()"
```

**Reset database:**
```bash
docker-compose down -v  # Remove volumes
docker-compose up -d database
```

## Architecture

### Request Flow
1. **Flask App** (`app.py`) - Entry point, registers blueprints, error handlers
2. **Routes** (`routes/`) - Blueprint-based API endpoints and views
3. **Models** (`models/`) - Business logic and database operations
4. **Services** (`services/`) - External integrations (geocoding, etc.)
5. **Templates** (`templates/`) - Server-rendered HTML views
6. **Static** (`static/`) - Frontend JavaScript, CSS, assets

### Key Components

**Database Layer (`models/database.py`):**
- `DatabaseManager` - Manages PostgreSQL/PostGIS connections
- Connection pooling via `get_connection()`
- Schema creation via `create_tables()`
- All SQL executed through `execute_query(query, params, fetch=bool)`

**Incident Management (`models/incident.py`):**
- `Incident` class handles incident creation, search area division, hospital assignment
- **Division Strategies**:
  - **Grid-Based**: Traditional grid divisions (default)
  - **Road-Based**: Uses OpenStreetMap road network to create natural divisions bounded by roads
- Search areas divided with user-controlled max divisions (default 8, max 100)
- Division generation supports both `max_divisions` (direct limit) and `area_size_m2` (calculated from area, default 40,000 m²)
- Road-based divisions:
  - Fetch road data from OpenStreetMap via Overpass API
  - Use roads as natural boundaries (no divisions crossing roads)
  - Ensures divisions are accessible from road network
  - Automatic fallback to grid-based if road data unavailable
- PostGIS geometries: POINT for locations, POLYGON for search areas
- Hospital data queried by proximity and specialty (Level 1 trauma, pediatric)

**Unit Tracking (`models/unit.py`, `routes/units.py`):**
- **Unified Status System**: All unit interactions are status updates, including initial check-in
- Status flow: `quarters` → `staging` (check-in) → `assigned` → `operating` → `recovering` → `out_of_service`
- **Auto-transitions**: `assigned` → `operating` when percentage_complete > 0
- **Auto-creation**: Units created automatically during first `staging` status update
- **Division lifecycle**: Units unassigned from divisions when transitioning to `staging`, `out_of_service`, or `quarters`
- Status history tracked in `unit_status_history` table with timestamps and percentage complete

**Blueprint Registration (`routes/__init__.py`):**
All blueprints defined in `ALL_BLUEPRINTS` list and auto-registered in `app.py`:
- `views_bp` - HTML views
- `incidents_bp` - Incident CRUD API
- `units_bp` - Unit status updates (unified endpoint: `/api/unit/<unit_id>/status`)
- `divisions_bp` - Division management
- `geocoding_bp` - Address geocoding via Nominatim
- `hospitals_bp` - Hospital queries
- `health_bp` - Health check endpoint

**Common Route Utilities (`routes/common.py`):**
- `@log_request_data` - Decorator for request/response logging
- `validate_required_fields(data, fields)` - Field validation
- `validate_coordinates(data, required=bool)` - Lat/long validation

### Database Schema

**Core tables:**
- `incidents` - Incident records with PostGIS geometries
- `units` - Unit roster with current status and assignment
- `unit_status_history` - Time-series status updates
- `search_divisions` - Grid divisions within search areas
- `hospitals` - Kentucky hospital database with PostGIS locations
- `incident_hospitals` - Hospital assignments per incident
- `search_progress` - Field reports and progress updates

**PostGIS columns:**
- Use `ST_GeomFromText(wkt, 4326)` for inserts
- Query with `ST_Distance()`, `ST_Within()`, `ST_Intersects()`
- All geometries stored as SRID 4326 (WGS84)

### Frontend

**JavaScript modules** (`static/js/`):
- `common.js` - Shared utilities, QR code generation
- `index.js` - Incident creation form with:
  - Division strategy selector (Grid-Based or Road-Based)
  - Max divisions selector (default 8, range 1-50)
- `unit-checkin.js` - Unit check-in form (creates initial status update)
- `unit-status.js` - Unit status updates
- Incident view inline JS - Division assignment, unit tracking

**Mapbox Integration:**
- Incident location and search area drawing
- Division visualization with 20-color high-contrast palette (optimized for map visibility)
- Unit location tracking
- Max divisions control with +/- buttons to prevent timeout issues
- Road-based division strategy for real-world search operations

### Configuration

**Environment variables** (`.env`):
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - Database connection
- `SEARCH_AREA_SIZE_M2` - Target size for division grid cells (default: 40000)
- `TEAM_SIZE` - Expected team size (default: 4)
- `NOMINATIM_URL` - Geocoding service URL
- `FLASK_ENV`, `FLASK_DEBUG` - Flask settings

**Test configuration** (`pytest.ini`):
- Coverage threshold: 80%
- Test DB port: 5433 (avoid conflicts with dev DB)

## Important Patterns

### Adding New Routes
1. Create blueprint in `routes/` module
2. Import and add to `ALL_BLUEPRINTS` in `routes/__init__.py`
3. Use `@log_request_data` decorator for API endpoints
4. Use `validate_required_fields()` for request validation

### Database Operations
- Always use `DatabaseManager.execute_query()` with parameterized queries
- Use `fetch=True` for SELECT queries
- Use context manager when multiple operations need same connection
- Schema changes: update `DatabaseManager.create_tables()`
- **Batch inserts**: For inserting multiple rows (especially with PostGIS geometries), use `psycopg2.extras.execute_values()` to avoid timeouts. Division saves use batch inserts with page_size=100.

### Unit Status Updates
- **Always use** `/api/unit/<unit_id>/status` endpoint (POST)
- Check-in = status update with `status: "staging"` and full unit details
- Include `incident_id`, `status`, and optional `division_id`, `percentage_complete`
- Business logic auto-applies status transitions

### PostGIS Queries
- Coordinates: longitude first, then latitude (PostGIS convention)
- Use `ST_MakePoint(longitude, latitude)` in queries
- Convert Python coordinates to WKT for inserts: `f"POINT({lon} {lat})"`

### Testing
- Use provided fixtures: `client`, `db_manager`, `incident`
- Tests run against isolated database on port 5433
- Mock external services (geocoding, OSM queries) using `responses` library
