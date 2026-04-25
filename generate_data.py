from app import create_app, db
from app.models import Product, Transaction, User
from datetime import datetime, timedelta
import random
import numpy as np

app = create_app()

with app.app_context():
    products = Product.query.all()
    employee = User.query.filter_by(role='employee').first()
    admin = User.query.filter_by(role='admin').first()
    user = employee if employee else admin

    # Define sales patterns per product
    patterns = {
        'cola':         {'avg': 8,  'peak': [4, 5], 'monthly_boost': {6:1.5, 7:1.5, 8:1.5, 12:1.3}},
        'Pepsi 500ml':  {'avg': 6,  'peak': [4, 5], 'monthly_boost': {6:1.4, 7:1.4, 12:1.2}},
        'Lays Chips':   {'avg': 5,  'peak': [5, 6], 'monthly_boost': {10:1.3, 11:1.5, 12:1.8}},
        'water':        {'avg': 12, 'peak': [0,1,2,3,4], 'monthly_boost': {5:1.5, 6:2.0, 7:2.0, 8:1.8}},
        'Chocolate':    {'avg': 4,  'peak': [5, 6], 'monthly_boost': {2:1.8, 10:1.3, 12:2.0}},
        'Noodles':      {'avg': 3,  'peak': [0, 6], 'monthly_boost': {11:1.4, 12:1.5, 1:1.3}},
    }

    # Generate 6 months back from 30 days ago
    end_date = datetime.now() - timedelta(days=31)
    start_date = end_date - timedelta(days=180)
    
    total_transactions = 0
    current_date = start_date

    print("Generating 6 months of historical data...")

    while current_date <= end_date:
        day_of_week = current_date.weekday()
        month = current_date.month

        for product in products:
            pattern = patterns.get(product.name, {'avg': 4, 'peak': [4,5], 'monthly_boost': {}})

            if random.random() < 0.15:
                continue

            avg = pattern['avg']
            if day_of_week in pattern['peak']:
                avg = avg * 1.4
            boost = pattern['monthly_boost'].get(month, 1.0)
            avg = avg * boost
            quantity = max(1, int(random.gauss(avg, avg * 0.3)))

            transaction = Transaction(
                product_id=product.id,
                user_id=user.id,
                type='sale',
                quantity=float(quantity),
                note=f'Historical data',
                timestamp=current_date.replace(
                    hour=random.randint(8, 20),
                    minute=random.randint(0, 59)
                )
            )
            db.session.add(transaction)
            total_transactions += 1

        # Restock every 7 days
        if current_date.weekday() == 0:
            for product in products:
                if random.random() < 0.6:
                    transaction = Transaction(
                        product_id=product.id,
                        user_id=user.id,
                        type='restock',
                        quantity=float(random.randint(20, 50)),
                        note='Weekly restock',
                        timestamp=current_date.replace(hour=9, minute=0)
                    )
                    db.session.add(transaction)
                    total_transactions += 1

        current_date += timedelta(days=1)

    db.session.commit()
    print(f"Done! Generated {total_transactions} additional transactions.")
    print("Total transactions now:")