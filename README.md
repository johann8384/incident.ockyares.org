# Fresh Start - Incident Management System

A complete full-stack application with PostGIS, PostgREST, Flask backend, and React frontend.

## Architecture

- **PostGIS**: PostgreSQL with geospatial extensions
- **PostgREST**: Auto-generated REST API for PostgreSQL
- **Flask**: Python backend with incident management endpoints
- **React**: Frontend user interface
- **Nginx**: Reverse proxy routing traffic

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
