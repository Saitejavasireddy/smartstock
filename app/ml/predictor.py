import pandas as pd
import numpy as np
from app.models import Transaction, Product
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import warnings
warnings.filterwarnings('ignore')

def get_transaction_df(owner_id=None):
    query = Transaction.query.join(Product).filter(Transaction.type == 'sale')
    if owner_id:
        query = query.filter(Product.owner_id == owner_id)
    transactions = query.all()
    if not transactions:
        return None
    data = []
    for t in transactions:
        data.append({
            'product_id': t.product_id,
            'product_name': t.product.name,
            'quantity': t.quantity,
            'date': t.timestamp.date(),
            'day_of_week': t.timestamp.weekday(),
            'month': t.timestamp.month,
            'quarter': (t.timestamp.month - 1) // 3 + 1,
        })
    return pd.DataFrame(data)

def get_days_of_data(owner_id=None):
    query = Transaction.query.join(Product)
    if owner_id:
        query = query.filter(Product.owner_id == owner_id)
    first = query.order_by(Transaction.timestamp.asc()).first()
    last = query.order_by(Transaction.timestamp.desc()).first()
    if not first or not last:
        return 0
    return (last.timestamp.date() - first.timestamp.date()).days

def prepare_product_features(product_df):
    daily = product_df.groupby('date')['quantity'].sum().reset_index()
    daily.columns = ['date', 'quantity']
    daily['date'] = pd.to_datetime(daily['date'])
    date_range = pd.date_range(start=daily['date'].min(), end=daily['date'].max(), freq='D')
    full_dates = pd.DataFrame({'date': date_range})
    daily = full_dates.merge(daily, on='date', how='left')
    daily['quantity'] = daily['quantity'].fillna(0)
    daily['day_of_week'] = daily['date'].dt.dayofweek
    daily['month'] = daily['date'].dt.month
    daily['quarter'] = daily['date'].dt.quarter
    daily['day_of_year'] = daily['date'].dt.dayofyear
    daily['is_weekend'] = daily['day_of_week'].isin([5, 6]).astype(int)
    for lag in [1, 7, 14]:
        daily[f'lag_{lag}'] = daily['quantity'].shift(lag)
    for window in [7, 14]:
        daily[f'rolling_{window}'] = daily['quantity'].rolling(window=window).mean()
    daily = daily.dropna()
    return daily

def train_model(daily_df):
    feature_cols = [
        'day_of_week', 'month', 'quarter', 'day_of_year', 'is_weekend',
        'lag_1', 'lag_7', 'lag_14', 'rolling_7', 'rolling_14'
    ]
    X = daily_df[feature_cols]
    y = daily_df['quantity']
    if len(X) < 10:
        return None, None, None
    split = int(len(X) * 0.85)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    model = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=5)
    model.fit(X_train, y_train)
    if len(X_test) > 0:
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
    else:
        mae = 0
        r2 = 0
    return model, mae, r2

def predict_future_sales(model, daily_df, days=30):
    feature_cols = [
        'day_of_week', 'month', 'quarter', 'day_of_year', 'is_weekend',
        'lag_1', 'lag_7', 'lag_14', 'rolling_7', 'rolling_14'
    ]
    last_date = daily_df['date'].max()
    recent_sales = daily_df['quantity'].values
    future_predictions = []
    for i in range(days):
        future_date = last_date + timedelta(days=i+1)
        lag_1 = recent_sales[-1] if len(recent_sales) >= 1 else 0
        lag_7 = recent_sales[-7] if len(recent_sales) >= 7 else np.mean(recent_sales)
        lag_14 = recent_sales[-14] if len(recent_sales) >= 14 else np.mean(recent_sales)
        rolling_7 = np.mean(recent_sales[-7:]) if len(recent_sales) >= 7 else np.mean(recent_sales)
        rolling_14 = np.mean(recent_sales[-14:]) if len(recent_sales) >= 14 else np.mean(recent_sales)
        features = pd.DataFrame([{
            'day_of_week': future_date.dayofweek,
            'month': future_date.month,
            'quarter': (future_date.month - 1) // 3 + 1,
            'day_of_year': future_date.dayofyear,
            'is_weekend': 1 if future_date.dayofweek in [5, 6] else 0,
            'lag_1': lag_1, 'lag_7': lag_7, 'lag_14': lag_14,
            'rolling_7': rolling_7, 'rolling_14': rolling_14
        }])
        pred = max(0, model.predict(features[feature_cols])[0])
        future_predictions.append(pred)
        recent_sales = np.append(recent_sales, pred)
    return future_predictions

def get_sales_by_day(df):
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    daily = df.groupby('day_of_week')['quantity'].sum().reset_index()
    daily['day_name'] = daily['day_of_week'].apply(lambda x: day_names[x])
    return daily

def get_sales_by_month(df):
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly = df.groupby('month')['quantity'].sum().reset_index()
    monthly['month_name'] = monthly['month'].apply(lambda x: month_names[x-1])
    return monthly

def get_sales_by_quarter(df):
    quarterly = df.groupby('quarter')['quantity'].sum().reset_index()
    quarterly['quarter_name'] = quarterly['quarter'].apply(lambda x: f'Q{x}')
    return quarterly

def get_all_predictions(owner_id=None):
    days = get_days_of_data(owner_id)
    if days < 30:
        return {'ready': False, 'days_available': days, 'days_needed': 30 - days}
    df = get_transaction_df(owner_id)
    if df is None:
        return {'ready': False, 'days_available': 0, 'days_needed': 30}
    products = Product.query.filter_by(owner_id=owner_id).all()
    stockout_predictions = []
    model_performance = []
    for product in products:
        product_df = df[df['product_id'] == product.id].copy()
        if len(product_df) < 10:
            continue
        daily_df = prepare_product_features(product_df)
        if len(daily_df) < 10:
            continue
        model, mae, r2 = train_model(daily_df)
        if model is None:
            continue
        future_sales = predict_future_sales(model, daily_df, days=30)
        total_predicted = sum(future_sales)
        avg_daily = np.mean(future_sales)
        stock_left = product.current_stock
        days_until_stockout = 0
        for daily_pred in future_sales:
            if stock_left <= 0:
                break
            stock_left -= daily_pred
            days_until_stockout += 1
        if stock_left > 0:
            days_until_stockout = 30
        stockout_predictions.append({
            'name': product.name,
            'current_stock': product.current_stock,
            'unit': product.unit,
            'days_until_stockout': round(days_until_stockout, 1),
            'predicted_30day_sales': round(total_predicted, 0),
            'avg_daily_predicted': round(avg_daily, 1),
            'status': 'critical' if days_until_stockout <= 3 else 'warning' if days_until_stockout <= 7 else 'ok',
            'mae': round(mae, 2),
            'r2': round(r2, 4)
        })
        model_performance.append({'product_name': product.name, 'mae': round(mae, 2), 'r2': round(r2, 4)})
    stockout_predictions.sort(key=lambda x: x['days_until_stockout'])
    best_sellers = df.groupby('product_name')['quantity'].sum().sort_values(ascending=False).reset_index()
    best_sellers.columns = ['product_name', 'total_sold']
    worst_sellers = df.groupby('product_name')['quantity'].sum().sort_values(ascending=True).reset_index()
    worst_sellers.columns = ['product_name', 'total_sold']
    return {
        'ready': True,
        'days_available': days,
        'stockout_predictions': stockout_predictions,
        'best_sellers': best_sellers.to_dict('records'),
        'worst_sellers': worst_sellers.to_dict('records'),
        'sales_by_day': get_sales_by_day(df).to_dict('records'),
        'sales_by_month': get_sales_by_month(df).to_dict('records'),
        'sales_by_quarter': get_sales_by_quarter(df).to_dict('records'),
        'model_performance': model_performance
    }