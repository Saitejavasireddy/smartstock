from app import create_app, db
from app.models import User, Product, Transaction, Alert

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        print("Connecting to:", app.config['SQLALCHEMY_DATABASE_URI'])
        db.create_all()
        print("Database tables created successfully!")
    app.run(debug=True)