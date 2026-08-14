# extensions.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
DB_SUCCESS = 0
ALREADY_ADDED = 1
DB_ERROR = 2

def init_db(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sqlite_alchemy.db' 
    db.init_app(app)
    with app.app_context():
        db.create_all()  # Create tables if they don't exist