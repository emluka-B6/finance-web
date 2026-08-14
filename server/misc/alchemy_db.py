from misc.extensions import db, ALREADY_ADDED, DB_ERROR, DB_SUCCESS
from models.user import User, Role

from werkzeug.security import generate_password_hash, check_password_hash

    
class AlchemyDb():
    def getUsers(__self__):
        users = User.query.all()
        return users
    
    def getUserById(__self__, user_id):
        return db.session.get(User, user_id)

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
            return  db.session.get(User, kwargs['user_id'])
        
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
            return DB_ERROR, "User not existing"
        
        try:
            db.session.delete(user) 
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return DB_ERROR, e
        
        return DB_SUCCESS, None