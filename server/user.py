from flask import Blueprint
from flask import request, render_template, redirect, url_for, flash, session
from email_validator import validate_email, EmailNotValidError
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from misc.extensions import ALREADY_ADDED, DB_ERROR, db
from misc.alchemy_db import AlchemyDb, Role
from .llm import LLM_PROVIDERS, get_llm_provider, get_llm_model, set_llm_settings, set_llm_api_key

# refering to url from different module is url_for("user.add")
user_bp = Blueprint("user", __name__)
dbApi = AlchemyDb()

login_manager = LoginManager()
login_manager.login_view = 'user.login'

CHART_PROVIDERS = {"chartjs", "lightweight"}


@user_bp.route('/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    state, e = dbApi.deleteUser(user_id)
    
    if state is DB_ERROR:
        flash(f'An error occurred: {e}', 'error')
    else:
        flash('User deleted successfully!', 'success')

    if current_user.role == Role.ADMIN:
        return redirect(url_for('user.index'))
    else: 
        return redirect(url_for('news.news'))

@user_bp.route('/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']

        if not name or not email:
            flash('Name and email are required!', 'error')
            return redirect(url_for('user.add_user'))
        
        try:
            validate_email(email)
        except EmailNotValidError as e:
            flash(f"Error: Invalid email address - {str(e)}", "error")
            return redirect(url_for('user.add_user'))

        state, e = dbApi.addUser(name, email)
        if state is ALREADY_ADDED:
            flash('User already added!', 'warning')
        elif state is DB_ERROR:
            flash(f'An error occurred: {e}', 'error')
        else:
            flash('User added successfully!', 'success')

        return redirect(url_for('user.add_user'))
     
    return render_template('add_user.html') 

# Load user for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    # return  dbApi.getUser(user_id = int(user_id))
    return  dbApi.getUserById(int(user_id))

@user_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        # Validate inputs
        if not name or not email or not password:
            flash("Error: All fields are required", "error")
            return redirect(url_for('user.register'))
        
        try:
            validate_email(email)
        except EmailNotValidError as e:
            flash(f"Error: Invalid email address - {str(e)}", "error")
            return redirect(url_for('user.register'))

        state, e = dbApi.addUser(name, email, password)
        if state is ALREADY_ADDED:
            flash('User already added!', 'warning')
        elif state is DB_ERROR:
            flash(f'An error occurred: {e}', 'error')
        else:
            flash('User added successfully!', 'success')
        return redirect(url_for('user.register'))     

    return render_template('register.html')

@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Validate inputs
        if not email or not password:
            flash("Error: Both email and password are required", "error")
            return redirect(url_for('user.login'))

        # Find the user by email
        user = dbApi.validateUser(email, password)
        if user:
            session.pop("favorites", None)
            login_user(user, remember=True)
            # Not used on target page
            # flash(f"Success: Logged in as {user.name}", "success")
            next_page = request.args.get("next")
            if user.role == Role.ADMIN:
                return redirect(next_page or url_for('user.index')) 
            else: 
                return redirect(next_page or url_for('news.news')) 
        else:
            flash("Error: Invalid email or password", "error")

    return render_template('login.html')

@user_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop("favorites", None)
    flash("Success: You have been logged out", "success")
    return redirect(url_for('user.login'))


@user_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        chart_provider = request.form.get('chart_provider')
        if chart_provider not in CHART_PROVIDERS:
            flash('Please select a valid chart provider.', 'error')
            return redirect(url_for('user.settings'))

        llm_provider = request.form.get('llm_provider')
        llm_model = request.form.get('llm_model')
        try:
            set_llm_settings(llm_provider, llm_model)
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('user.settings'))

        llm_api_key = request.form.get('llm_api_key', '')
        if llm_api_key.strip():
            set_llm_api_key(llm_api_key)

        current_user.chart_provider = chart_provider
        db.session.commit()
        flash('Settings saved successfully.', 'success')
        return redirect(url_for('user.settings'))

    llm_provider = get_llm_provider()
    return render_template(
        'settings.html',
        llm_providers=LLM_PROVIDERS,
        llm_provider=llm_provider,
        llm_model=get_llm_model(),
        llm_models=LLM_PROVIDERS[llm_provider]["models"],
    )


@user_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if not current_user.is_admin():
        flash("Error: You do not have permission to access this page", "error")
        return redirect(url_for('user.add_user'))

    users = dbApi.getUsers()
    return render_template('index.html', users=users)