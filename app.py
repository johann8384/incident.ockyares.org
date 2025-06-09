import os
import logging

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from models.database import DatabaseManager
from services.geocoding import GeocodingService
from routes import ALL_BLUEPRINTS

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize services
db_manager = DatabaseManager()
geocode_service = GeocodingService()

# Register all route blueprints
for blueprint in ALL_BLUEPRINTS:
    app.register_blueprint(blueprint)
    logger.info(f"Registered blueprint: {blueprint.name}")


@app.errorhandler(404)
def not_found(error):
    logger.warning(f"404 error: {request.path} not found")
    return jsonify({"error": "Endpoint not found", "path": request.path}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    logger.warning(f"405 error: {request.method} not allowed for {request.path}")
    return jsonify({"error": "Method not allowed", "method": request.method, "path": request.path}), 405


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {str(error)}")
    return jsonify({"error": "Internal server error", "message": str(error)}), 500


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    # Initialize database schema on startup
    try:
        db_manager.create_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    logger.info("Starting Emergency Incident Management System with modular routes")
    app.run(
        debug=os.getenv("FLASK_DEBUG", "True").lower() == "true",
        host="0.0.0.0",
        port=int(os.getenv("FLASK_PORT", 5000)),
    )
