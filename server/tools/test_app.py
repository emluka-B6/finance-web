import os
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "dev_secret_key")

# --- MAIN DB (for app models) ---
main_db_path = os.path.join(app.root_path, "main_app.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{main_db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- SESSION DB (as a SQLAlchemy bind) ---
session_db_path = os.path.join(app.root_path, "session_data.db")
app.config['SQLALCHEMY_BINDS'] = {
    'sessions': f"sqlite:///{session_db_path}"
}

# Initialize a single SQLAlchemy instance
db = SQLAlchemy(app)

# --- Flask-Session setup using that db instance ---
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SESSION_SQLALCHEMY'] = db
app.config['SESSION_SQLALCHEMY_TABLE'] = 'flask_sessions'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True

Session(app)

# --- Example model in main DB ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='User')

# --- Create both sets of tables ---
with app.app_context():
    db.create_all()  # creates models in main_app.db
    # create the sessions table in the bound session database
    session_engine = db.engines['sessions']
    db.metadata.create_all(bind=session_engine)

# --- Example route ---
@app.route('/')
def index():
    session['visited'] = session.get('visited', 0) + 1
    return f"Welcome! You’ve visited {session['visited']} times."

if __name__ == '__main__':
    app.run(debug=True)
