from flask_mail import Message
from app import mail
from app.models import User

def send_low_stock_alert(product):
    try:
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            return

        msg = Message(
            subject=f'LOW STOCK ALERT: {product.name}',
            recipients=[admin.email],
            body=f'''
SmartStock Inventory Alert

Product: {product.name}
Category: {product.category}
Current Stock: {product.current_stock} {product.unit}
Reorder Threshold: {product.threshold} {product.unit}

Action Required: Please reorder {product.name} immediately.

This is an automated alert from SmartStock.
            '''
        )
        mail.send(msg)
        print(f"Alert email sent for {product.name}")
    except Exception as e:
        print(f"Email not sent: {e}")