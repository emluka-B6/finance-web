from werkzeug.security import generate_password_hash
from flask import Flask

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
main_dir = os.path.dirname(current_dir)
misc_dir = os.path.join(main_dir, 'misc')
sys.path.insert(0, misc_dir)

from extensions import db
from alchemy_db import AlchemyDb, Role

app = Flask(__name__)

if __name__ == '__main__':
    dbApi = AlchemyDb()
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sqlite_alchemy.db' 
    db.init_app(app)
    with app.app_context():
        db.create_all()  # Create tables if they don't exist

    with app.app_context():
        hashed_password = generate_password_hash("adminpassword")
        res = dbApi.addUser("Admin", "admin@example.com", hashed_password, Role.ADMIN)
        print("res ", res)