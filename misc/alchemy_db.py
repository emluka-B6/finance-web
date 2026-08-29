import sys
print("Loaded user module as:", __name__)
print("Module path:", sys.modules[__name__])

from .extensions import db
from .extensions import ALREADY_ADDED, DB_ERROR, DB_SUCCESS
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

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
    favorites = db.relationship("Favorite", backref="user", cascade="all, delete-orphan", lazy=True)

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

    
class Favorite(db.Model):
    __table_args__ = (db.UniqueConstraint("user_id", "symbol", name="uq_favorite_user_symbol"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(120), nullable=False)


class AlchemyDb():
    def getUsers(__self__):
        users = User.query.all()
        return users
    
    def getUserById(__self__, user_id):
        return User.query.get(user_id);

    def getUserByMail(__self__, email):
        return User.query.filter_by(email=email).first()

    def validateUser(__self__, email, password):
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            return user
        return None

    def getUser(__self__, **kwargs):
        if 'email' in kwargs:
          return User.query.filter_by(email=kwargs['email']).first()

        if 'user_id' in kwargs:
            return User.query.get(kwargs['user_id'])
        
        raise Exception("Only email or user_id")

        
    def addUser(__self__, name, email, password, role = Role.USER):
        existing_user_by_email = User.query.filter_by(email=email).first()
        existing_user = User.query.filter_by(name=name).first()
        if existing_user or existing_user_by_email:
            return ALREADY_ADDED, None
    
        hashed = generate_password_hash(password)
        # new_user = User(name, email)
        new_user = User(name=name, email=email, password=hashed, role=role)

        try:
            db.session.add(new_user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return DB_ERROR, str(e)

        return DB_SUCCESS, None
    
    def deleteUser(__self__, user_id):
        user = db.session.get(User, user_id)
        if user is None:
            return DB_ERROR, "NOT ADDED"
        
        try:
            db.session.delete(user) 
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return DB_ERROR, e
        
        return DB_SUCCESS, None