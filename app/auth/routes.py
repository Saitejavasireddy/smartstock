from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth
from app.models import User
from app import db
from werkzeug.security import check_password_hash, generate_password_hash

@auth.route('/')
def landing():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('employee.dashboard'))
    return render_template('landing.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        store_name = request.form.get('store_name')

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('Email already registered!', 'danger')
            return redirect(url_for('auth.register'))

        admin = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role='admin',
            store_name=store_name
        )
        db.session.add(admin)
        db.session.commit()
        login_user(admin, remember=True)
        flash(f'Welcome to SmartStock, {name}!', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('auth/register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('employee.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=True)

        if user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('employee.dashboard'))

    return render_template('auth/login.html')

@auth.route('/employee/login', methods=['GET', 'POST'])
def employee_login():
    if current_user.is_authenticated:
        return redirect(url_for('employee.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email, role='employee').first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password', 'danger')
            return redirect(url_for('auth.employee_login'))

        login_user(user, remember=True)
        return redirect(url_for('employee.dashboard'))

    return render_template('auth/employee_login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.landing'))