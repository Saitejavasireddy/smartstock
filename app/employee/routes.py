from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.employee import employee
from app.models import Product, Transaction, Alert
from app import db
from functools import wraps

def employee_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['employee', 'admin']:
            flash('Access denied!', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@employee.route('/employee/dashboard')
@login_required
@employee_required
def dashboard():
    products = Product.query.all()
    low_stock = Product.query.filter(Product.current_stock <= Product.threshold).all()
    return render_template('employee/dashboard.html', 
                           products=products,
                           low_stock=low_stock)

@employee.route('/employee/update-stock', methods=['GET', 'POST'])
@login_required
@employee_required
def update_stock():
    products = Product.query.all()
    
    if request.method == 'POST':
        product_id = int(request.form.get('product_id'))
        transaction_type = request.form.get('type')
        quantity = float(request.form.get('quantity'))
        note = request.form.get('note')

        product = Product.query.get_or_404(product_id)

        if transaction_type == 'sale':
            if quantity > product.current_stock:
                flash('Not enough stock available!', 'danger')
                return redirect(url_for('employee.update_stock'))
            product.current_stock -= quantity
        else:
            product.current_stock += quantity

        transaction = Transaction(
            product_id=product_id,
            user_id=current_user.id,
            type=transaction_type,
            quantity=quantity,
            note=note
        )
        db.session.add(transaction)
        db.session.commit()

        # Check threshold and create alert
        if product.current_stock <= product.threshold:
            existing_alert = Alert.query.filter_by(
                product_id=product_id, 
                is_read=False
            ).first()
            if not existing_alert:
                alert = Alert(
                    product_id=product_id,
                    alert_type='low_stock',
                    message=f'LOW STOCK ALERT: {product.name} has only {product.current_stock} {product.unit} left. Reorder threshold is {product.threshold}.'
                )
                db.session.add(alert)
                db.session.commit()

                # Send email alert
                from app.utils.alerts import send_low_stock_alert
                send_low_stock_alert(product)

        flash(f'Stock updated successfully!', 'success')
        return redirect(url_for('employee.update_stock'))

    return render_template('employee/update_stock.html', products=products)

@employee.route('/employee/transactions')
@login_required
@employee_required
def transactions():
    my_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.timestamp.desc()).all()
    return render_template('employee/transactions.html', 
                           transactions=my_transactions)