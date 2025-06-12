from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from flask_migrate import Migrate
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash



app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'thesecretkey'

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)])
    password = PasswordField(validators=[InputRequired(), Length(min=6, max=80)])
    submit = SubmitField("Register")

    def validate_username(self, username):
        existing_user = User.query.filter_by(username=username.data).first()
        if existing_user:
            raise ValidationError("Username already exists. Choose a different one.")

class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)])
    password = PasswordField(validators=[InputRequired(), Length(min=6, max=80)])
    submit = SubmitField("Login")

# Routes
@app.route('/')
def home():
    return render_template ("index.html")

"""
This route takes both get and post requests and uses LoginForm as an instance.
If all validators are passed it then checks if username exists in the database.
If it doesn't exist it then check if the password matches the one stored
to the username in the stored hash. If it matches it logs in the user
and sets up a session using flask login.
If the user id is 1 it is treated as a admin and redirected to the admin dashboard.
"""
@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash("Login successfully", "success")
            if user.id == 1:
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("dashboard"))
        flash("Invalid username or password", "danger")
    return render_template("login.html", form=form)

"""
This route takes both get and post requests and uses register form as an instance.
if the form is valid it creates a hashed password from the password the user put into
the form. It then creates a new user and puts a username and the hashed
password to that user. it then commits it to the database.
"""

@app.route('/signup', methods=["GET", "POST"])
def signup():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data, method="pbkdf2:sha256")
        new_user = User(username=form.username.data, password = hashed_password, is_admin=False)
        db.session.add(new_user)
        db.session.commit()
        flash("Account Created", "success")
        return redirect(url_for("login"))
    return render_template("signup.html", form=form)


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template('admin_dashboard.html')



if __name__ == '__main__':
    with app.app_context():
        app.run(debug=True)