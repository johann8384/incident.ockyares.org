import requests
import tempfile
import zipfile
from pathlib import Path

class QFieldCloudManager:
    def __init__(self, api_token=None):
        self.api_token = api_token or os.getenv('QFIELD_CLOUD_TOKEN')
        self.base_url = 'https://app.qfield.org/api/v1'
        
    def create_project(self, incident_id, team_info, db_config):
        """Create a QField Cloud project for a team"""
        if not self.api_token:
            app.logger.warning("No QField Cloud API token configured")
            return None
            
        project_name = f"{incident_id}_{team_info['team_id']}"
        
        # Create QGIS project file
        qgis_project = self.generate_qgis_project(incident_id, team_info, db_config)
        
        # Create project on QField Cloud
        headers = {
            'Authorization': f'Token {self.api_token}',
            'Content-Type': 'application/json'
        }
        
        project_data = {
            'name': project_name,
            'description': f'Emergency response project for {team_info["team_name"]}',
            'public': False
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/projects/',
                headers=headers,
                json=project_data
            )
            
            if response.status_code == 201:
                project = response.json()
                
                # Upload QGIS project file
                self.upload_project_file(project['id'], qgis_project, headers)
                
                app.logger.info(f"Created QField project: {project_name}")
                return project
            else:
                app.logger.error(f"Failed to create QField project: {response.text}")
                return None
                
        except Exception as e:
            app.logger.error(f"Error creating QField project: {e}")
            return None
    
    def generate_qgis_project(self, incident_id, team_info, db_config):
        """Generate a QGIS project file with incident-specific layers"""
        # This would create a proper QGIS project XML
        # For now, return a basic project structure
        
        project_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<qgis version="3.28.0" projectname="{incident_id}_{team_info['team_id']}">
  <title>{incident_id} - {team_info['team_name']}</title>
  <projectlayers>
    <!-- Incident boundaries layer -->
    <maplayer type="vector" geometry="Polygon">
      <id>search_areas</id>
      <datasource>host={db_config['host']} port=5432 dbname={db_config['database']} 
                  user={team_info['team_id']} password=team_password 
                  table="search_areas" (geom) sql=incident_id='{incident_id}'</datasource>
      <layername>Search Areas</layername>
    </maplayer>
    
    <!-- Team divisions layer -->
    <maplayer type="vector" geometry="Polygon">
      <id>divisions</id>
      <datasource>host={db_config['host']} port=5432 dbname={db_config['database']} 
                  user={team_info['team_id']} password=team_password 
                  table="search_divisions" (geom) sql=assigned_team='{team_info['team_name']}'</datasource>
      <layername>My Divisions</layername>
    </maplayer>
    
    <!-- Points of interest/findings -->
    <maplayer type="vector" geometry="Point">
      <id>findings</id>
      <datasource>host={db_config['host']} port=5432 dbname={db_config['database']} 
                  user={team_info['team_id']} password=team_password 
                  table="incident_findings" (geom)</datasource>
      <layername>Findings</layername>
    </maplayer>
  </projectlayers>
</qgis>"""
        
        return project_xml
    
    def upload_project_file(self, project_id, project_content, headers):
        """Upload QGIS project file to QField Cloud"""
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.qgs', delete=False) as f:
            f.write(project_content.encode())
            temp_path = f.name
        
        try:
            files = {
                'file': ('project.qgs', open(temp_path, 'rb'), 'application/octet-stream')
            }
            
            response = requests.post(
                f'{self.base_url}/projects/{project_id}/files/',
                headers={k: v for k, v in headers.items() if k != 'Content-Type'},
                files=files
            )
            
            if response.status_code != 201:
                app.logger.error(f"Failed to upload project file: {response.text}")
                
        finally:
            os.unlink(temp_path)

# Add to IncidentManager class
def create_database_users(self, incident_id, teams):
    """Create database users for each team with restricted access"""
    conn = self.connect_db()
    cursor = conn.cursor()
    
    try:
        for team in teams:
            team_id = team['team_id']
            username = f"team_{team_id}"
            password = f"temp_pass_{incident_id}_{team_id}"  # Generate secure password
            
            # Create user
            cursor.execute(f"""
                CREATE USER "{username}" WITH PASSWORD %s;
            """, (password,))
            
            # Grant limited permissions
            cursor.execute(f"""
                GRANT CONNECT ON DATABASE {DB_CONFIG['database']} TO "{username}";
                GRANT USAGE ON SCHEMA public TO "{username}";
                GRANT SELECT ON incidents, search_areas TO "{username}";
                GRANT SELECT, INSERT, UPDATE ON incident_findings TO "{username}";
                GRANT SELECT ON search_divisions TO "{username}";
            """)
            
            # Add row-level security
            cursor.execute(f"""
                CREATE POLICY team_policy_{team_id} ON search_divisions 
                FOR ALL TO "{username}" 
                USING (assigned_team = %s);
            """, (team['team_name'],))
            
        conn.commit()
        app.logger.info(f"Created database users for {len(teams)} teams")
        
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Failed to create database users: {e}")
        raise e
    finally:
        cursor.close()
        self.close_db()
