# Unit Status Management Feature

This feature adds comprehensive unit status tracking and management capabilities to the Emergency Incident Management System.

## Overview

The unit status system allows incident commanders to:
- Create and manage responding units
- Track unit status throughout incident lifecycle
- Assign units to search divisions
- Monitor unit progress and location
- Maintain accountability for all resources

## Unit Status Workflow

### Status Types
- **Staging**: Unit has arrived on scene and checked in
- **Assigned**: Unit has been assigned to a specific division
- **Operating**: Unit is actively working their assigned division
- **Recovering**: Unit has completed their assignment and is preparing for next task
- **Out of Service**: Unit is temporarily unavailable but still part of incident
- **Quarters**: Unit has been released from incident

### Standard Workflow
1. Unit arrives → **Staging**
2. Resources Officer assigns division → **Assigned** 
3. Unit begins work → **Operating** (with % complete tracking)
4. Work completed → **Recovering**
5. Ready for new assignment → **Staging** (repeat as needed)
6. Released from incident → **Quarters**

## Database Schema

### Tables Added
- `units`: Core unit information and current status
- `unit_status_history`: Complete audit trail of all status changes
- `search_divisions`: Modified to include `assigned_unit_id`

### Key Fields
- Unit identification and contact info
- Current status and incident assignment
- Geographic location tracking
- Progress percentage for operating units
- Timestamped status history with notes

## API Endpoints

### Unit Management
- `POST /api/unit/create` - Create new unit
- `GET /api/incident/{id}/units` - Get all units for incident
- `GET /api/unit/{id}/history` - Get unit status history

### Status Updates
- `POST /api/unit/{id}/status` - Update unit status with location/notes
- `POST /api/incident/{id}/assign-division` - Assign unit to division

### Data Format Examples

#### Create Unit
```json
{
  "unit_id": "ENG-101",
  "unit_name": "Engine 101", 
  "unit_type": "Engine",
  "unit_leader": "Captain Smith",
  "contact_info": "Radio Channel 1"
}
```

#### Status Update
```json
{
  "incident_id": "INC-001",
  "status": "operating",
  "division_id": "DIV-A", 
  "percentage_complete": 75,
  "latitude": 37.7749,
  "longitude": -122.4194,
  "notes": "Making good progress on north side",
  "user_name": "Officer Jones"
}
```

## User Interface

### Unit Status Update Page
- `/incident/{id}/unit-status`
- Form for status updates with map location picker
- Division selection based on assignments
- Progress slider for operating status
- Status history display

### Enhanced Incident View
- `/templates/incident_view_enhanced.html`
- Unit management panel
- Division assignment interface
- Real-time status monitoring
- Quick action buttons

### Features
- Interactive map for location updates
- Automatic GPS location detection
- Bootstrap 5 responsive design
- Real-time data refresh
- Status history tracking

## Security & Validation

### Input Validation
- Required field validation
- Status transition rules
- Coordinate range validation
- SQL injection prevention

### Database Security
- Parameterized queries
- Transaction rollback on errors
- Proper connection handling
- Audit trail maintenance

## Testing

### Test Coverage
- Unit model functionality
- API endpoint validation
- Status workflow testing
- Error handling verification
- Integration test scenarios

### Test Files
- `tests/test_unit_status.py` - Comprehensive unit tests
- Mock database connections for isolation
- Complete workflow testing

## Usage Examples

### Creating and Managing Units
```python
# Create unit
unit = Unit(
    unit_id='ENG-101',
    unit_name='Engine 101',
    unit_type='Engine', 
    unit_leader='Captain Smith'
)
unit.create_unit('Radio Channel 1')

# Assign to division
unit.assign_to_division('INC-001', 'DIV-A')

# Update status
unit.update_status(
    incident_id='INC-001',
    new_status=Unit.STATUS_OPERATING,
    division_id='DIV-A',
    percentage_complete=50,
    latitude=37.7749,
    longitude=-122.4194,
    notes='Progress update',
    user_name='Officer Jones'
)
```

### API Usage
```bash
# Create unit
curl -X POST /api/unit/create \
  -H "Content-Type: application/json" \
  -d '{"unit_id":"ENG-101","unit_name":"Engine 101","unit_type":"Engine","unit_leader":"Captain Smith"}'

# Update status  
curl -X POST /api/unit/ENG-101/status \
  -H "Content-Type: application/json" \
  -d '{"incident_id":"INC-001","status":"operating","percentage_complete":75}'

# Assign division
curl -X POST /api/incident/INC-001/assign-division \
  -H "Content-Type: application/json" \
  -d '{"unit_id":"ENG-101","division_id":"DIV-A"}'
```

## Future Enhancements

### Planned Features
- WebSocket real-time updates
- Mobile app integration
- Automated status notifications
- Resource availability forecasting
- Performance metrics dashboard

### Integration Points
- QField mobile data collection
- External CAD system integration
- Radio system status updates
- GPS tracking device integration

## Configuration

### Environment Variables
- Database connection settings (inherited from main app)
- External location service APIs
- Real-time update intervals

### Deployment Notes
- Requires PostGIS for location tracking
- Bootstrap 5 and Leaflet for UI components
- Compatible with existing Docker setup
