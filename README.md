# Fresh Start - Incident Management System

A complete full-stack application with PostGIS, PostgREST, Flask backend, and React frontend.

## Architecture

- **PostGIS**: PostgreSQL with geospatial extensions
- **PostgREST**: Auto-generated REST API for PostgreSQL
- **Flask**: Python backend with incident management endpoints
- **React**: Frontend user interface
- **Nginx**: Reverse proxy routing traffic

## Project Context & History

This is a **fresh start** branch that replaced a more complex incident management system. The original system had extensive features including:
- QR code generation for field teams
- Search area division management
- GeoServer integration
- Complex incident workflows
- Security scanning and CI/CD

This fresh start focuses on **core functionality** with a clean, simple foundation that can be extended.

## Database Schema Context

**Current Schema:**
- `incidents` table with basic fields (id, name, description, location as POINT geometry)
- PostgREST roles configured (`web_anon`, `authenticator`)
- Sample data includes Kentucky coordinates (Carrollton area: ~37.839, -84.273)

**Geographic Context:**
- Primary use case: Kentucky ARES (Amateur Radio Emergency Service)
- Target area: Kentucky emergency response
- Coordinate system: EPSG:4326 (WGS84)

## Technology Decisions & Preferences

**Backend:**
- Flask chosen for simplicity (previous version was more complex)
- PostgREST provides direct database API access
- PostgreSQL preferred database (user preference noted)
- Python dependencies kept minimal

**Frontend:**
- React with functional components
- Axios for API calls
- No complex state management (yet)
- Prepared for Apache Cordova mobile app generation (user preference)

**Container Strategy:**
- Development-focused docker-compose setup
- Separate Dockerfile.dev for React hot reloading
- Volume mounts for development
- Health checks on all services

## Port Allocation

- `80`: Nginx (main entry point)
- `3000`: PostgREST API
- `3001`: React dev server (internal)
- `5000`: Flask backend (internal)
- `5432`: PostgreSQL (exposed for development)

## API Design Patterns

**Flask API (`/api/`):**
- RESTful endpoints
- JSON responses
- Error handling with proper HTTP codes
- CORS enabled for React development

**PostgREST API (`/postgrest/`):**
- Auto-generated from database schema
- Row Level Security ready
- Direct database queries
- JWT authentication capable

## File Structure Context

```
├── docker-compose.yml          # Main orchestration
├── database/init/              # Database initialization scripts
├── backend/                    # Flask application
│   ├── app.py                 # Main Flask app with basic CRUD
│   ├── requirements.txt       # Python dependencies
│   └── Dockerfile             # Backend container
├── frontend/                   # React application
│   ├── src/App.js            # Main React component
│   ├── package.json          # Node dependencies
│   └── Dockerfile.dev        # Frontend container
└── nginx/nginx.conf           # Reverse proxy configuration
```

## Development Workflow Context

**Local Development:**
- All services run in containers for consistency
- React has hot reloading enabled
- Database persists in named volume
- Logs accessible via `docker-compose logs [service]`

**Future Extension Points:**
- Authentication system (PostgREST JWT ready)
- Mobile app via Cordova (React foundation ready)
- Geographic features (PostGIS ready)
- Real-time updates (WebSocket endpoints can be added)

## Known Limitations & Future Considerations

**Current Limitations:**
- No authentication implemented
- Basic error handling
- No data validation on frontend
- No testing framework set up
- No CI/CD pipeline

**Ready for Extension:**
- PostgREST provides instant API expansion when schema changes
- React component structure supports complex UI additions
- PostGIS ready for advanced geospatial features
- Container setup supports additional services

## User Context & Preferences

- **User Background**: Drone company software development, Go backend preference, React frontend, Postgres database
- **Target Use Case**: Emergency communications and incident tracking for amateur radio services
- **Mobile Strategy**: Apache Cordova for native mobile apps
- **Geographic Focus**: Kentucky region emergency response

## Quick Start

```bash
# Clone and checkout the fresh-start branch
git clone https://github.com/johann8384/incident.ockyares.org.git
cd incident.ockyares.org
git checkout fresh-start

# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

## Service URLs

- **Frontend**: http://localhost (React app)
- **Flask API**: http://localhost/api/incidents
- **PostgREST API**: http://localhost/postgrest/incidents
- **Health Check**: http://localhost/health
- **Direct PostgREST**: http://localhost:3000/incidents
- **Direct Flask**: http://localhost:5000/api/incidents

## Features

### Frontend (React)
- System status dashboard
- Create new incidents
- View incident list
- Real-time status monitoring

### Backend (Flask)
- Health check endpoint
- Incident CRUD operations
- PostGIS integration
- CORS enabled for frontend

### Database (PostGIS)
- Spatial data support
- Sample incident data
- PostgREST permissions setup

## Development

### Backend Development
```bash
cd backend
pip install -r requirements.txt
python app.py
```

### Frontend Development
```bash
cd frontend
npm install
npm start
```

### Database Access
```bash
# Connect to PostgreSQL
docker-compose exec postgis psql -U postgres -d incident_app

# View incidents
SELECT * FROM incidents;
```

## Testing the Setup

1. Visit http://localhost to see the React frontend
2. Check system status (should show green checkmarks)
3. Create a new incident using the form
4. View the incident list

## API Examples

### Flask API
```bash
# Get incidents
curl http://localhost:5000/api/incidents

# Create incident
curl -X POST http://localhost:5000/api/incidents \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Incident", "description": "Test"}'
```

### PostgREST API
```bash
# Get incidents
curl http://localhost:3000/incidents

# Create incident (requires authentication)
curl -X POST http://localhost:3000/incidents \
  -H "Content-Type: application/json" \
  -d '{"name": "PostgREST Incident", "description": "Via PostgREST"}'
```

## Troubleshooting

### Services not starting
```bash
docker-compose logs [service-name]
```

### Database connection issues
```bash
docker-compose exec postgis pg_isready -U postgres
```

### Port conflicts
If ports are in use, update the docker-compose.yml file with different ports.

## Next Steps

This fresh start provides:
- ✅ Working PostGIS database with sample data
- ✅ PostgREST API with proper permissions
- ✅ Flask backend with incident management
- ✅ React frontend with full UI
- ✅ Nginx routing between services

You can now build upon this foundation to add:
- Authentication and authorization
- More complex incident workflows
- Mapping and geospatial features
- Real-time updates with WebSockets
- Mobile app integration
