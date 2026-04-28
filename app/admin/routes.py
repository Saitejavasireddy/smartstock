from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.admin import admin
from app.models import Product, Transaction, Alert, User
from app import db
from functools import wraps
from datetime import datetime, timedelta

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Access denied!', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin.route('/admin/dashboard')
@login_required
@admin_required
def dashboard():
    total_products = Product.query.filter_by(owner_id=current_user.id).count()
    low_stock_products = Product.query.filter(
        Product.owner_id == current_user.id,
        Product.current_stock <= Product.threshold
    ).all()
    unread_alerts = Alert.query.join(Product).filter(
        Product.owner_id == current_user.id,
        Alert.is_read == False
    ).count()
    recent_transactions = Transaction.query.join(Product).filter(
        Product.owner_id == current_user.id
    ).order_by(Transaction.timestamp.desc()).limit(5).all()

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    daily_sales = db.session.execute(db.text("""
        SELECT DATE(t.timestamp) as date, SUM(t.quantity) as total
        FROM transactions t
        JOIN products p ON t.product_id = p.id
        WHERE t.type = 'sale' AND t.timestamp >= :start AND p.owner_id = :owner_id
        GROUP BY DATE(t.timestamp)
        ORDER BY DATE(t.timestamp)
    """), {'start': thirty_days_ago, 'owner_id': current_user.id}).fetchall()

    chart_labels = [str(row[0]) for row in daily_sales]
    chart_data = [float(row[1]) for row in daily_sales]

    top_products = db.session.execute(db.text("""
        SELECT p.name, SUM(t.quantity) as total
        FROM transactions t
        JOIN products p ON t.product_id = p.id
        WHERE t.type = 'sale' AND p.owner_id = :owner_id
        GROUP BY p.name
        ORDER BY total DESC
        LIMIT 6
    """), {'owner_id': current_user.id}).fetchall()

    product_labels = [row[0] for row in top_products]
    product_data = [float(row[1]) for row in top_products]

    return render_template('admin/dashboard.html',
                           total_products=total_products,
                           low_stock=len(low_stock_products),
                           low_stock_products=low_stock_products,
                           unread_alerts=unread_alerts,
                           unread_count=unread_alerts,
                           recent_transactions=recent_transactions,
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           product_labels=product_labels,
                           product_data=product_data)

@admin.route('/admin/products')
@login_required
@admin_required
def products():
    all_products = Product.query.filter_by(owner_id=current_user.id).all()
    return render_template('admin/products.html', products=all_products)

@admin.route('/admin/products/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        unit = request.form.get('unit')
        current_stock = float(request.form.get('current_stock'))
        threshold = float(request.form.get('threshold'))

        product = Product(
            name=name,
            category=category,
            unit=unit,
            current_stock=current_stock,
            threshold=threshold,
            created_by=current_user.id,
            owner_id=current_user.id
        )
        db.session.add(product)
        db.session.commit()
        flash(f'Product "{name}" added successfully!', 'success')
        return redirect(url_for('admin.products'))

    return render_template('admin/add_product.html')

@admin.route('/admin/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(id):
    product = Product.query.filter_by(id=id, owner_id=current_user.id).first_or_404()

    if request.method == 'POST':
        product.name = request.form.get('name')
        product.category = request.form.get('category')
        product.unit = request.form.get('unit')
        product.current_stock = float(request.form.get('current_stock'))
        product.threshold = float(request.form.get('threshold'))
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('admin.products'))

    return render_template('admin/edit_product.html', product=product)

@admin.route('/admin/products/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_product(id):
    product = Product.query.filter_by(id=id, owner_id=current_user.id).first_or_404()
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('admin.products'))

@admin.route('/admin/employees')
@login_required
@admin_required
def employees():
    all_employees = User.query.filter_by(role='employee', owner_id=current_user.id).all()
    return render_template('admin/employees.html', employees=all_employees)

@admin.route('/admin/employees/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_employee():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('Email already exists!', 'danger')
            return redirect(url_for('admin.add_employee'))

        from werkzeug.security import generate_password_hash
        employee = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role='employee',
            owner_id=current_user.id
        )
        db.session.add(employee)
        db.session.commit()
        flash(f'Employee "{name}" added successfully!', 'success')
        return redirect(url_for('admin.employees'))

    return render_template('admin/add_employee.html')

@admin.route('/admin/employees/deactivate/<int:id>', methods=['POST'])
@login_required
@admin_required
def deactivate_employee(id):
    employee = User.query.get_or_404(id)
    employee.is_active = False
    db.session.commit()
    flash(f'Employee "{employee.name}" deactivated!', 'warning')
    return redirect(url_for('admin.employees'))

@admin.route('/admin/alerts')
@login_required
@admin_required
def alerts():
    all_alerts = Alert.query.join(Product).filter(
        Product.owner_id == current_user.id
    ).order_by(Alert.created_at.desc()).all()
    return render_template('admin/alerts.html', alerts=all_alerts)

@admin.route('/admin/alerts/read/<int:id>', methods=['POST'])
@login_required
@admin_required
def mark_read(id):
    alert = Alert.query.get_or_404(id)
    alert.is_read = True
    db.session.commit()
    flash('Alert marked as read!', 'success')
    return redirect(url_for('admin.alerts'))

@admin.route('/admin/transactions')
@login_required
@admin_required
def transactions():
    all_transactions = Transaction.query.join(Product).filter(
        Product.owner_id == current_user.id
    ).order_by(Transaction.timestamp.desc()).all()
    return render_template('admin/transactions.html', transactions=all_transactions)

@admin.route('/admin/predictions')
@login_required
@admin_required
def predictions():
    from app.ml.predictor import get_all_predictions
    data = get_all_predictions(current_user.id)
    return render_template('admin/predictions.html', data=data)