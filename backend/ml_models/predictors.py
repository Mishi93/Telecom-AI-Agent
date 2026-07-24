"""
Loads the trained churn and package-tier models and exposes prediction
functions for a given customer_id, using the customer's current live data
from the database.
"""
import joblib
import pandas as pd
from pathlib import Path

from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import Customer, Complaint

_ML_DIR = Path(__file__).resolve().parent
CHURN_MODEL_PATH = _ML_DIR / "saved" / "churn_xgb.pkl"
PACKAGE_MODEL_PATH = _ML_DIR / "saved" / "package_rf.pkl"

_churn_bundle = None
_package_bundle = None


def _load_churn_bundle():
    global _churn_bundle
    if _churn_bundle is None:
        if not CHURN_MODEL_PATH.exists():
            raise RuntimeError(
                f"Churn model not found at {CHURN_MODEL_PATH}. "
                "Run 'python data_pipeline/train_models.py' first."
            )
        _churn_bundle = joblib.load(CHURN_MODEL_PATH)
    return _churn_bundle


def _load_package_bundle():
    global _package_bundle
    if _package_bundle is None:
        if not PACKAGE_MODEL_PATH.exists():
            raise RuntimeError(
                f"Package model not found at {PACKAGE_MODEL_PATH}. "
                "Run 'python data_pipeline/train_models.py' first."
            )
        _package_bundle = joblib.load(PACKAGE_MODEL_PATH)
    return _package_bundle


def _parse_data_gb(data_remaining: str) -> float:
    if data_remaining is None:
        return 0.0
    cleaned = str(data_remaining).strip().lower()
    if cleaned == "unlimited":
        return 999.0
    try:
        return float(cleaned.replace("gb", "").strip())
    except ValueError:
        return 0.0


def _build_feature_row(customer: Customer, complaints: list) -> dict:
    data_gb = _parse_data_gb(customer.data_remaining)
    has_unlimited = 1 if str(customer.data_remaining).strip().lower() == "unlimited" else 0

    total_complaints = len(complaints)
    open_complaints = sum(1 for c in complaints if c.status == "Open")
    high_priority_complaints = sum(1 for c in complaints if c.priority == "High")
    billing_complaints = sum(1 for c in complaints if c.issue_type == "Billing")
    network_complaints = sum(1 for c in complaints if c.issue_type == "Network")

    return {
        "balance": customer.balance,
        "data_gb": data_gb,
        "has_unlimited_data": has_unlimited,
        "minutes_remaining": customer.minutes_remaining,
        "total_complaints": total_complaints,
        "open_complaints": open_complaints,
        "high_priority_complaints": high_priority_complaints,
        "billing_complaints": billing_complaints,
        "network_complaints": network_complaints,
    }


def _get_customer_and_complaints(db: Session, customer_id: str):
    clean_id = str(customer_id).strip()
    customer = db.query(Customer).filter(Customer.customer_id == clean_id).first()
    if not customer:
        return None, None
    complaints = db.query(Complaint).filter(Complaint.customer_id == clean_id).all()
    return customer, complaints


def predict_churn(customer_id: str) -> dict:
    """Returns churn risk prediction for a customer based on their usage metrics."""
    bundle = _load_churn_bundle()
    model = bundle["model"]
    feature_columns = bundle["feature_columns"]

    db = SessionLocal()
    try:
        customer, complaints = _get_customer_and_complaints(db, customer_id)
        if not customer:
            return {"error": f"Customer '{customer_id}' not found."}

        features = _build_feature_row(customer, complaints)
        
        # FIX: Wrapped raw feature array in a DataFrame with matching column names
        X = pd.DataFrame([[features[col] for col in feature_columns]], columns=feature_columns)

        prediction = int(model.predict(X)[0])
        probability = float(model.predict_proba(X)[0][1])

        return {
            "customer_id": customer.customer_id,
            "churn_risk": bool(prediction),
            "churn_probability": round(probability, 4),
            "label": "At Risk" if prediction == 1 else "Stable",
        }
    finally:
        db.close()


def recommend_package(customer_id: str) -> dict:
    """Returns a recommended plan tier for a customer based on usage patterns."""
    bundle = _load_package_bundle()
    model = bundle["model"]
    feature_columns = bundle["feature_columns"]

    db = SessionLocal()
    try:
        customer, complaints = _get_customer_and_complaints(db, customer_id)
        if not customer:
            return {"error": f"Customer '{customer_id}' not found."}

        features = _build_feature_row(customer, complaints)
        
        # FIX: Wrapped raw feature array in a DataFrame with matching column names
        X = pd.DataFrame([[features[col] for col in feature_columns]], columns=feature_columns)

        prediction = model.predict(X)[0]
        probabilities = model.predict_proba(X)[0]
        class_probabilities = dict(zip(model.classes_, [round(float(p), 4) for p in probabilities]))

        return {
            "customer_id": customer.customer_id,
            "recommended_tier": str(prediction),
            "tier_probabilities": class_probabilities,
        }
    finally:
        db.close()