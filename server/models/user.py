import sys
print("Loaded user module as:", __name__)
print("Module path:", sys.modules[__name__])

from flask_login import UserMixin
from misc.extensions import db

# Define roles as constants
class Role:
    ADMIN = 'Admin'
    USER = 'User'

class User(UserMixin, db.Model):
    # for relative imports in more than one file, then is attempt to create two tables in db  
    # __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False) # Ensure names are unique
    email = db.Column(db.String(80), unique=True, nullable=False) # Add email field
    password = db.Column(db.String(120), nullable=False, default="")  # Add password field
    role = db.Column(db.String(20), nullable=False, default=Role.USER)  # Add role field

    # def __self__(self, _name, _email):
        # self.name = _name
        # self.email = _email

    def __repr__(self):
        return '<User %r>' % self.name
    
    def is_admin(self):
        return self.role == Role.ADMIN
    
    def get_id(self): # While UserMixin provides this, it's good to understand
        return str(self.id) # Flask-Login expects ID as a string
    
    def is_authenticated(self):
        return True  # Ensure this returns True for logged-in users
    
    def is_active(self):
        return True  # Ensure the user is active
