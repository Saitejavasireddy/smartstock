from flask import Blueprint

employee = Blueprint('employee', __name__)

from app.employee import routes