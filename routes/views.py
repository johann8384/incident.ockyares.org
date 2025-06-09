"""View routes for HTML page rendering"""

from flask import Blueprint, render_template

views_bp = Blueprint('views', __name__)


@views_bp.route("/")
def index():
    """Main incident creation page"""
    return render_template("index.html")


@views_bp.route("/incident/<incident_id>")
def view_incident(incident_id):
    """View specific incident"""
    return render_template("incident_view.html", incident_id=incident_id)


@views_bp.route("/incident/<incident_id>/unit-checkin")
def unit_checkin(incident_id):
    """Unit checkin page"""
    return render_template("unit_checkin.html", incident_id=incident_id)


@views_bp.route("/incident/<incident_id>/unit-status")
def unit_status_page(incident_id):
    """Unit status update page"""
    return render_template("unit_status.html", incident_id=incident_id)
